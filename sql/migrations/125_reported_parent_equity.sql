-- Preserve the supplier's directly reported parent equity in each statement version.
SET LOCAL lock_timeout = '5s';
ALTER TABLE balancesheet ADD COLUMN IF NOT EXISTS total_hldr_eqy_exc_min_int NUMERIC(20,4);
COMMENT ON COLUMN balancesheet.total_hldr_eqy_exc_min_int IS '合并报表中归属于母公司所有者权益，元';
