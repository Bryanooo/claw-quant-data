"""Extract reviewed rows from a local official filing using an explicit manifest.

Run with a Python environment containing pypdf. The manifest pins the PDF hash,
security, report dates, scope, unit and reviewed page/label locations. Output is
evidence, not automatic financial-table promotion or historical acceptance.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from service.financial_filing_evidence import extract_two_column_row


def extract(path, spec):
    from pypdf import PdfReader
    raw=path.read_bytes()
    digest=hashlib.sha256(raw).hexdigest()
    if digest!=spec['sha256']:
        raise ValueError('filing changed; page and scope review must be repeated')
    reader=PdfReader(path)
    title_page = spec.get('title_page', 1)
    if not isinstance(title_page, int) or not 1 <= title_page <= len(reader.pages):
        raise ValueError('invalid reviewed title page')
    title=reader.pages[title_page-1].extract_text() or ''
    if spec['title'] not in ''.join(title.split()):
        raise ValueError('wrong filing title')
    if spec['scope']!='consolidated':
        raise ValueError('only reviewed consolidated scope supported')
    rows=[]
    for item in spec['rows']:
        page=item['page']
        value=extract_two_column_row(reader.pages[page-1].extract_text(),item['label'],unit=spec['unit'])
        rows.append(dict(item,**{k:v for k,v in value.items() if k!='label'}))
    return dict(spec,extracted_facts=rows,policy='evidence_only_no_source_overwrite_no_pit_promotion')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest',type=Path,required=True)
    parser.add_argument('--pdf-directory',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    documents=json.loads(args.manifest.read_text())['documents']
    result={'documents':[extract(args.pdf_directory/d['file'],d) for d in documents]}
    args.output.write_text(json.dumps(result,default=str,ensure_ascii=False,indent=2)+'\n')
    print({'documents':len(documents),'facts':sum(len(d['extracted_facts']) for d in result['documents'])})
