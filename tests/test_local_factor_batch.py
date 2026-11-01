from datetime import date
from unittest.mock import MagicMock

import pytest

from service.research.local_factors import batch


def test_catalog_sync_does_not_rewrite_unchanged_fk_targets(monkeypatch):
    from service.research.local_factors import materializer

    connection = MagicMock()
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.rowcount = 1
    cursor.fetchone.return_value = (materializer.FACTOR_COUNT,)
    captured = []
    monkeypatch.setattr(
        materializer.psycopg2.extras, "execute_values",
        lambda cur, sql, values, **kwargs: captured.append(sql),
    )
    materializer.sync_factor_catalog(connection)
    assert len(captured) == 1
    assert "IS DISTINCT FROM" in captured[0]
    for field in (
        "factor_name", "factor_family", "formula", "computation_group",
        "overlap_kind", "overlap_dataset", "overlap_field", "convention_note",
    ):
        assert f"local_factor_catalog.{field}" in captured[0]


@pytest.mark.parametrize('partial', [1, 2203])
def test_partial_snapshot_cannot_be_reused_as_certified(monkeypatch, partial):
    from service.research.local_factors import materializer

    connection = MagicMock()
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.fetchone.return_value = (5577, 5577, True, 3367, partial, 272, 32, 4600)
    monkeypatch.setattr(materializer, 'get_conn', lambda: connection)
    assert materializer._reuse_certified_snapshot(
        date(2026, 10, 29), source_execution_id=123,
    ) is None
    assert cursor.execute.call_count == 1
    connection.commit.assert_not_called()
    connection.close.assert_called_once()


def test_batch_is_resumable_and_deduplicates_dates(monkeypatch):
    days = [date(2026, 10, 9), date(2026, 10, 8), date(2026, 10, 9)]
    monkeypatch.setattr(batch, "published_dates", lambda dates: {date(2026, 10, 8)})
    monkeypatch.setattr(batch, "_sync_catalog_once", lambda: None)
    calls = []

    def materialize(day):
        calls.append(day)
        return {"snapshot_date": day.isoformat(), "data_ready": True}

    monkeypatch.setattr(batch, "_materialize_one", materialize)
    result = batch.materialize_factor_batch(days)
    assert calls == [date(2026, 10, 9)]
    assert result["skipped_complete_dates"] == ["2026-10-08"]
    assert result["completed_dates"] == ["2026-10-09"]
    assert result["failed_dates"] == {}


def test_batch_keeps_success_and_reports_individual_failure(monkeypatch):
    monkeypatch.setattr(batch, "published_dates", lambda dates: set())
    monkeypatch.setattr(batch, "_sync_catalog_once", lambda: None)

    def materialize(day):
        if day.day == 9:
            raise RuntimeError("broken input")
        return {"snapshot_date": day.isoformat(), "data_ready": True}

    monkeypatch.setattr(batch, "_materialize_one", materialize)
    result = batch.materialize_factor_batch(
        [date(2026, 10, 8), date(2026, 10, 9)], force=False,
    )
    assert result["completed_dates"] == ["2026-10-08"]
    assert result["failed_dates"] == {"2026-10-09": "RuntimeError: broken input"}


@pytest.mark.parametrize('result', [{'data_ready': False}, {}])
def test_batch_does_not_report_partial_or_unknown_as_completed(monkeypatch, result):
    monkeypatch.setattr(batch, 'published_dates', lambda dates: set())
    monkeypatch.setattr(batch, '_sync_catalog_once', lambda: None)
    monkeypatch.setattr(batch, '_materialize_one', lambda day: result)
    events = []
    output = batch.materialize_factor_batch([date(2026, 10, 29)], progress=events.append)
    assert output['completed_dates'] == []
    assert output['partial_dates'] == ['2026-10-29']
    assert events[-1]['event'] == 'date_partial'


def test_operational_batch_creates_one_v2_execution_per_date(monkeypatch):
    from service.orchestration_v2 import gap_repair, repository

    captured = {}

    def create_repair_executions(**kwargs):
        captured.update(kwargs)
        return {"selected": len(kwargs["proposals"]), "created": 2, "existing": 0}

    sentinel_repository = object()
    monkeypatch.setattr(gap_repair, "create_repair_executions", create_repair_executions)
    monkeypatch.setattr(repository, "OrchestrationV2Repository", lambda: sentinel_repository)
    result = batch.enqueue_factor_batch(
        [date(2026, 10, 9), date(2026, 10, 8), date(2026, 10, 9)]
    )

    assert result["mode"] == "v2_control_plane"
    assert result["requested_dates"] == ["2026-10-08", "2026-10-09"]
    assert captured["repository"] is sentinel_repository
    assert captured["purpose"] == "backfill"
    assert captured["frozen_scope_extra"]["historical_source_validation"] == "transform_owned"
    assert [item.observation_key for item in captured["proposals"]] == [
        "2026-10-08", "2026-10-09"
    ]
