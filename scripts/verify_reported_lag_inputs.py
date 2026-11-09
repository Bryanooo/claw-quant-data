"""Extract independently corroborated current amounts for an as-of ROE calculation.

Input is one manifest containing symbol, issuer and three original documents.
Each document supplies path, SHA-256, original URL, disclosure date, period,
and same-disclosure n_income_attr_p. The last also supplies consolidated equity
and minority interest. The resulting evidence can be archived and replayed
through the existing filing-fact importer. This command never writes the DB.
"""
import argparse
import json
from datetime import date
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from service.financial_filing_facts import original_filing_source
from service.financial_filing_tables import read_verified_pdf_pages, verify_tables


def verify(manifest):
    symbol = manifest['symbol']
    docs = sorted(manifest['documents'], key=lambda doc: doc['period'])
    if len(docs) != 3:
        raise ValueError('three original periods required')
    prior, annual, current = [date.fromisoformat(doc['period']) for doc in docs]
    if (current.month, current.day) not in {(3, 31), (6, 30)} or prior != current.replace(year=current.year-1) or annual != date(prior.year,12,31):
        raise ValueError('incompatible interim or annual period')
    result = []
    for doc in docs:
        publication = date.fromisoformat(doc['published_on'])
        if not date.fromisoformat(doc['period']) <= publication < date.fromisoformat(manifest['cutoff']):
            raise ValueError('outside publication window')
        if not original_filing_source(doc['url'], publication):
            raise ValueError('invalid original filing URL')
        last = doc is docs[-1]
        pages = read_verified_pdf_pages(doc['path'], doc['sha256'])
        fields = verify_tables(pages, code=symbol.split('.')[0], issuer=manifest['issuer'],
                               period=doc['period'], income=doc['n_income_attr_p'],
                               balance=doc['balance'] if last else None,
                               comparison=docs[0]['n_income_attr_p'] if last else None)
        for unit in sorted({row['unit'] for _,row in fields}):
            values = [dict(field=field, **row) for field,row in fields if row['unit']==unit]
            result.append(dict(file=doc['path'],symbol=symbol,title=doc['title'],period=doc['period'],
                               published_on=doc['published_on'],url=doc['url'],sha256=doc['sha256'],
                               scope='consolidated',unit=unit,extracted_facts=values,
                               rows=[{k:row[k] for k in ('field','page','label')} for row in values],
                               review='Matched current amounts to same-disclosure consolidated data, '
                                      f'verified printed units, report periods and prior {"Q1" if current.month == 3 else "H1"} comparison.'))
    return result


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    docs=verify(json.loads(args.manifest.read_text()))
    args.output.write_text(json.dumps({'documents':docs}, ensure_ascii=False,indent=2)+'\n')
