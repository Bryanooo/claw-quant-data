CREATE TABLE IF NOT EXISTS sys_data_coverage_job (
    job_id BIGSERIAL PRIMARY KEY,
    dataset_name VARCHAR(64) NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    status VARCHAR(16) NOT NULL DEFAULT 'queued',
    attempt SMALLINT NOT NULL DEFAULT 0,
    max_attempts SMALLINT NOT NULL DEFAULT 2,
    idempotency_key VARCHAR(160) UNIQUE,
    worker_id VARCHAR(128),
    error_message TEXT,
    available_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    CONSTRAINT ck_data_coverage_job_status
        CHECK (status IN ('queued', 'running', 'success', 'failed')),
    CONSTRAINT ck_data_coverage_job_attempts
        CHECK (attempt >= 0 AND max_attempts BETWEEN 1 AND 5),
    CONSTRAINT ck_data_coverage_job_range CHECK (start_date <= end_date)
);

CREATE INDEX IF NOT EXISTS idx_data_coverage_job_queue
    ON sys_data_coverage_job(status, available_at, created_at);
CREATE INDEX IF NOT EXISTS idx_data_coverage_job_dataset
    ON sys_data_coverage_job(dataset_name, created_at DESC);

CREATE TABLE IF NOT EXISTS sys_data_coverage_audit (
    audit_id BIGSERIAL PRIMARY KEY,
    job_id BIGINT REFERENCES sys_data_coverage_job(job_id),
    dataset_name VARCHAR(64) NOT NULL,
    strategy VARCHAR(32) NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    expected_partitions INTEGER NOT NULL DEFAULT 0,
    present_partitions INTEGER NOT NULL DEFAULT 0,
    missing_partitions INTEGER NOT NULL DEFAULT 0,
    observed_partitions INTEGER NOT NULL DEFAULT 0,
    coverage_ratio NUMERIC(8, 6),
    status VARCHAR(24) NOT NULL,
    evidence JSONB NOT NULL DEFAULT '{}'::jsonb,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_data_coverage_audit_range CHECK (start_date <= end_date),
    CONSTRAINT ck_data_coverage_audit_status
        CHECK (status IN ('complete', 'gaps', 'empty', 'observed_only'))
);

CREATE INDEX IF NOT EXISTS idx_data_coverage_audit_dataset
    ON sys_data_coverage_audit(dataset_name, finished_at DESC);

CREATE TABLE IF NOT EXISTS sys_data_coverage_partition (
    dataset_name VARCHAR(64) NOT NULL,
    partition_date DATE NOT NULL,
    status VARCHAR(24) NOT NULL,
    row_count BIGINT NOT NULL DEFAULT 0,
    entity_count BIGINT,
    expected BOOLEAN NOT NULL,
    evidence JSONB NOT NULL DEFAULT '{}'::jsonb,
    audit_id BIGINT NOT NULL REFERENCES sys_data_coverage_audit(audit_id),
    checked_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (dataset_name, partition_date),
    CONSTRAINT ck_data_coverage_partition_status
        CHECK (status IN ('present', 'missing', 'pending', 'observed_only'))
);

CREATE INDEX IF NOT EXISTS idx_data_coverage_partition_status
    ON sys_data_coverage_partition(dataset_name, status, partition_date DESC);

COMMENT ON TABLE sys_data_coverage_job IS 'Independent durable queue for dataset coverage audits';
COMMENT ON TABLE sys_data_coverage_audit IS 'Summary and evidence for one bounded coverage audit';
COMMENT ON TABLE sys_data_coverage_partition IS 'Latest observed state of one dataset date/report partition';
