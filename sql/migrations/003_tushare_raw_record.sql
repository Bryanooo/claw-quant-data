-- Add lossless storage for the catalog-driven Tushare collector.

CREATE TABLE IF NOT EXISTS tushare_raw_record (
    api_name       VARCHAR(128) NOT NULL,
    request_hash   CHAR(64) NOT NULL,
    record_hash    CHAR(64) NOT NULL,
    request_params JSONB NOT NULL DEFAULT '{}'::jsonb,
    payload        JSONB NOT NULL,
    source_doc_id  INTEGER,
    collected_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    first_seen_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (api_name, request_hash, record_hash)
);

CREATE INDEX IF NOT EXISTS idx_tushare_raw_record_api_collected
    ON tushare_raw_record (api_name, collected_at DESC);

CREATE INDEX IF NOT EXISTS idx_tushare_raw_record_payload
    ON tushare_raw_record USING GIN (payload);

COMMENT ON TABLE tushare_raw_record IS
    'Catalog-driven Tushare interface records; payload preserves upstream JSON';
