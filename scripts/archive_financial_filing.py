"""Archive one explicitly selected CNINFO original; no crawl, retries or fact import."""
import argparse
from datetime import date
import hashlib
import json
from pathlib import Path
import re
import sys
import time
from urllib.parse import urlsplit

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from service.source_connectors.raw_archive import SourceRawArchive
from service.source_connectors.contracts import AcquisitionMode


def validate_url(url):
    parsed = urlsplit(url)
    match = re.fullmatch(r'/finalpage/(\d{4}-\d{2}-\d{2})/(\d+)\.PDF',parsed.path)
    if (parsed.scheme != 'https' or parsed.hostname != 'static.cninfo.com.cn'
        or parsed.port not in (None,443) or parsed.username or parsed.password
        or parsed.query or parsed.fragment or not match):
        raise ValueError('exact original CNINFO PDF URL required')
    date.fromisoformat(match[1])
    return match[1], match[2]


def fetch(url, *, http_get=requests.get):
    validate_url(url)
    deadline = time.monotonic()+60
    with http_get(url,timeout=(5,20),allow_redirects=False,stream=True,
                  headers={'User-Agent':'Mozilla/5.0'}) as response:
        if response.status_code != 200:
            raise ValueError('filing returned non-200 or redirect; no retry')
        chunks,size = [],0
        for chunk in response.iter_content(65536):
            size += len(chunk)
            if size > 20*1024*1024 or time.monotonic() > deadline:
                raise ValueError('filing response budget exceeded')
            chunks.append(chunk)
        content = b''.join(chunks)
        if not content.startswith(b'%PDF-'):
            raise ValueError('filing response is not a PDF')
        headers = {key:response.headers[key] for key in ('Content-Type','ETag','Last-Modified') if key in response.headers}
        return content,headers


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url',required=True)
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args()
    publication,identifier = validate_url(args.url)
    if args.output.exists():
        raise ValueError('refusing to overwrite an existing evidence file')
    content,headers = fetch(args.url)
    archive = SourceRawArchive(source_id='cninfo',acquisition_mode=AcquisitionMode.WEB_SNAPSHOT)
    evidence = archive.archive_artifact(endpoint_key='financial_filing_'+identifier,
        content_type='application/pdf',content=content,source_url=args.url,http_status=200,
        response_headers=headers,parser_name='reviewed_financial_filing',parser_version='1')
    with args.output.open('xb') as output:
        output.write(content)
    print(json.dumps(dict(**evidence,sha256=hashlib.sha256(content).hexdigest(),
        publication_path_date=publication,bytes=len(content),facts_imported=0)))
