-- Typed standard storage for rt_hk_k, newly granted to the configured token.
-- Permission was independently confirmed twice on 2026-09-09.

CREATE TABLE IF NOT EXISTS tushare_norm_rt_hk_k (
    _record_hash CHAR(64) PRIMARY KEY,
    _request_hash CHAR(64) NOT NULL,
    _source_doc_id INTEGER,
    _source_collected_at TIMESTAMPTZ NOT NULL,
    _first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _schema_version INTEGER NOT NULL DEFAULT 1,
    _extra_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    ts_code TEXT,
    pre_close NUMERIC,
    close NUMERIC,
    high NUMERIC,
    open NUMERIC,
    low NUMERIC,
    vol NUMERIC,
    amount NUMERIC
);

CREATE INDEX IF NOT EXISTS idx_tushare_norm_rt_hk_k_source
    ON tushare_norm_rt_hk_k (_source_collected_at DESC);

COMMENT ON TABLE tushare_norm_rt_hk_k IS
    '港股实时日线；契约驱动标准化表';
COMMENT ON COLUMN tushare_norm_rt_hk_k.ts_code IS '股票代码';
COMMENT ON COLUMN tushare_norm_rt_hk_k.pre_close IS '昨收价';
COMMENT ON COLUMN tushare_norm_rt_hk_k.close IS '收盘价';
COMMENT ON COLUMN tushare_norm_rt_hk_k.high IS '最高价';
COMMENT ON COLUMN tushare_norm_rt_hk_k.open IS '开盘价';
COMMENT ON COLUMN tushare_norm_rt_hk_k.low IS '最低价';
COMMENT ON COLUMN tushare_norm_rt_hk_k.vol IS '成交量（股）';
COMMENT ON COLUMN tushare_norm_rt_hk_k.amount IS '成交额(元)';
