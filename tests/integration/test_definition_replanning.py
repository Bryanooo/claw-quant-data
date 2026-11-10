"""Real PostgreSQL identity regression; every fixture is rolled back."""
from contextlib import contextmanager
from datetime import date
import os
from uuid import uuid4

import pytest

from service.db import get_conn
from service.orchestration_v2.contracts import ExecutionRequest, TaskDefinitionDocument
from service.orchestration_v2.repository import OrchestrationV2Repository
from tests.test_orchestration_v2 import acquisition_definition

pytestmark = pytest.mark.skipif(os.getenv('RUN_DB_INTEGRATION') != '1', reason='isolated PostgreSQL required')


@pytest.mark.parametrize('status,category,should_replan', [
    ('superseded', 'audit_contract_superseded', True),
    ('superseded', 'definition_superseded', True),
    ('superseded', 'research_scope_paused', False),
    ('cancelled', 'user_cancelled', False),
])
def test_replaced_definition_replans_once_without_reviving_operator_stops(monkeypatch, status, category, should_replan):
    conn = get_conn()
    repo = OrchestrationV2Repository()
    @contextmanager
    def connection(): yield conn
    monkeypatch.setattr(repo, '_connection', connection)
    try:
        document = TaskDefinitionDocument.model_validate(acquisition_definition(task_key='replan_'+uuid4().hex))
        first = repo.create_definition_draft(document, actor='integration')
        repo.publish_definition(first['task_definition_id'], actor='integration', app_revision='fixture', image_digest='fixture')
        request = ExecutionRequest(task_key=document.task_key, purpose='daily', trigger_source='schedule',
            idempotency_key='fixture:'+uuid4().hex, observation_key='2026-11-09',
            observation_start=date(2026, 11, 9), observation_end=date(2026, 11, 9))
        original, created = repo.create_execution(request)
        assert created
        with conn.cursor() as cursor:
            cursor.execute("UPDATE orchestration_v2.task_execution SET status=%s,final_error_category=%s,finished_at=now() WHERE task_execution_id=%s",
                           (status, category, original['task_execution_id']))
        changed = document.model_copy(update={'resource': document.resource.model_copy(update={'priority': 91})})
        second = repo.create_definition_draft(changed, actor='integration')
        repo.publish_definition(second['task_definition_id'], actor='integration', app_revision='fixture2', image_digest='fixture2')
        replacement, created = repo.create_execution(request)
        assert created is should_replan
        repeated, created_again = repo.create_execution(request)
        assert not created_again
        assert repeated['task_execution_id'] == replacement['task_execution_id']
        if should_replan:
            assert replacement['task_definition_id'] == second['task_definition_id']
            assert replacement['task_execution_id'] != original['task_execution_id']
            assert replacement['idempotency_key'] != original['idempotency_key']
        else:
            assert replacement['task_execution_id'] == original['task_execution_id']
        with conn.cursor() as cursor:
            cursor.execute('SELECT status,idempotency_key FROM orchestration_v2.task_execution WHERE task_execution_id=%s',
                           (original['task_execution_id'],))
            assert cursor.fetchone() == (status, request.idempotency_key)
    finally:
        conn.rollback()
        conn.close()
