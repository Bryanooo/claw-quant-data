ALTER TABLE sys_collection_job
    ADD COLUMN IF NOT EXISTS rows_fetched INTEGER,
    ADD COLUMN IF NOT EXISTS api_name VARCHAR(64),
    ADD COLUMN IF NOT EXISTS cadence VARCHAR(16),
    ADD COLUMN IF NOT EXISTS period_key VARCHAR(32),
    ADD COLUMN IF NOT EXISTS expected_for DATE,
    ADD COLUMN IF NOT EXISTS completion_status VARCHAR(16) NOT NULL DEFAULT 'pending',
    ADD COLUMN IF NOT EXISTS completion_evidence JSONB NOT NULL DEFAULT '{}'::jsonb;

UPDATE sys_collection_job
SET api_name = parameters->>'api_name'
WHERE api_name IS NULL AND task_name = 'tushare_interface';

UPDATE sys_collection_job
SET completion_status = CASE
    WHEN status = 'queued' THEN 'pending'
    WHEN status = 'running' THEN 'running'
    WHEN status = 'failed' AND error_message LIKE 'IncompleteCollectionError:%'
        THEN 'incomplete'
    WHEN status = 'failed' THEN 'failed'
    WHEN status = 'success'
         AND task_name = 'tushare_interface'
         AND COALESCE((parameters->>'complete')::boolean, TRUE)
        THEN 'complete'
    ELSE 'unverified'
END;

ALTER TABLE sys_collection_job
    DROP CONSTRAINT IF EXISTS ck_collection_job_completion_status;
ALTER TABLE sys_collection_job
    ADD CONSTRAINT ck_collection_job_completion_status CHECK (
        completion_status IN (
            'pending', 'running', 'retrying', 'complete', 'empty',
            'unverified', 'incomplete', 'failed'
        )
    );

CREATE INDEX IF NOT EXISTS idx_collection_job_interface_period
    ON sys_collection_job(api_name, period_key, created_at DESC);
