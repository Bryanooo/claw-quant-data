"""Financial source comparison, never a write-through or PIT certification.

Compare only reviewed monetary A-share field pairs. A matching current value
does not establish historical availability, independence of vendors, or equal
consolidation scope. Keep those qualifications alongside every result.
"""
from collections import Counter, defaultdict
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from service.source_connectors.financial_data_protocol import tabular_rows

BALANCE_ROUTE = '/api/v1/stock_fnd/balance-sheet'
FLOW_ROUTE = '/api/v1/stock_fnd/income-cashflow-acc'
TTM_ROUTE = '/api/v1/stock_fnd/metrics-ttm'
FIELD_PAIRS = {
    BALANCE_ROUTE: {
        'total_assets': ('balancesheet', 'total_assets'),
        'total_liab': ('balancesheet', 'total_liab'),
        'total_equity': ('balancesheet', 'total_hldr_eqy_inc_min_int'),
        'fix_assets': ('balancesheet', 'fix_assets'),
        'total_fixed_assets': ('balancesheet', 'fix_assets_total'),
    },
    FLOW_ROUTE: {
        'operating_revenue': ('income', 'revenue'),
        'net_profit': ('income', 'n_income'),
        'npoc': ('income', 'n_income_attr_p'),
        'total_profit': ('income', 'total_profit'),
        'cfo_net': ('cashflow', 'n_cashflow_act'),
        'cfi_net': ('cashflow', 'n_cashflow_inv_act'),
        'cff_net': ('cashflow', 'n_cash_flows_fnc_act'),
    },
}


def day(value):
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if not value:
        return None
    value = str(value)
    return datetime.strptime(value, '%Y%m%d').date() if len(value) == 8 else date.fromisoformat(value[:10])


def number(value):
    if value is None:
        return None
    result = Decimal(str(value))
    if not result.is_finite():
        raise ValueError('non-finite financial value')
    return result


def numeric_status(local, provider, unit, *, absolute_tolerance=Decimal('0.01')):
    """No relative tolerance: a small percentage of a huge balance is material."""
    try:
        a, b = number(local), number(provider)
    except (ValueError, InvalidOperation):
        return 'invalid_number'
    if a is None and b is None:
        return 'both_missing'
    if b is None:
        return 'provider_missing'
    if unit != '人民币元':
        return 'unit_unverified'
    if a is None:
        return 'local_missing_candidate'
    return 'value_agreement' if abs(a-b) <= absolute_tolerance else 'value_mismatch'


def reconcile(response, local_rows, *, symbols, periods, cutoff):
    """Full requested grid, including absent rows; duplicates never pick a winner."""
    periods = {day(p) for p in periods}
    symbols = set(symbols)
    if not symbols or not periods or any(not s.endswith(('.SZ', '.SH', '.BJ')) for s in symbols):
        raise ValueError('explicit A-share symbols and report periods required')
    cutoff = day(cutoff)
    local = defaultdict(list)
    for table, rows in local_rows.items():
        for row in rows:
            # Non-consolidated statements are not comparable candidates.
            if str(row.get('report_type')) == '1':
                local[(table, row['ts_code'], day(row['end_date']))].append(row)
    results = []
    for route, fields in FIELD_PAIRS.items():
        rows = tabular_rows(response, route=route)
        meta = next(r['meta'] for r in response['results'] if r['url'] == route)
        units = meta.get('unit') or {}
        if not isinstance(units, dict):
            units = {}
        provider = defaultdict(list)
        for row in rows:
            symbol, period = row.get('symbol'), day(row.get('report_period'))
            if symbol not in symbols or period not in periods:
                raise ValueError('unrequested security or report period')
            actual_end = day(row.get('report_period_end'))
            if actual_end != period:
                raise ValueError('actual report end differs or is absent')
            provider[(symbol, period)].append(row)
        for symbol in sorted(symbols):
            for period in sorted(periods):
                upstream = provider[(symbol, period)]
                for field, (table, column) in fields.items():
                    stored = local[(table, symbol, period)]
                    item = dict(symbol=symbol, period=period.isoformat(), route=route,
                                table=table, field=column, provider_field=field,
                                pit_certified=False, scope_equivalence='requires_contract_review')
                    if len(upstream)>1 or len(stored)>1:
                        item['status'] = 'duplicate_identity'
                    elif not upstream:
                        item['status'] = 'provider_row_missing'
                    else:
                        ant, ts = upstream[0], stored[0] if stored else {}
                        value, other = ts.get(column), ant.get(field)
                        item.update(local_value=value, provider_value=other, unit=units.get(field))
                        item['status'] = numeric_status(value, other, units.get(field))
                        disclosed = day(ant.get('disclosure_date'))
                        ts_dates = [day(ts.get(k)) for k in ('ann_date','f_ann_date') if ts.get(k)]
                        local_disclosed = max(ts_dates) if ts_dates else None
                        item.update(provider_disclosure=disclosed, local_disclosure=local_disclosed)
                        item['version_status'] = (
                            'publication_unknown' if disclosed is None or local_disclosed is None else
                            'after_cutoff' if max(disclosed,local_disclosed)>cutoff else
                            'disclosure_mismatch' if disclosed != local_disclosed else
                            'same_disclosure_not_revision_proof')
                    results.append(item)
    return dict(policy='comparison_only_no_promotion', cutoff=cutoff,
                counts=dict(Counter(r['status'] for r in results)), results=results)


def ebitda_bridge(income, cashflow):
    """Two explicitly named hypotheses; never replace provider income.ebitda.

    Missing components stay missing, including right-of-use depreciation.
    Caller must supply one security/period and equal disclosure versions.
    """
    identity = ('ts_code','end_date','ann_date','f_ann_date','report_type')
    if any(income.get(k) is None or income.get(k) != cashflow.get(k) for k in identity):
        return {'status':'statement_identity_mismatch'}
    names = ('depr_fa_coga_dpba','amort_intang_assets','lt_amort_deferred_exp','use_right_asset_dep')
    missing = [k for k in names if cashflow.get(k) is None]
    missing += [k for k in ('total_profit','fin_exp_int_exp','fin_exp_int_inc') if income.get(k) is None]
    if missing:
        return {'status':'missing_components','missing':missing}
    daa = sum(number(cashflow[k]) for k in names)
    gross = number(income['total_profit']) + number(income['fin_exp_int_exp'])
    net = gross-number(income['fin_exp_int_inc'])
    return dict(status='diagnostic_not_official_formula', depreciation_amortization=daa,
                ebit_gross_interest=gross, ebit_net_interest=net,
                ebitda_gross_interest=gross+daa, ebitda_net_interest=net+daa)
