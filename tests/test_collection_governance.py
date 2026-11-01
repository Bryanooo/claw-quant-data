from datetime import datetime
from pathlib import Path
from unittest.mock import Mock
from zoneinfo import ZoneInfo

import pytest

from service.orchestration_v2 import runtime


def test_running_history_yields_without_transport_or_retry_cost(monkeypatch):
    now = datetime(2026, 10, 30, 9, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    resume = now.replace(hour=16)
    monkeypatch.setattr(runtime, "business_now", lambda: now)
    gate = Mock(return_value=resume)
    monkeypatch.setattr(runtime, "historical_resume_at", gate)
    with pytest.raises(runtime.HistoricalWindowDeferred) as captured:
        runtime.check_history_window({"purpose":"repair", "resource_class":"v2-backfill"})
    assert captured.value.defer_without_failure is True
    assert captured.value.retry_after_seconds == 7 * 3600
    gate.assert_called_once_with("repair",resource_class="v2-backfill",now=now)


def test_routine_request_not_blocked_by_history_window(monkeypatch):
    monkeypatch.setattr(runtime,"historical_resume_at",lambda *a,**kw:None)
    runtime.check_history_window({"purpose":"daily", "resource_class":"market"})


def test_restore_stops_actual_topology_and_refuses_remaining_clients():
    source=(Path(__file__).resolve().parents[1]/"scripts/restore.sh").read_text()
    assert 'ps --status running --services' in source
    assert 'stop -t 3600 "${RUNNING_SERVICES[@]}"' in source
    assert '"${ACTIVE_CONNECTIONS}" != "0"' in source
    assert source.index('"${ACTIVE_CONNECTIONS}" != "0"') < source.index('pg_restore -U')
    assert 'up -d --no-deps "${RUNNING_SERVICES[@]}"' in source


def test_lineage_preserves_task_and_data_state_and_redacts_credentials():
    from service.api.routers.operations import task_relationships
    repository=Mock()
    repository.get_definition.return_value={"task_key":"daily", "definition":{"acquisition_endpoint_ids":[1]}}
    repository.get_endpoint.return_value={"source_id":"tushare","endpoint_key":"daily","credential_ref":"secret", "request_contract":{"token":"secret"}}
    repository.list_executions.return_value=[{"task_execution_id":9,"status":"success"}]
    repository.execution_output_states.return_value=[{"source_execution_id":9,"ready":False,"data_status":"partial"}]
    result=task_relationships(1,repository)
    assert result["recent_executions"][0]["status"]=="success"
    assert result["published_states"][0]["ready"] is False
    assert "secret" not in str(result)
    repository.execution_output_states.assert_called_once_with([9])


def test_full_coverage_dispatch_runs_outside_opening_hours():
    from collectors.scheduler import create_scheduler
    scheduler=create_scheduler(set_active=False)
    job=scheduler.get_job("v2_coverage_dispatch")
    assert "hour='20'" in str(job.trigger)
