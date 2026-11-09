-- Preserve distinct provider indicator values for reconciliation. No fallback
-- into income.ebitda / balancesheet.fix_assets; old revisions remain null.
SET LOCAL lock_timeout = '5s';
ALTER TABLE fina_indicator
    ADD COLUMN IF NOT EXISTS ebit numeric(24,4),
    ADD COLUMN IF NOT EXISTS ebitda numeric(24,4),
    ADD COLUMN IF NOT EXISTS daa numeric(24,4),
    ADD COLUMN IF NOT EXISTS fa_turn numeric(20,8),
    ADD COLUMN IF NOT EXISTS total_fa_trun numeric(20,8),
    ADD COLUMN IF NOT EXISTS fixed_assets numeric(24,4);
COMMENT ON COLUMN fina_indicator.ebitda IS 'Tushare fina_indicator EBITDA; not a fallback for income.ebitda';
COMMENT ON COLUMN fina_indicator.daa IS 'Tushare fina_indicator depreciation and amortization';
COMMENT ON COLUMN fina_indicator.fa_turn IS 'Tushare fixed-asset turnover; distinct from total_fa_trun';
COMMENT ON COLUMN fina_indicator.total_fa_trun IS 'Tushare total fixed-asset turnover';
COMMENT ON COLUMN fina_indicator.fixed_assets IS 'Tushare total fixed assets; not a fallback for balancesheet.fix_assets';
