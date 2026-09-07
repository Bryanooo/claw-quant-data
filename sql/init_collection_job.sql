-- Persistent queue for manually requested collection jobs.
CREATE TABLE IF NOT EXISTS sys_collection_job (
    job_id           BIGSERIAL PRIMARY KEY,
    task_name        VARCHAR(64) NOT NULL,
    parameters       JSONB NOT NULL DEFAULT '{}'::jsonb,
    status           VARCHAR(16) NOT NULL DEFAULT 'queued',
    attempt          SMALLINT NOT NULL DEFAULT 0,
    max_attempts     SMALLINT NOT NULL DEFAULT 3,
    rows_inserted    INTEGER NOT NULL DEFAULT 0,
    rows_fetched     INTEGER,
    api_name         VARCHAR(64),
    cadence          VARCHAR(16),
    period_key       VARCHAR(32),
    expected_for     DATE,
    completion_status VARCHAR(16) NOT NULL DEFAULT 'pending',
    completion_evidence JSONB NOT NULL DEFAULT '{}'::jsonb,
    idempotency_key  VARCHAR(128) UNIQUE,
    parent_job_id    BIGINT REFERENCES sys_collection_job(job_id),
    recheck_of_job_id BIGINT REFERENCES sys_collection_job(job_id),
    recheck_root_job_id BIGINT REFERENCES sys_collection_job(job_id),
    recheck_generation SMALLINT NOT NULL DEFAULT 0,
    worker_id        VARCHAR(128),
    handler_type     VARCHAR(16),
    handler_key      VARCHAR(255),
    handler_version  VARCHAR(32),
    code_revision    VARCHAR(128),
    priority         SMALLINT NOT NULL DEFAULT 50,
    resource_class   VARCHAR(32) NOT NULL DEFAULT 'default',
    job_kind         VARCHAR(16) NOT NULL DEFAULT 'leaf',
    child_total      INTEGER NOT NULL DEFAULT 0,
    child_queued     INTEGER NOT NULL DEFAULT 0,
    child_running    INTEGER NOT NULL DEFAULT 0,
    child_succeeded  INTEGER NOT NULL DEFAULT 0,
    child_failed     INTEGER NOT NULL DEFAULT 0,
    heartbeat_at     TIMESTAMPTZ,
    lease_expires_at TIMESTAMPTZ,
    error_message    TEXT,
    available_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at       TIMESTAMPTZ,
    finished_at      TIMESTAMPTZ,
    CONSTRAINT ck_collection_job_status
        CHECK (status IN ('queued', 'running', 'success', 'failed')),
    CONSTRAINT ck_collection_job_attempts
        CHECK (attempt >= 0 AND max_attempts BETWEEN 1 AND 5),
    CONSTRAINT ck_collection_job_priority CHECK (priority BETWEEN 0 AND 100),
    CONSTRAINT ck_collection_job_recheck_generation
        CHECK (recheck_generation BETWEEN 0 AND 20),
    CONSTRAINT ck_collection_job_kind CHECK (job_kind IN ('leaf', 'batch')),
    CONSTRAINT ck_collection_job_completion_status CHECK (
        completion_status IN (
            'pending', 'running', 'retrying', 'complete', 'empty',
            'verifying', 'unverified', 'incomplete', 'failed'
        )
    ),
    CONSTRAINT ck_collection_job_handler_type CHECK (
        handler_type IS NULL OR handler_type IN ('generic', 'dedicated', 'specialized')
    )
);

CREATE INDEX IF NOT EXISTS idx_collection_job_queue
    ON sys_collection_job(status, available_at, priority DESC, created_at);
CREATE INDEX IF NOT EXISTS idx_collection_job_task
    ON sys_collection_job(task_name, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_collection_job_interface_period
    ON sys_collection_job(api_name, period_key, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_collection_job_expired_lease
    ON sys_collection_job(lease_expires_at)
    WHERE status = 'running';
CREATE INDEX IF NOT EXISTS idx_collection_job_parent
    ON sys_collection_job(parent_job_id, status, job_id)
    WHERE parent_job_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS uq_collection_job_recheck_source
    ON sys_collection_job(recheck_of_job_id)
    WHERE recheck_of_job_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_collection_job_recheck_root
    ON sys_collection_job(recheck_root_job_id, recheck_generation DESC)
    WHERE recheck_root_job_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS sys_collection_schedule_cursor (
    schedule_id          VARCHAR(64) PRIMARY KEY,
    last_dispatched_for  TIMESTAMPTZ NOT NULL,
    last_job_id          BIGINT REFERENCES sys_collection_job(job_id),
    handler_key          VARCHAR(255) NOT NULL,
    handler_version      VARCHAR(32) NOT NULL,
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
