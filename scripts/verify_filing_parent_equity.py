"""Read an original interim consolidated balance sheet against independent reported amounts."""
import argparse
from datetime import date
from decimal import Decimal
import json
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from service.financial_filing_facts import original_filing_source
from service.financial_filing_tables import read_verified_pdf_pages, verify_equity_rows


def verify_parent_equity(document):
    path = Path(document['path'])
    disclosure = document['published_on']
    source = original_filing_source(document['url'], disclosure)
    if not source:
        raise ValueError('original_artifact_identity_unproven')
    period = document['period']
    if not date.fromisoformat(period) <= date.fromisoformat(disclosure) < date.fromisoformat(document['cutoff']) or not period.endswith('-09-30'):
        raise ValueError('invalid_q3_publication_window')
    pages = read_verified_pdf_pages(path, document['sha256'])
    cover = ''.join(''.join(pages[:2]).split())
    code = document['symbol'][:6]
    issuer = document['issuer']
    if not re.search(period[:4] + '年第?三季度报告', cover) or not (
            re.search(r'(?<!\d)' + re.escape(code) + r'(?!\d)', cover) or issuer and issuer in cover):
        raise ValueError('issuer_or_period_unproven')
    # A blank minority column in the independent version cannot prove equality.
    # The original must print both closing amounts in separate identified rows.
    total = document['total']
    if Decimal(document['direct']) != Decimal(total):
        raise ValueError('independent_parent_and_total_disagree')
    fields = dict(verify_equity_rows(pages, period, {'total_hldr_eqy_inc_min_int': total}))
    row = dict(field='total_hldr_eqy_exc_min_int', **fields['total_hldr_eqy_exc_min_int'])
    return dict(file=str(path),symbol=document['symbol'],title=document['title'],period=period,
                published_on=disclosure,url=document['url'],sha256=document['sha256'],
                scope='consolidated',unit=row['unit'],extracted_facts=[row],
                rows=[{k:row[k] for k in ('field','page','label')}],
                review='Matched both directly printed parent equity and total consolidated equity '
                       'to separate provider observations for the same disclosure and report period.')

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = verify_parent_equity(json.loads(args.manifest.read_text()))
    args.output.write_text(json.dumps({'documents':[result]}, ensure_ascii=False, indent=2) + '\n')
