"""One reproducible sample contract for reference collection and comparison.

Plans do not perform provider requests or certify whole-market completeness.
Sampling is anchored to committed local snapshots, never the current universe.
"""
from datetime import date, timedelta

from service.db import query
from .catalog import FACTOR_SCHEMA_VERSION, FACTOR_SPECS

SAMPLE_SIZE = 128
FIXED_SIZE = 32
SAMPLE_METHOD = 'fixed32_rotating96_md5_v1'

# The provider truncates any single response at 6,000 rows and a truncated
# response is indistinguishable from a complete one, so a request must stay
# strictly below the cap. One security-day costs one row per catalogued
# factor, which is what makes a per-security request windowable at all: the
# whole-market task cannot batch days because a single factor-day already
# returns the entire universe. Two sessions of reserve absorb catalogue
# growth, so widening the factor set shrinks the window instead of producing
# silent truncation.
PROVIDER_ROW_CAP = 6_000
MAX_WINDOW_DAYS = max(1, PROVIDER_ROW_CAP // max(len(FACTOR_SPECS), 1) - 2)

# Four parameters match the comparison query's sample CTE contract.
SAMPLE_CODES_SQL = """
SELECT ts_code FROM (
    SELECT ts_code, row_number() OVER (
        ORDER BY md5('factor-reference-fixed-v1:' || ts_code), ts_code
    ) AS fixed_rank
    FROM local_factor_snapshot
    WHERE schema_version=%s AND trade_date=%s
) universe
ORDER BY CASE WHEN fixed_rank <= 32 THEN 0 ELSE 1 END,
         CASE WHEN fixed_rank <= 32 THEN fixed_rank END,
         md5(%s || ':' || ts_code), ts_code
LIMIT %s
"""


def window_trade_dates(day: date, window_days: int = 1) -> list[date]:
    """Trading days ending at ``day``, oldest first.

    A window is counted in sessions rather than calendar days because a
    non-session contributes no rows and would silently shrink the batch.
    """
    span = max(1, min(int(window_days), MAX_WINDOW_DAYS))
    rows = query(
        """SELECT cal_date FROM trade_cal
           WHERE exchange='SSE' AND is_open=1 AND cal_date BETWEEN %s AND %s
           ORDER BY cal_date""",
        (day - timedelta(days=span * 3 + 10), day),
    )
    days = [row['cal_date'] for row in rows if row.get('cal_date')]
    return days[-span:] or [day]


def reference_sample_plan(day: date, *, window_days: int = 1) -> dict:
    """Read-only preview. Empty/missing calendars never permit remote calls.

    ``window_days`` batches several sessions into one request per security.
    The sample is drawn once from the window's latest snapshot and reused for
    every session, which is what holds the cost at one call per security per
    window instead of one call per security per day.
    """
    calendar = query(
        "SELECT is_open FROM trade_cal WHERE exchange='SSE' AND cal_date=%s",
        (day,),
    )
    if len(calendar) != 1:
        return {'date': day.isoformat(), 'status': 'calendar_missing', 'requests': []}
    if not calendar[0]['is_open']:
        return {'date': day.isoformat(), 'status': 'closed', 'requests': []}
    days = window_trade_dates(day, window_days)
    if days[-1] != day:
        return {'date': day.isoformat(), 'status': 'calendar_missing', 'requests': []}
    codes = [row['ts_code'] for row in query(
        SAMPLE_CODES_SQL, (FACTOR_SCHEMA_VERSION, day, day.isoformat(), SAMPLE_SIZE),
    )]
    # A single session keeps the exact-date request the contract was probed
    # with; only a real window switches to the range form.
    window = ({'trade_date': day.strftime('%Y%m%d')} if len(days) == 1 else
              {'start_date': days[0].strftime('%Y%m%d'),
               'end_date': days[-1].strftime('%Y%m%d')})
    planned = len(codes) >= 30
    return {
        'date': day.isoformat(),
        'start_date': days[0].isoformat(),
        'end_date': days[-1].isoformat(),
        'trade_dates': [item.isoformat() for item in days],
        'window_days': len(days),
        'max_window_days': MAX_WINDOW_DAYS,
        'estimated_calls': len(codes) if planned else 0,
        'status': 'planned' if planned else 'local_sample_insufficient',
        'sample_method': SAMPLE_METHOD,
        'sample_seed': day.isoformat(),
        'scope': 'reference_sample_only',
        'securities': codes,
        'requests': [
            dict(ts_code=code, **window) for code in codes
        ] if planned else [],
        'provider_contract_probe_required': True,
        'whole_market_certified': False,
    }
