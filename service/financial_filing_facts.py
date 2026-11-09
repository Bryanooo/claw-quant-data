"""Conservative read-time recovery of individually verified original facts.

Never rewrites supplier tables/revisions. Never mixes publication versions to
fill holes. A conflicting reviewed fact blocks that field, not silently wins.
"""
from collections import defaultdict
from datetime import timedelta
from decimal import Decimal
import hashlib
import json
import math
import re
from urllib.parse import urlparse

from service.financial_filing_evidence import UNITS
from service.financial_reconciliation import day, number

FACT_FIELDS = {
    'fixed_assets_net_in_note': ('balancesheet', 'fix_assets'),
    'reported_fixed_assets_line': ('balancesheet', 'fix_assets_total'),
    'fin_exp_int_exp': ('income', 'fin_exp_int_exp'),
    'fin_exp_int_inc': ('income', 'fin_exp_int_inc'),
    **{k: ('income', k) for k in ('revenue','oper_cost','sell_exp','admin_exp','fin_exp',
        'biz_tax_surchg','operate_profit','total_profit','income_tax','n_income','n_income_attr_p')},
    **{k: ('cashflow', k) for k in ('depr_fa_coga_dpba', 'amort_intang_assets',
                                  'lt_amort_deferred_exp', 'use_right_asset_dep',
                                  'n_cashflow_act','n_cashflow_inv_act','n_cash_flows_fnc_act',
                                  'c_inf_fr_operate_a','stot_inflows_inv_act','stot_out_inv_act',
                                  'c_paid_to_for_empl')},
    **{k: ('balancesheet', k) for k in ('money_cap','trad_asset','accounts_receiv',
        'prepayment','inventories','total_cur_assets','lt_rec','defer_tax_assets',
        'total_assets','total_cur_liab','total_ncl','total_liab',
        'total_hldr_eqy_inc_min_int','total_hldr_eqy_exc_min_int','minority_int')},
}


def prepare_facts(documents, *, reviewer):
    """Admin-reviewed extraction input; current column only, never comparatives."""
    if not reviewer.strip():
        raise ValueError('reviewer required')
    facts = []
    seen = set()
    for doc in documents:
        period, published = day(doc['period']), day(doc['published_on'])
        if doc['scope'] != 'consolidated' or published < period:
            raise ValueError('unreviewed scope or invalid publication date')
        if not doc.get('review') or doc['unit'] not in UNITS:
            raise ValueError('review and verified unit required')
        declared = {(r['field'], r['page'], r['label']) for r in doc['rows']}
        for row in doc['extracted_facts']:
            if (row['field'], row['page'], row['label']) not in declared or row['unit'] != doc['unit']:
                raise ValueError('extraction differs from reviewed row contract')
            table, field = FACT_FIELDS[row['field']]
            value = number(row['current'])
            if value is None:
                raise ValueError('absent fact is not zero')
            key = (doc['artifact_id'], table, doc['symbol'], period, field)
            if key in seen:
                raise ValueError('duplicate reviewed fact')
            seen.add(key)
            facts.append(dict(artifact_id=doc['artifact_id'], artifact_sha256=doc['sha256'],
                statement_table=table, ts_code=doc['symbol'], end_date=period,
                published_on=published, field_name=field, value_yuan=value,
                page_number=row['page'], row_label=row['label'], original_unit=row['unit'],
                reviewed_by=reviewer, evidence=dict(source_url=doc['url'], title=doc['title'],
                    review=doc['review'], comparison_column_not_imported=True,
                    publication_policy='next_calendar_day_conservative')))
        if len(doc['extracted_facts']) != len(declared):
            raise ValueError('reviewed extraction is incomplete')
    return facts


def original_filing_source(url, publication):
    """Pin the original filing host and date path, including the HTTPS authority."""
    parsed = urlparse(url)
    if parsed.scheme != 'https' or parsed.query or parsed.fragment or parsed.params:
        return None
    day_part = re.escape(str(publication))
    if parsed.netloc == 'static.cninfo.com.cn' and re.fullmatch(
        rf'/finalpage/{day_part}/[0-9]+\.PDF', parsed.path
    ):
        return 'cninfo'
    if parsed.netloc == 'disc.static.szse.cn' and re.fullmatch(
        rf'/download/disc/disk[0-9]+/finalpage/{day_part}/[0-9a-fA-F]{{8}}(?:-[0-9a-fA-F]{{4}}){{3}}-[0-9a-fA-F]{{12}}\.PDF', parsed.path
    ):
        return 'szse'
    return None


