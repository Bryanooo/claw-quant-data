"""Exact security/date obligations; missing rows are never supplier exemptions."""

def audit_security_dates(cursor, start_date, end_date):
    # Indexed existence probes avoid multiplying each daily bar by hundreds of
    # price bins. The daily universe is lifecycle-valid, not today's stock list.
    cursor.execute("""
        WITH checked AS MATERIALIZED (
            SELECT d.trade_date,d.ts_code,
                   EXISTS(SELECT 1 FROM cyq_chips x
                     WHERE x.ts_code=d.ts_code AND x.trade_date=d.trade_date) AS present
            FROM daily d
            JOIN stock_basic s USING(ts_code)
            WHERE d.trade_date BETWEEN %s AND %s
              AND NULLIF(s.list_date,'') IS NOT NULL
              AND d.trade_date >= to_date(s.list_date,'YYYYMMDD')
              AND (NULLIF(s.delist_date,'') IS NULL
                   OR d.trade_date <= to_date(s.delist_date,'YYYYMMDD'))
        )
        SELECT c.cal_date AS trade_date, count(d.ts_code) AS expected,
               count(d.ts_code) FILTER (WHERE d.present) AS present,
               coalesce(array_agg(d.ts_code ORDER BY d.ts_code)
                 FILTER (WHERE d.ts_code IS NOT NULL AND NOT d.present),
                 ARRAY[]::varchar[]) AS missing_codes
        FROM trade_cal c
        LEFT JOIN checked d ON d.trade_date=c.cal_date
        WHERE c.exchange='SSE' AND c.is_open=1 AND c.cal_date BETWEEN %s AND %s
        GROUP BY c.cal_date ORDER BY c.cal_date
    """, (start_date, end_date, start_date, end_date))
    return [dict(row) for row in cursor.fetchall()]


def summarize_day(row):
    return {
        'trade_date': str(row['trade_date']),
        'expected': row['expected'], 'present': row['present'],
        'missing_codes': list(row['missing_codes']),
        'status': ('baseline_unverified' if not row['expected'] else
                   'missing' if row['missing_codes'] else 'security_presence_verified'),
        'missing_reason': 'not_collected_or_provider_unconfirmed',
        'provider_unavailable_confirmed': [],
        'limitations': 'Presence does not prove exhaustive price bins; daily baseline must also be audited.',
    }
