-- Provider-neutral source registry and acquisition evidence foundation.

CREATE TABLE IF NOT EXISTS sys_data_source (
    source_id           VARCHAR(64) PRIMARY KEY,
    display_name        TEXT NOT NULL,
    source_kind         VARCHAR(32) NOT NULL,
    acquisition_modes   TEXT[] NOT NULL,
    credential_ref      TEXT,
    base_url            TEXT,
    timezone            VARCHAR(64) NOT NULL DEFAULT 'UTC',
    license_policy      JSONB NOT NULL DEFAULT '{}'::jsonb,
    configuration       JSONB NOT NULL DEFAULT '{}'::jsonb,
    enabled             BOOLEAN NOT NULL DEFAULT TRUE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_data_source_id CHECK (
        source_id ~ '^[a-z][a-z0-9_-]{1,63}$'
    ),
    CONSTRAINT ck_data_source_kind CHECK (
        source_kind IN ('api', 'website', 'file', 'stream', 'hybrid')
    ),
    CONSTRAINT ck_data_source_modes CHECK (
        acquisition_modes <@ ARRAY[
            'scheduled_pull', 'web_snapshot', 'query_through', 'stream'
        ]::TEXT[]
        AND cardinality(acquisition_modes) > 0
    )
);

CREATE TABLE IF NOT EXISTS sys_source_endpoint (
    source_id           VARCHAR(64) NOT NULL REFERENCES sys_data_source(source_id),
    endpoint_key        VARCHAR(128) NOT NULL,
    title               TEXT NOT NULL,
    acquisition_mode    VARCHAR(32) NOT NULL,
    resource_class      VARCHAR(32) NOT NULL DEFAULT 'default',
    cadence             VARCHAR(32),
    parser_name         VARCHAR(128),
    parser_version      VARCHAR(32),
    cache_ttl_seconds   INTEGER,
    request_contract    JSONB NOT NULL DEFAULT '{}'::jsonb,
    completeness_policy JSONB NOT NULL DEFAULT '{}'::jsonb,
    enabled             BOOLEAN NOT NULL DEFAULT TRUE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (source_id, endpoint_key),
    CONSTRAINT ck_source_endpoint_mode CHECK (
        acquisition_mode IN (
            'scheduled_pull', 'web_snapshot', 'query_through', 'stream'
        )
    ),
    CONSTRAINT ck_source_endpoint_cache_ttl CHECK (
        cache_ttl_seconds IS NULL OR cache_ttl_seconds >= 0
    )
);

INSERT INTO sys_data_source (
    source_id, display_name, source_kind, acquisition_modes,
    credential_ref, base_url, timezone, license_policy, configuration
) VALUES (
    'tushare', 'Tushare Pro', 'api', ARRAY['scheduled_pull']::TEXT[],
    'env:TUSHARE_TOKEN', 'https://api.tushare.pro', 'Asia/Shanghai',
    '{"persist_raw_records": true}'::jsonb,
    '{"adapter": "tushare"}'::jsonb
)
ON CONFLICT (source_id) DO UPDATE SET
    display_name=EXCLUDED.display_name,
    source_kind=EXCLUDED.source_kind,
    acquisition_modes=EXCLUDED.acquisition_modes,
    credential_ref=EXCLUDED.credential_ref,
    base_url=EXCLUDED.base_url,
    timezone=EXCLUDED.timezone,
    license_policy=EXCLUDED.license_policy,
    configuration=EXCLUDED.configuration,
    updated_at=NOW();

-- Do not rewrite or relock the very large legacy Tushare raw tables. New
-- providers use sidecar stores and provider-neutral views merge both worlds.
CREATE TABLE IF NOT EXISTS source_raw_request_store (
    request_id             BIGSERIAL PRIMARY KEY,
    source_id              VARCHAR(64) NOT NULL REFERENCES sys_data_source(source_id),
    endpoint_key           VARCHAR(128) NOT NULL,
    acquisition_mode       VARCHAR(32) NOT NULL,
    request_hash           CHAR(64) NOT NULL,
    logical_request_hash   CHAR(64) NOT NULL,
    request_params         JSONB NOT NULL,
    logical_request_params JSONB NOT NULL,
    collector_name         TEXT NOT NULL,
    status                 VARCHAR(16) NOT NULL,
    row_count              INTEGER NOT NULL DEFAULT 0,
    response_hash          CHAR(64),
    source_doc_id          INTEGER,
    error_message          TEXT,
    requested_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at           TIMESTAMPTZ,
    CONSTRAINT ck_source_raw_request_status CHECK (
        status IN ('success', 'empty', 'failed')
    ),
    CONSTRAINT ck_source_raw_request_mode CHECK (
        acquisition_mode IN (
            'scheduled_pull', 'web_snapshot', 'query_through', 'stream'
        )
    )
);
CREATE INDEX IF NOT EXISTS idx_source_raw_request_store_endpoint_time
    ON source_raw_request_store(
        source_id, endpoint_key, requested_at DESC, request_id DESC
    );

CREATE TABLE IF NOT EXISTS source_raw_record_store (
    source_id      VARCHAR(64) NOT NULL REFERENCES sys_data_source(source_id),
    endpoint_key   VARCHAR(128) NOT NULL,
    request_hash   CHAR(64) NOT NULL,
    record_hash    CHAR(64) NOT NULL,
    request_params JSONB NOT NULL,
    payload        JSONB NOT NULL,
    source_doc_id  INTEGER,
    collected_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    first_seen_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (source_id, endpoint_key, request_hash, record_hash)
);
CREATE INDEX IF NOT EXISTS idx_source_raw_record_store_endpoint_seen
    ON source_raw_record_store(source_id, endpoint_key, last_seen_at DESC);