def persist_facts(connection, facts):
    """Caller owns transaction; exact replay only, conflicting replay fails."""
    from psycopg2.extras import Json, RealDictCursor
    added = 0
    with connection.cursor(cursor_factory=RealDictCursor) as cur:
        for fact in facts:
            if (fact['statement_table'], fact['field_name']) not in set(FACT_FIELDS.values()):
                raise ValueError('unreviewed filing field mapping')
            cur.execute('SELECT content_hash,inline_content,source_url,source_id,content_type FROM source_raw_artifact '
                        'WHERE artifact_id=%s FOR SHARE', (fact['artifact_id'],))
            artifact = cur.fetchone()
            source = original_filing_source(fact['evidence']['source_url'], fact['published_on'])
            if (not artifact or not artifact['inline_content'] or
                source is None or artifact['source_id'] != source or artifact['content_type'] != 'application/pdf' or
                not bytes(artifact['inline_content']).startswith(b'%PDF-') or
                artifact['content_hash'] != fact['artifact_sha256'] or
                hashlib.sha256(bytes(artifact['inline_content'])).hexdigest() != fact['artifact_sha256'] or
                artifact['source_url'] != fact['evidence']['source_url']):
                raise ValueError('original artifact bytes/hash/url not verified')
            columns = list(fact)
            params = [Json(fact[k]) if k == 'evidence' else fact[k] for k in columns]
            cur.execute(f"INSERT INTO financial_filing_fact ({','.join(columns)}) "
                        f"VALUES ({','.join(['%s']*len(columns))}) ON CONFLICT DO NOTHING RETURNING fact_id", params)
            if cur.fetchone():
                added += 1
            else:
                cur.execute('SELECT * FROM financial_filing_fact WHERE artifact_id=%s AND statement_table=%s '
                            'AND ts_code=%s AND end_date=%s AND field_name=%s',
                            tuple(fact[k] for k in ('artifact_id','statement_table','ts_code','end_date','field_name')))
                old = cur.fetchone()
                if old['revoked_at'] is not None or any(old[k] != v for k, v in fact.items() if k != 'reviewed_by'):
                    raise ValueError('conflicting or revoked fact; do not overwrite reviewed evidence')
    return added


def _missing(value):
    return value is None or (isinstance(value, float) and math.isnan(value))


def recover_rows(rows, facts, *, table, fields, cutoff):
    """All identities are consolidated; outputs retain exact applied fact ids."""
    cutoff = day(cutoff)
    result = {}
    for row in rows:
        key = (row['ts_code'], day(row['end_date']))
        if key in result:
            raise ValueError('duplicate eligible financial statement')
        result[key] = dict(row)
    grouped = defaultdict(list)
    for fact in facts:
        if (fact['statement_table'] == table and
            not fact.get('revoked_at') and day(fact['available_on']) <= cutoff and
            day(fact['published_on']) + timedelta(days=1) <= cutoff):
            grouped[(fact['ts_code'], day(fact['end_date']))].append(fact)
    evidence = []
    for key, candidates in sorted(grouped.items()):
        # A known later publication also invalidates an older projected row
        # when none of the reviewed fields are requested by this caller.
        relevant_fields = {f['field_name'] for f in candidates} & set(fields)
        if not relevant_fields and key not in result:
            continue
        published = max(day(f['published_on']) for f in candidates)
        latest_version = [f for f in candidates if day(f['published_on']) == published]
        latest = [f for f in latest_version if f['field_name'] in fields]
        row = result.get(key)
        if row is not None:
            disclosure = row.get('_disclosure', row.get('ann_date'))
            report_type = row.get('report_type', 1)
            if day(disclosure) is None or published > day(disclosure):
                # A later proven original supersedes this observation. Keep
                # only fields actually proved in the later version, never mix
                # older vendor values into the new partial statement.
                row = None
                result.pop(key, None)
                evidence.append(dict(symbol=key[0], period=str(key[1]), status='older_version_replaced_by_proven_fields',
                                     fact_ids=sorted(f['fact_id'] for f in latest_version)))
            elif day(disclosure) != published or report_type != 1:
                evidence.append(dict(symbol=key[0], period=str(key[1]), status='different_version_not_merged',
                                     fact_ids=sorted(f['fact_id'] for f in latest_version)))
                continue
        if not latest:
            # Projection must not resurrect an older filing when a newer
            # reviewed version only proves fields outside this request.
            evidence.append(dict(symbol=key[0], period=str(key[1]), status='latest_version_field_unproven',
                                 fact_ids=sorted(f['fact_id'] for f in latest_version)))
            continue
        if row is None:
            row = dict(ts_code=key[0], end_date=key[1], ann_date=published,
                       report_type=1, **{field: None for field in fields})
        by_field = defaultdict(list)
        for fact in latest:
            by_field[fact['field_name']].append(fact)
        for field, versions in sorted(by_field.items()):
            values = {number(f['value_yuan']) for f in versions}
            old = row.get(field)
            if len(values) != 1 or (not _missing(old) and abs(number(old)-next(iter(values))) > Decimal('0.01')):
                row[field] = None
                status = 'conflicting_fact_blocked'
            elif _missing(old):
                row[field] = next(iter(values))
                status = 'recovered_from_original'
            else:
                status = 'corroborated'
            evidence.append(dict(symbol=key[0], period=str(key[1]), field=field, status=status,
                                 fact_ids=sorted(f['fact_id'] for f in versions)))
        result[key] = row
    return list(result.values()), evidence
