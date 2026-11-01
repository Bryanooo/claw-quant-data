from datetime import date, datetime, time, timedelta, timezone

import pytest

from service.intraday.collector import INDEX_PROXIES, PROXIES
from service.intraday.replay import replay_day
from scripts.backfill_intraday_observation import _provider_batches


CST = timezone(timedelta(hours=8))


def test_provider_batches_pair_only_adjacent_calendar_days():
    days = [
        date(2026, 10, 16), date(2026, 10, 19), date(2026, 10, 20),
        date(2026, 10, 21), date(2026, 10, 22),
    ]

    assert _provider_batches(days) == [
        [date(2026, 10, 16)],
        [date(2026, 10, 19), date(2026, 10, 20)],
        [date(2026, 10, 21), date(2026, 10, 22)],
    ]


def _bar(symbol, name, at, close, previous_close, scope):
    return {
        "symbol": symbol, "name": name,
        "bar_time": datetime.combine(date(2026, 10, 22), at, tzinfo=CST),
        "scope_type": scope, "open": close, "high": close,
        "low": close, "close": close, "previous_close": previous_close,
        "volume": 1, "amount": close,
    }


def test_replay_uses_day_previous_close_and_classifies_downtrend():
    rows = []
    for symbol, name in PROXIES.items():
        rows.extend([
            _bar(symbol, name, time(9, 30), 99, 100, "etf"),
            _bar(symbol, name, time(15, 0), 97, 99, "etf"),
        ])
    rows.extend([
        _bar("399001.SZ", INDEX_PROXIES["399001.SZ"], time(9, 30), 99, 100, "index"),
        _bar("399001.SZ", INDEX_PROXIES["399001.SZ"], time(15, 0), 98, 99, "index"),
        _bar("811100.CNS", "农林牧渔", time(9, 30), 99, 100, "industry"),
        _bar("811100.CNS", "农林牧渔", time(15, 0), 97, 99, "industry"),
        _bar("600111.SH", "北方稀土", time(9, 30), 99, 100, "stock"),
        _bar("600111.SH", "北方稀土", time(15, 0), 96, 99, "stock"),
    ])
    result = replay_day({
        "day": date(2026, 10, 22), "quote_rows": rows,
        "flow_source": [], "flow_rows": [],
        "industry_symbols": {"811100.CNS"}, "watch_symbols": {"600111.SH"},
        "expected_proxies": 4, "expected_sectors": 1,
    })

    close = result[-1]["analyses"]
    market = next(item for item in close if item["scope_type"] == "market")
    stock = next(item for item in close if item["scope_type"] == "stock")
    index = next(item for item in close if item["scope_type"] == "index")
    assert market["state"] == "strong_downtrend"
    assert market["metrics"]["proxy_median_pct"] == pytest.approx(-3)
    assert stock["state"] == "strong_downtrend"
    assert index["state"] == "downtrend"