CREATE OR REPLACE VIEW source_raw_request AS
SELECT request_id, 'tushare'::VARCHAR(64) AS source_id,
       api_name::VARCHAR(128) AS endpoint_key,
       'scheduled_pull'::VARCHAR(32) AS acquisition_mode,
       request_hash, logical_request_hash,
       request_params, logical_request_params, collector_name,
       status, row_count, response_hash, source_doc_id,
       error_message, requested_at, completed_at
FROM tushare_raw_request
UNION ALL
SELECT request_id, source_id, endpoint_key, acquisition_mode,
       request_hash, logical_request_hash, request_params,
       logical_request_params, collector_name, status, row_count,
       response_hash, source_doc_id, error_message, requested_at, completed_at
FROM source_raw_request_store;

CREATE OR REPLACE VIEW source_raw_record AS
SELECT 'tushare'::VARCHAR(64) AS source_id,
       api_name::VARCHAR(128) AS endpoint_key, request_hash, record_hash,
       request_params, payload, source_doc_id, collected_at,
       first_seen_at, last_seen_at
FROM tushare_raw_record
UNION ALL
SELECT source_id, endpoint_key, request_hash, record_hash,
       request_params, payload, source_doc_id, collected_at,
       first_seen_at, last_seen_at
FROM source_raw_record_store;

CREATE TABLE IF NOT EXISTS source_raw_artifact (
    artifact_id         BIGSERIAL PRIMARY KEY,
    source_id           VARCHAR(64) NOT NULL REFERENCES sys_data_source(source_id),
    endpoint_key        VARCHAR(128) NOT NULL,
    request_id          BIGINT,
    source_url          TEXT,
    content_type        TEXT NOT NULL,
    content_hash        CHAR(64) NOT NULL,
    storage_uri         TEXT,
    inline_content      BYTEA,
    http_status         INTEGER,
    response_headers    JSONB NOT NULL DEFAULT '{}'::jsonb,
    parser_name         VARCHAR(128),
    parser_version      VARCHAR(32),
    fetched_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    first_seen_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_source_raw_artifact_content CHECK (
        storage_uri IS NOT NULL OR inline_content IS NOT NULL
    ),
    CONSTRAINT ck_source_raw_artifact_http_status CHECK (
        http_status IS NULL OR http_status BETWEEN 100 AND 599
    ),
    UNIQUE (source_id, endpoint_key, content_hash)
);
CREATE INDEX IF NOT EXISTS idx_source_raw_artifact_endpoint_time
    ON source_raw_artifact(source_id, endpoint_key, fetched_at DESC);

ALTER TABLE sys_collection_job
    ADD COLUMN IF NOT EXISTS source_id VARCHAR(64),
    ADD COLUMN IF NOT EXISTS endpoint_key VARCHAR(128),
    ADD COLUMN IF NOT EXISTS acquisition_mode VARCHAR(32);

ALTER TABLE sys_collection_job
    ADD CONSTRAINT ck_collection_job_acquisition_mode CHECK (
        acquisition_mode IS NULL OR acquisition_mode IN (
            'scheduled_pull', 'web_snapshot', 'query_through', 'stream'
        )
    ) NOT VALID;

CREATE OR REPLACE FUNCTION apply_collection_job_source_identity()
RETURNS TRIGGER AS $$
BEGIN
    NEW.source_id := COALESCE(
        NEW.source_id,
        NEW.parameters->>'source_id',
        CASE
            WHEN NEW.task_name = 'tushare_interface' OR NEW.api_name IS NOT NULL
            THEN 'tushare'
        END
    );
    NEW.endpoint_key := COALESCE(
        NEW.endpoint_key,
        NEW.parameters->>'endpoint_key',
        NEW.api_name,
        NEW.parameters->>'api_name'
    );
    NEW.acquisition_mode := COALESCE(
        NEW.acquisition_mode,
        NEW.parameters->>'acquisition_mode',
        CASE WHEN NEW.source_id = 'tushare' THEN 'scheduled_pull' END
    );
    IF NEW.api_name IS NULL AND NEW.source_id = 'tushare' THEN
        NEW.api_name := NEW.endpoint_key;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_collection_job_source_identity ON sys_collection_job;
CREATE TRIGGER trg_collection_job_source_identity
BEFORE INSERT OR UPDATE OF task_name, parameters, api_name, source_id,
    endpoint_key, acquisition_mode
ON sys_collection_job
FOR EACH ROW EXECUTE FUNCTION apply_collection_job_source_identity();

CREATE INDEX IF NOT EXISTS idx_collection_job_source_endpoint_period
    ON sys_collection_job(source_id, endpoint_key, expected_for, period_key, created_at DESC)
    WHERE source_id IS NOT NULL;

COMMENT ON VIEW source_raw_request IS
    'Provider-neutral request audit view; legacy Tushare storage remains the physical compatibility table.';
COMMENT ON VIEW source_raw_record IS
    'Provider-neutral lossless record view keyed by source and endpoint.';
COMMENT ON TABLE source_raw_artifact IS
    'Immutable HTML, PDF, file or other raw artifacts with parser-version lineage.';
