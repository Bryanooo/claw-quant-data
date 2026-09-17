-- Transport-level lineage for both generic and specialized Tushare collectors.

CREATE TABLE IF NOT EXISTS tushare_raw_request (
    request_id              BIGSERIAL PRIMARY KEY,
    api_name                VARCHAR(128) NOT NULL,
    request_hash            CHAR(64) NOT NULL,
    logical_request_hash    CHAR(64) NOT NULL,
    request_params          JSONB NOT NULL DEFAULT '{}'::jsonb,
    logical_request_params  JSONB NOT NULL DEFAULT '{}'::jsonb,
    collector_name          VARCHAR(255) NOT NULL,
    status                  VARCHAR(16) NOT NULL,
    row_count               INTEGER NOT NULL DEFAULT 0,
    response_hash           CHAR(64),
    source_doc_id           INTEGER,
    error_message           TEXT,
    requested_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at            TIMESTAMPTZ,
    CONSTRAINT ck_tushare_raw_request_status
        CHECK (status IN ('success', 'empty', 'failed')),
    CONSTRAINT ck_tushare_raw_request_row_count
        CHECK (row_count >= 0)
);

CREATE INDEX IF NOT EXISTS idx_tushare_raw_request_api_time
    ON tushare_raw_request (api_name, requested_at DESC, request_id DESC);

CREATE INDEX IF NOT EXISTS idx_tushare_raw_request_logical
    ON tushare_raw_request (api_name, logical_request_hash, requested_at DESC);

CREATE INDEX IF NOT EXISTS idx_tushare_raw_request_status_time
    ON tushare_raw_request (status, requested_at DESC)
    WHERE status <> 'success';

COMMENT ON TABLE tushare_raw_request IS
    'One immutable audit row per Tushare SDK query, including empty and failed calls';
