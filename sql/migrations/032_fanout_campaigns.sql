-- Durable, resumable aggregation across multiple bounded fan-out batches.
CREATE TABLE IF NOT EXISTS sys_collection_fanout_campaign (
    campaign_id BIGSERIAL PRIMARY KEY,
    api_name VARCHAR(64) NOT NULL,
    request JSONB NOT NULL DEFAULT '{}'::jsonb,
    page_size SMALLINT NOT NULL DEFAULT 100,
    status VARCHAR(16) NOT NULL DEFAULT 'running',
    completion_status VARCHAR(16) NOT NULL DEFAULT 'pending',
    universe_source VARCHAR(64),
    universe_total INTEGER,
    universe_digest CHAR(64),
    next_offset INTEGER NOT NULL DEFAULT 0,
    completed_offset INTEGER NOT NULL DEFAULT 0,
    pages_created INTEGER NOT NULL DEFAULT 0,
    pages_completed INTEGER NOT NULL DEFAULT 0,
    rows_fetched BIGINT NOT NULL DEFAULT 0,
    rows_inserted BIGINT NOT NULL DEFAULT 0,
    initialization_id BIGINT REFERENCES sys_collection_initialization(initialization_id),
    idempotency_key VARCHAR(128) NOT NULL UNIQUE,
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMPTZ,
    CONSTRAINT ck_fanout_campaign_page_size CHECK (page_size BETWEEN 1 AND 200),
    CONSTRAINT ck_fanout_campaign_status
        CHECK (status IN ('running', 'paused', 'attention', 'success')),
    CONSTRAINT ck_fanout_campaign_completion CHECK (
        completion_status IN ('pending', 'running', 'complete', 'empty', 'incomplete')
    ),
    CONSTRAINT ck_fanout_campaign_offsets CHECK (
        next_offset >= 0 AND completed_offset >= 0
        AND completed_offset <= next_offset
        AND pages_created >= 0 AND pages_completed >= 0
    )
);

CREATE TABLE IF NOT EXISTS sys_collection_fanout_campaign_batch (
    campaign_id BIGINT NOT NULL
        REFERENCES sys_collection_fanout_campaign(campaign_id) ON DELETE CASCADE,
    page_index INTEGER NOT NULL,
    batch_job_id BIGINT NOT NULL UNIQUE
        REFERENCES sys_collection_job(job_id),
    entity_offset INTEGER NOT NULL,
    next_offset INTEGER NOT NULL,
    entities_selected INTEGER NOT NULL,
    selected_digest CHAR(64) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (campaign_id, page_index),
    CONSTRAINT ck_fanout_campaign_batch_offsets CHECK (
        page_index >= 0 AND entity_offset >= 0
        AND next_offset > entity_offset AND entities_selected > 0
    )
);

CREATE INDEX IF NOT EXISTS idx_fanout_campaign_active
    ON sys_collection_fanout_campaign(status, updated_at, campaign_id)
    WHERE status IN ('running', 'attention');

CREATE INDEX IF NOT EXISTS idx_fanout_campaign_initialization
    ON sys_collection_fanout_campaign(initialization_id, campaign_id)
    WHERE initialization_id IS NOT NULL;

ALTER TABLE sys_collection_initialization
    DROP CONSTRAINT ck_collection_initialization_phase;

ALTER TABLE sys_collection_initialization
    ADD CONSTRAINT ck_collection_initialization_phase
    CHECK (current_phase BETWEEN 0 AND 5);

ALTER TABLE sys_collection_initialization_step
    ADD COLUMN IF NOT EXISTS fanout_campaign_id BIGINT
        REFERENCES sys_collection_fanout_campaign(campaign_id);

ALTER TABLE sys_collection_initialization_step
    DROP CONSTRAINT ck_collection_initialization_step_resource;

ALTER TABLE sys_collection_initialization_step
    ADD CONSTRAINT ck_collection_initialization_step_resource
    CHECK (resource_type IN ('collection', 'coverage', 'fanout'));

ALTER TABLE sys_collection_initialization_step
    DROP CONSTRAINT ck_collection_initialization_step_target;

ALTER TABLE sys_collection_initialization_step
    ADD CONSTRAINT ck_collection_initialization_step_target CHECK (
        (resource_type = 'collection' AND collection_job_id IS NOT NULL
            AND coverage_job_id IS NULL AND fanout_campaign_id IS NULL)
        OR
        (resource_type = 'coverage' AND coverage_job_id IS NOT NULL
            AND collection_job_id IS NULL AND fanout_campaign_id IS NULL)
        OR
        (resource_type = 'fanout' AND fanout_campaign_id IS NOT NULL
            AND collection_job_id IS NULL AND coverage_job_id IS NULL)
    );

COMMENT ON TABLE sys_collection_fanout_campaign IS
    'Resumable whole-universe collection across bounded fan-out batch pages';
COMMENT ON TABLE sys_collection_fanout_campaign_batch IS
    'Ordered immutable mapping between one fan-out campaign and its batch pages';
