"""Replay archived Ant evidence against current Tushare facts without API spend.

Only --probe calls Ant (two bounded subrequests, no retries); every successful
response is retained before comparison. Neither path writes financial values
or certifies historical factor completeness.
"""
import argparse
from datetime import date, datetime, timezone
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from service.db import query
from service.financial_reconciliation import FIELD_PAIRS, reconcile
from service.source_connectors.contracts import AcquisitionMode, ConnectorRequest
from service.source_connectors.financial_data import FinancialDataConnector
from service.source_connectors.raw_archive import SourceRawArchive


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--symbols', nargs='+', required=True)
    parser.add_argument('--periods', nargs='+', type=date.fromisoformat, required=True)
    parser.add_argument('--as-of', type=date.fromisoformat, required=True)
    parser.add_argument('--probe', action='store_true')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if len(set(args.symbols))>10 or len(set(args.periods))>12:
        parser.error('diagnostic budget: maximum 10 symbols and 12 periods')
    if any((d.month,d.day) not in ((3,31),(6,30),(9,30),(12,31)) for d in args.periods):
        parser.error('closed calendar quarters required')
    if max(args.periods)>args.as_of:
        parser.error('future report period')
    if args.probe:
        payload = {'mode':'data','requests':[
            {'url':route,'params':{'symbols':sorted(set(args.symbols)),
                                  'start_date':min(args.periods).isoformat(),
                                  'end_date':max(args.periods).isoformat()}}
            for route in FIELD_PAIRS]}
        archive = SourceRawArchive(source_id='financial_data', acquisition_mode=AcquisitionMode.QUERY_THROUGH)
        result = FinancialDataConnector(archive=archive).query(ConnectorRequest(
            source_id='financial_data', endpoint_key='common_query',
            acquisition_mode=AcquisitionMode.QUERY_THROUGH, parameters=payload))
        response = result.records[0]
        evidence = archive.archive_response(endpoint_key='financial_reconciliation_probe',
                    parameters=payload, collector_name='financial_reconciliation_probe', records=[response])
    else:
        rows = query("""SELECT payload,record_hash,request_hash,collected_at,request_params
            FROM source_raw_record_store WHERE source_id='financial_data'
            AND endpoint_key='financial_reconciliation_probe' ORDER BY collected_at DESC LIMIT 100""")
        match = None
        for row in rows:
            requests = row['request_params'].get('requests',[])
            matching = {r.get('url') for r in requests
                if set(args.symbols) <= set(r.get('params',{}).get('symbols',[]))
                and r['params'].get('start_date','9999')[:10] <= min(args.periods).isoformat()
                and r['params'].get('end_date','')[:10] >= max(args.periods).isoformat()}
            if set(FIELD_PAIRS) <= matching:
                match = row
                break
        if match is None:
            parser.error('no matching retained evidence; no automatic paid fallback')
        response = match['payload']
        evidence = {k:match[k] for k in ('record_hash','request_hash','collected_at')}
        # Explicit subset selection for a cached superset, not source validation.
        response = json.loads(json.dumps(response))
        from service.source_connectors.financial_data_protocol import tabular_rows
        for result in response['results']:
            if result['url'] in FIELD_PAIRS:
                fields = result['meta']['fields']
                from service.financial_reconciliation import day
                decoded = tabular_rows(match['payload'],route=result['url'])
                result['data'] = [[r.get(f) for f in fields] for r in decoded
                    if r['symbol'] in args.symbols and day(r['report_period']) in args.periods]
    local = {table:query(f"SELECT * FROM {table} WHERE ts_code=ANY(%s) AND end_date=ANY(%s)",
                       (args.symbols,args.periods)) for table in ('income','balancesheet','cashflow')}
    report = reconcile(response,local,symbols=args.symbols,periods=args.periods,cutoff=args.as_of)
    report.update(evidence=evidence,generated_at=datetime.now(timezone.utc).isoformat(),
                  publication='diagnostic only; source rows and factor acceptance unchanged')
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,default=str,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(report['counts'],ensure_ascii=False))


if __name__ == '__main__':
    main()
