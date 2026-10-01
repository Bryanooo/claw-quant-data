-- One runnable V2 instance owns one task/logical-period pair.  Different
-- triggers (daily catch-up, initialization and repair) must converge instead
-- of issuing duplicate upstream requests.
CREATE UNIQUE INDEX IF NOT EXISTS uq_orchestration_v2_active_scope
    ON orchestration_v2.task_execution(task_key, observation_key)
    WHERE status IN (
        'created', 'queued', 'running', 'waiting_dependency', 'retrying',
        'validating', 'publishing'
    );
