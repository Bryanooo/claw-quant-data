-- One-time, resumable initialization campaigns and the runtime mode gate.
CREATE TABLE IF NOT EXISTS sys_collection_initialization (
    initialization_id BIGSERIAL PRIMARY KEY,
    profile VARCHAR(16) NOT NULL,
    history_start DATE NOT NULL,
    history_end DATE NOT NULL,
    auto_activate BOOLEAN NOT NULL DEFAULT TRUE,
    status VARCHAR(16) NOT NULL DEFAULT 'running',
    current_phase SMALLINT NOT NULL DEFAULT 0,
    phase_name VARCHAR(32) NOT NULL DEFAULT 'foundation',
    planned_steps INTEGER NOT NULL DEFAULT 0,
    completed_steps INTEGER NOT NULL DEFAULT 0,
    failed_steps INTEGER NOT NULL DEFAULT 0,
    verification_round SMALLINT NOT NULL DEFAULT 1,
    options JSONB NOT NULL DEFAULT '{}'::jsonb,
    idempotency_key VARCHAR(128) NOT NULL UNIQUE,
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMPTZ,
    CONSTRAINT ck_collection_initialization_profile
        CHECK (profile IN ('quick', 'standard', 'research')),
    CONSTRAINT ck_collection_initialization_status
        CHECK (status IN ('running', 'paused', 'attention', 'ready', 'completed')),
    CONSTRAINT ck_collection_initialization_dates
        CHECK (history_start <= history_end),
    CONSTRAINT ck_collection_initialization_phase
        CHECK (current_phase BETWEEN 0 AND 4)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_collection_initialization_active
    ON sys_collection_initialization ((1))
    WHERE status IN ('running', 'paused', 'attention', 'ready');

CREATE TABLE IF NOT EXISTS sys_collection_initialization_step (
    step_id BIGSERIAL PRIMARY KEY,
    initialization_id BIGINT NOT NULL
        REFERENCES sys_collection_initialization(initialization_id) ON DELETE CASCADE,
    phase SMALLINT NOT NULL,
    step_key VARCHAR(192) NOT NULL,
    resource_type VARCHAR(16) NOT NULL DEFAULT 'collection',
    collection_job_id BIGINT REFERENCES sys_collection_job(job_id),
    coverage_job_id BIGINT REFERENCES sys_data_coverage_job(job_id),
    allow_empty BOOLEAN NOT NULL DEFAULT FALSE,
    require_verified BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (initialization_id, step_key),
    CONSTRAINT ck_collection_initialization_step_resource
        CHECK (resource_type IN ('collection', 'coverage')),
    CONSTRAINT ck_collection_initialization_step_target CHECK (
        (resource_type = 'collection' AND collection_job_id IS NOT NULL
            AND coverage_job_id IS NULL)
        OR
        (resource_type = 'coverage' AND coverage_job_id IS NOT NULL
            AND collection_job_id IS NULL)
    )
);

CREATE INDEX IF NOT EXISTS idx_collection_initialization_step_phase
    ON sys_collection_initialization_step(initialization_id, phase, step_id);

CREATE TABLE IF NOT EXISTS sys_collection_runtime_state (
    singleton BOOLEAN PRIMARY KEY DEFAULT TRUE CHECK (singleton),
    mode VARCHAR(32) NOT NULL,
    active_initialization_id BIGINT
        REFERENCES sys_collection_initialization(initialization_id),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_collection_runtime_mode
        CHECK (mode IN ('awaiting_initialization', 'initializing', 'daily'))
);

INSERT INTO sys_collection_runtime_state(singleton, mode)
SELECT TRUE,
       CASE
           WHEN EXISTS (SELECT 1 FROM sys_collection_job LIMIT 1)
             OR EXISTS (SELECT 1 FROM stock_basic LIMIT 1)
             OR EXISTS (SELECT 1 FROM tushare_raw_record LIMIT 1)
           THEN 'daily'
           ELSE 'awaiting_initialization'
       END
ON CONFLICT (singleton) DO NOTHING;

COMMENT ON TABLE sys_collection_initialization IS
    'Resumable installation-time history and baseline collection campaigns';
COMMENT ON TABLE sys_collection_runtime_state IS
    'Singleton gate: routine schedules run only in daily mode';
