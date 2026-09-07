-- Persist logical collector routing and recover worker failures continuously.

ALTER TABLE sys_collection_job
    ALTER COLUMN max_attempts SET DEFAULT 3,
    ADD COLUMN IF NOT EXISTS handler_type VARCHAR(16),
    ADD COLUMN IF NOT EXISTS handler_key VARCHAR(255),
    ADD COLUMN IF NOT EXISTS handler_version VARCHAR(32),
    ADD COLUMN IF NOT EXISTS code_revision VARCHAR(128),
    ADD COLUMN IF NOT EXISTS heartbeat_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS lease_expires_at TIMESTAMPTZ;

-- Existing queued rows intentionally remain without a handler snapshot and
-- are treated as legacy-compatible. Every newly submitted row is snapshotted.

ALTER TABLE sys_collection_job
    DROP CONSTRAINT IF EXISTS ck_collection_job_handler_type;
ALTER TABLE sys_collection_job
    ADD CONSTRAINT ck_collection_job_handler_type CHECK (
        handler_type IS NULL OR handler_type IN ('generic', 'dedicated')
    );

CREATE INDEX IF NOT EXISTS idx_collection_job_expired_lease
    ON sys_collection_job(lease_expires_at)
    WHERE status = 'running';

CREATE TABLE IF NOT EXISTS sys_collection_schedule_cursor (
    schedule_id          VARCHAR(64) PRIMARY KEY,
    last_dispatched_for  TIMESTAMPTZ NOT NULL,
    last_job_id          BIGINT NOT NULL REFERENCES sys_collection_job(job_id),
    handler_key          VARCHAR(255) NOT NULL,
    handler_version      VARCHAR(32) NOT NULL,
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE sys_collection_schedule_cursor IS
    'Monotonic durable cursor used to reconcile missed dedicated schedule fires';
