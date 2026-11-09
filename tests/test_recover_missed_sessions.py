from datetime import date
from types import SimpleNamespace
from scripts.recover_missed_sessions import dated_request
from service.history_baselines import generic_policy_history_partitions


def test_recovery_requires_an_exact_period():
    day = date(2026, 11, 6)

    def allowed(**params):
        return dated_request(SimpleNamespace(parameters={"parameters": params}), day)

    assert allowed(trade_date="20261106")
    assert allowed(start_date="2026-11-06", end_date="2026-11-06")
    assert not allowed(start_date="20261101", end_date="20261106")
    assert not allowed(ts_code="000001.SZ")


def test_marketwide_futures_history_uses_exact_date():
    day = date(2026, 11, 6)
    keys = {"fut_settle", "fut_wsr"}
    scopes = {
        p.api_name: p.parameters
        for p in generic_policy_history_partitions(day, day, trade_dates=[day])
        if p.api_name in keys
    }
    assert scopes == {k: {"trade_date": "20261106"} for k in keys}
