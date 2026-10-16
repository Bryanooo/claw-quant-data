-- Add the newly live-verified, strictly rate-limited US daily market dataset.
-- Raw payloads remain replayable in tushare_raw_record; this table is the
-- typed standard layer used by REST, coverage audits and V2 publication.

CREATE TABLE IF NOT EXISTS tushare_norm_us_daily (
    _record_hash CHAR(64) PRIMARY KEY,
    _request_hash CHAR(64) NOT NULL,
    _source_doc_id INTEGER,
    _source_collected_at TIMESTAMPTZ NOT NULL,
    _first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _schema_version INTEGER NOT NULL DEFAULT 1,
    _extra_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    ts_code TEXT,
    trade_date DATE,
    close NUMERIC,
    open NUMERIC,
    high NUMERIC,
    low NUMERIC,
    pre_close NUMERIC,
    change NUMERIC,
    pct_change NUMERIC,
    vol NUMERIC,
    amount NUMERIC,
    vwap NUMERIC,
    turnover_ratio NUMERIC,
    total_mv NUMERIC,
    pe NUMERIC,
    pb NUMERIC
);

CREATE INDEX IF NOT EXISTS idx_tushare_norm_us_daily_source
    ON tushare_norm_us_daily (_source_collected_at DESC);
CREATE INDEX IF NOT EXISTS idx_tushare_norm_us_daily_date
    ON tushare_norm_us_daily (trade_date DESC);
CREATE INDEX IF NOT EXISTS idx_tushare_norm_us_daily_symbol_date
    ON tushare_norm_us_daily (ts_code, trade_date DESC);

COMMENT ON TABLE tushare_norm_us_daily IS
    '美股未复权日行情；Tushare us_daily 契约驱动标准化表';

CREATE OR REPLACE VIEW tushare_current_us_daily AS
SELECT DISTINCT ON (trade_date, ts_code) *
FROM tushare_norm_us_daily
WHERE trade_date IS NOT NULL
  AND NULLIF(BTRIM(ts_code), '') IS NOT NULL
ORDER BY trade_date,
         ts_code,
         _source_collected_at DESC,
         _last_seen_at DESC,
         _record_hash DESC;

COMMENT ON VIEW tushare_current_us_daily IS
    'Latest trustworthy US daily payload per trade_date and ts_code';
