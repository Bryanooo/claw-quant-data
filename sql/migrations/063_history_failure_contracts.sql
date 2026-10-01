-- Repair storage contracts exposed by strict reverse-history collection.
-- The migration widens values without truncation and gives ths_hot a source
-- identity that does not pretend every ranked instrument has a Tushare code.

ALTER TABLE suspend_d
    ALTER COLUMN suspend_timing TYPE TEXT
    USING suspend_timing::text;

ALTER TABLE bak_basic
    ALTER COLUMN rev_yoy TYPE NUMERIC(20,6),
    ALTER COLUMN profit_yoy TYPE NUMERIC(20,6),
    ALTER COLUMN gpr TYPE NUMERIC(20,6),
    ALTER COLUMN npr TYPE NUMERIC(20,6);

ALTER TABLE ths_hot
    ADD COLUMN IF NOT EXISTS source_key VARCHAR(32);

UPDATE ths_hot
SET source_key = md5(concat_ws(
    '|', trade_date, data_type, COALESCE(ts_code, ''),
    COALESCE(ts_name, ''), rank::text, rank_time
))
WHERE source_key IS NULL;

ALTER TABLE ths_hot DROP CONSTRAINT IF EXISTS ths_hot_pkey;
ALTER TABLE ths_hot ALTER COLUMN ts_code DROP NOT NULL;
ALTER TABLE ths_hot ALTER COLUMN source_key SET NOT NULL;
ALTER TABLE ths_hot ADD CONSTRAINT ths_hot_pkey PRIMARY KEY (source_key);

CREATE INDEX IF NOT EXISTS idx_ths_hot_trade_date
    ON ths_hot (trade_date);
CREATE INDEX IF NOT EXISTS idx_ths_hot_ts_code
    ON ths_hot (ts_code) WHERE ts_code IS NOT NULL;

COMMENT ON COLUMN ths_hot.source_key IS
    '上游排行记录稳定标识，兼容港美股等无 ts_code 的合法记录';
