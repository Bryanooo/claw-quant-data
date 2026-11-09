-- Source fields needed to explain EBITDA, not interchangeable EBITDA formulas.
-- Keep the legacy misspelled cashflow column for older live workers. Never copy
-- its values into the correctly named source field or backdate old revisions.
SET LOCAL lock_timeout = '5s';
ALTER TABLE income
    ADD COLUMN IF NOT EXISTS fin_exp_int_exp numeric(24,4),
    ADD COLUMN IF NOT EXISTS fin_exp_int_inc numeric(24,4);
ALTER TABLE cashflow
    ADD COLUMN IF NOT EXISTS finan_exp numeric(24,4),
    ADD COLUMN IF NOT EXISTS amort_intang_assets numeric(24,4),
    ADD COLUMN IF NOT EXISTS lt_amort_deferred_exp numeric(24,4),
    ADD COLUMN IF NOT EXISTS use_right_asset_dep numeric(24,4);
COMMENT ON COLUMN cashflow.financian_exp IS 'Legacy misspelling; not a Tushare field. Retained for old-worker compatibility only.';
COMMENT ON COLUMN cashflow.finan_exp IS 'Tushare cashflow.finan_exp; cash flow reconciliation finance expense, distinct from income.fin_exp';
COMMENT ON COLUMN income.fin_exp_int_exp IS 'Tushare income.fin_exp_int_exp: interest expense within finance expense, distinct from int_exp';
