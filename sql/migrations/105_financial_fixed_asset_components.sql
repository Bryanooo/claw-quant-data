-- Preserve source accounting concepts separately; do not replace fix_assets.
SET LOCAL lock_timeout = '5s';
ALTER TABLE balancesheet
    ADD COLUMN IF NOT EXISTS fix_assets_total NUMERIC(20,4),
    ADD COLUMN IF NOT EXISTS fixed_assets_disp NUMERIC(20,4);
COMMENT ON COLUMN balancesheet.fix_assets_total IS 'Tushare 固定资产合计，元；独立于 fix_assets，禁止静默混用';
COMMENT ON COLUMN balancesheet.fixed_assets_disp IS 'Tushare 固定资产清理，元；上游空值保留 NULL';
