-- Resumable page checkpoints for catalog-driven Tushare collection.

CREATE TABLE IF NOT EXISTS sys_tushare_collection_checkpoint (
    api_name          VARCHAR(128) NOT NULL,
    scope_hash        CHAR(64) NOT NULL,
    base_params       JSONB NOT NULL DEFAULT '{}'::jsonb,
    status            VARCHAR(16) NOT NULL DEFAULT 'running',
    next_offset       BIGINT NOT NULL DEFAULT 0,
    page_size         INTEGER NOT NULL,
    pages_completed   INTEGER NOT NULL DEFAULT 0,
    rows_fetched      BIGINT NOT NULL DEFAULT 0,
    rows_stored       BIGINT NOT NULL DEFAULT 0,
    last_page_hash    CHAR(64),
    last_error        TEXT,
    started_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at      TIMESTAMPTZ,
    PRIMARY KEY (api_name, scope_hash),
    CONSTRAINT ck_tushare_checkpoint_status
        CHECK (status IN ('running', 'success', 'partial', 'failed')),
    CONSTRAINT ck_tushare_checkpoint_counts
        CHECK (
            next_offset >= 0 AND page_size > 0 AND pages_completed >= 0
            AND rows_fetched >= 0 AND rows_stored >= 0
        )
);

CREATE INDEX IF NOT EXISTS idx_tushare_checkpoint_status
    ON sys_tushare_collection_checkpoint(status, updated_at);

CREATE TABLE IF NOT EXISTS sys_major_news_window_checkpoint (
    source          VARCHAR(64) NOT NULL,
    window_start    TIMESTAMP NOT NULL,
    window_end      TIMESTAMP NOT NULL,
    status          VARCHAR(16) NOT NULL,
    rows_fetched    INTEGER NOT NULL DEFAULT 0,
    rows_stored     INTEGER NOT NULL DEFAULT 0,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (source, window_start, window_end),
    CONSTRAINT ck_major_news_checkpoint_window CHECK (window_start <= window_end),
    CONSTRAINT ck_major_news_checkpoint_status CHECK (status IN ('split', 'complete')),
    CONSTRAINT ck_major_news_checkpoint_rows CHECK (
        rows_fetched >= 0 AND rows_stored >= 0
    )
);

CREATE INDEX IF NOT EXISTS idx_major_news_checkpoint_status
    ON sys_major_news_window_checkpoint(status, updated_at);
