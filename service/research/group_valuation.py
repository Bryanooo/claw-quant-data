"""Same-date cross-sectional descriptions, not supplier index valuations.

No imputation, winsorisation, or reconstruction of missing earnings is allowed.
"""

from bisect import bisect_left, bisect_right
from math import isfinite
from statistics import mean, median


def number(value):
    try:
        result = float(value)
        return result if isfinite(result) else None
    except (ValueError, TypeError, OverflowError):
        return None


def quantile(values, fraction):
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def distribution(values):
    """Finite samples only; retain negatives for financial ratios."""
    return {key: quantile(values, fraction) if values else None
            for key, fraction in (('p10', .1), ('p25', .25), ('p75', .75), ('p90', .9))}


def summarize_financials(members, rows, report_period, as_of):
    observed = {r['ts_code']: r for r in rows if r['ts_code'] in members
                and str(r.get('end_date')) == str(report_period)
                and r.get('ann_date') is not None and str(r['ann_date']) <= str(as_of)}
    metrics = {}
    for field in ('roe', 'roic', 'grossprofit_margin', 'netprofit_margin', 'debt_to_assets'):
        valid = {c: v for c in members
                 if (v := number(observed.get(c, {}).get(field))) is not None}
        values = list(valid.values())
        metrics[field] = {
            **distribution(values), 'mean': mean(values) if values else None,
            'median': median(values) if values else None, 'valid_count': len(values),
            'coverage_pct': 100 * len(values) / len(members) if members else 0,
            'missing_codes': sorted(set(members) - valid.keys()),
            'positive_count': sum(v > 0 for v in values),
            'negative_count': sum(v < 0 for v in values),
        }
    return {'report_period': report_period, 'members': len(members),
            'disclosed_members': len(observed), 'metrics': metrics,
            'methodology': 'same report period; announced by requested date; negative ratios retained; no annualization'}


def aggregate_valuation(members, rows):
    result = {}
    for key, field in (('pe_ttm', 'net_income_ttm'), ('pb', 'parent_equity')):
        pairs = {}
        for row in rows:
            cap, denominator = number(row.get('total_mv')), number(row.get(field))
            if row['ts_code'] in members and cap is not None and cap > 0 and denominator is not None:
                pairs[row['ts_code']] = (cap * 10000, denominator)
        cap_sum = sum(pair[0] for pair in pairs.values())
        denominator_sum = sum(pair[1] for pair in pairs.values())
        result[key] = {
            'value': cap_sum / denominator_sum if denominator_sum > 0 else None,
            'status': 'computed' if len(pairs) == len(members) and denominator_sum > 0 else 'partial' if denominator_sum > 0 else 'nonpositive_or_missing_denominator',
            'matched_members': len(pairs), 'missing_codes': sorted(set(members) - pairs.keys()),
            'market_cap_yuan': cap_sum, 'denominator_yuan': denominator_sum,
            'negative_denominator_members': sum(pair[1] < 0 for pair in pairs.values()),
            'zero_denominator_members': sum(pair[1] == 0 for pair in pairs.values()),
            'methodology': 'ratio of sums on matched securities; negative and zero denominators included; not mean of ratios',
        }
    return result


def summarize_valuation(members, rows, trade_date):
    """Members: code -> optional index weight; only exact-date rows qualify."""
    observed = {r['ts_code']: r for r in rows if r['ts_code'] in members
                and str(r.get('trade_date')) == str(trade_date)}
    metrics = {}
    for field in ('pe', 'pe_ttm', 'pb', 'ps_ttm', 'dv_ttm'):
        valid, missing, excluded = {}, [], []
        for code in members:
            value = number(observed.get(code, {}).get(field))
            if value is None:
                missing.append(code)
            elif value < 0 or (field != 'dv_ttm' and value == 0):
                excluded.append(code)
            else:
                valid[code] = value
        values = list(valid.values())
        item = {'valid_count': len(values), 'missing_codes': missing,
                'nonpositive_excluded_codes': excluded,
                'coverage_pct': 100 * len(values) / len(members) if members else 0,
                'mean': mean(values) if values else None,
                'median': median(values) if values else None,
                'p25': quantile(values, .25) if values else None,
                'p75': quantile(values, .75) if values else None,
                'min': min(values) if values else None,
                'max': max(values) if values else None}
        item.update(distribution(values))
        iqr = item['p75'] - item['p25'] if values else None
        item['iqr'] = iqr
        item['outliers'] = [
            {'ts_code': c, 'value': v}
            for c, v in sorted(valid.items(), key=lambda pair: (-pair[1], pair[0]))
            if v < item['p25'] - 1.5 * iqr or v > item['p75'] + 1.5 * iqr
        ] if values else []
        item['outlier_method'] = 'Tukey 1.5 IQR; flagged, never removed'
        ordered = sorted(values)
        item['member_percentiles'] = {
            c: 50 * (bisect_left(ordered, v) + bisect_right(ordered, v)) / len(values)
            for c, v in valid.items()
        }
        item['percentile_method'] = 'midrank: (less + 0.5 * equal) / valid_count * 100'
        for name, weights in (
            ('market_cap', {c: number(observed.get(c, {}).get('total_mv')) for c in valid}),
            ('index', {c: number(members[c]) for c in valid}),
        ):
            weights = {c: w for c, w in weights.items() if w is not None and w > 0}
            denominator = sum(weights.values())
            item[name + '_weighted_mean'] = (
                sum(valid[c] * w for c, w in weights.items()) / denominator
                if denominator else None)
            item[name + '_weighted_count'] = len(weights)
            item[name + '_weight_sum'] = denominator
        metrics[field] = item
    caps = sorted((v for r in observed.values()
                   if (v := number(r.get('total_mv'))) is not None and v > 0), reverse=True)
    cap_sum = sum(caps)
    return {'members': len(members), 'observed_members': len(observed),
            'missing_codes': sorted(set(members) - observed.keys()),
            'metrics': metrics,
            'concentration': {'covered_members': len(caps),
                              'total_market_value_wan': cap_sum if caps else None,
                              'top10_market_cap_share_pct': 100 * sum(caps[:10]) / cap_sum if cap_sum else None,
                              'market_cap_hhi': sum((v / cap_sum) ** 2 for v in caps) if cap_sum else None},
            'positive_pe_ttm_coverage_pct': metrics['pe_ttm']['coverage_pct']}
