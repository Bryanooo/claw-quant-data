from datetime import date

import scripts.queue_catalog_history_repair as repair
from service.history_baselines import catalog_history_partitions


def _row(key, **overrides):
    value = {
        "period_key": key,
        "status": "success",
        "completion_status": "complete",
        "completion_evidence": {"verified": True},
    }
    value.update(overrides)
    return value


def test_catalog_history_audit_requires_every_verified_partition(monkeypatch):
    start = date(2026, 1, 1)
    end = date(2026, 1, 31)
    keys = [item.key for item in catalog_history_partitions(start, end)]
    rows = [_row(key) for key in keys]
    monkeypatch.setattr(repair, "query", lambda *_args, **_kwargs: rows)

    result = repair.audit_repairs(start, end)

    assert result["complete"] is True
    assert result["expected"] == len(keys)
    assert result["observed"] == len(keys)


def test_catalog_history_audit_rejects_missing_active_failed_and_unverified(monkeypatch):
    start = date(2026, 1, 1)
    end = date(2026, 1, 31)
    keys = [item.key for item in catalog_history_partitions(start, end)]
    rows = [_row(key) for key in keys[4:]]
    rows.extend(
        (
            _row(keys[1], status="running", completion_status="running"),
            _row(keys[2], status="failed", completion_status="failed"),
            _row(keys[3], completion_status="complete", completion_evidence={}),
        )
    )
    monkeypatch.setattr(repair, "query", lambda *_args, **_kwargs: rows)

    result = repair.audit_repairs(start, end)

    assert result["complete"] is False
    assert result["missing"] == [keys[0]]
    assert result["active"] == [keys[1]]
    assert result["failed"] == [keys[2]]
    assert result["unverified"] == [keys[3]]
