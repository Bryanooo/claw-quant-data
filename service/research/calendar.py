"""Trading-session gate: absence is unknown, never a closed exchange."""
from datetime import date, datetime, timezone

def session_from_rows(day: date, exchange: str, rows: list[dict]) -> dict:
    key = day.strftime('%Y%m%d')
    row = next((r for r in rows if r['cal_date'] == key), None)
    known = row is not None and row.get('is_open') in (0, 1)
    previous = row.get('pretrade_date') if row else None
    iso = lambda value: f'{value[:4]}-{value[4:6]}-{value[6:]}' if value else None
    return {'data': {'trading_date': day.isoformat(), 'exchange': exchange,
                     'status': 'known' if known else 'unknown',
                     'is_open': bool(row['is_open']) if known else None,
                     'previous_trading_date': iso(previous),
                     'market_timezone': 'Asia/Shanghai',
                     'session_open_at': day.isoformat()+'T09:30:00+08:00' if known and row['is_open'] else None},
            'meta': {'dataset': 'trade_calendar', 'generated_at': datetime.now(timezone.utc).isoformat(),
                     'limitation': 'SSE/SZSE equity sessions only; missing coverage is unknown'}}
