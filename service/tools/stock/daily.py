"""A-share daily market data query helpers."""

from service.db import query


def get_daily(
    ts_code: str,
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[dict]:
    """Return daily bars for one stock in ascending date order."""
    conditions = ["ts_code = %s"]
    params: list[object] = [ts_code]
    if start_date:
        conditions.append("trade_date >= %s")
        params.append(start_date)
    if end_date:
        conditions.append("trade_date <= %s")
        params.append(end_date)
    return query(
        f"SELECT * FROM daily WHERE {' AND '.join(conditions)} ORDER BY trade_date",
        tuple(params),
    )


def get_daily_by_date(
    trade_date: str,
    limit: int = 100,
    offset: int = 0,
) -> list[dict]:
    """Return a page of bars for one trading date."""
    return query(
        """
        SELECT * FROM daily
        WHERE trade_date = %s
        ORDER BY ts_code
        LIMIT %s OFFSET %s
        """,
        (trade_date, limit, offset),
    )
