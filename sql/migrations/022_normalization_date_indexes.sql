-- Remove misleading range indexes from reference/snapshot interfaces whose
-- date-like attributes are not the dataset's observation date.

DROP INDEX IF EXISTS idx_tushare_norm_cb_basic_date;
DROP INDEX IF EXISTS idx_tushare_norm_cb_rate_date;
DROP INDEX IF EXISTS idx_tushare_norm_ci_index_member_date;
DROP INDEX IF EXISTS idx_tushare_norm_etf_basic_date;
DROP INDEX IF EXISTS idx_tushare_norm_etf_index_date;
DROP INDEX IF EXISTS idx_tushare_norm_fund_basic_date;
DROP INDEX IF EXISTS idx_tushare_norm_fut_basic_date;
DROP INDEX IF EXISTS idx_tushare_norm_fut_weekly_detail_date;
DROP INDEX IF EXISTS idx_tushare_norm_hk_basic_date;
DROP INDEX IF EXISTS idx_tushare_norm_index_member_all_date;
DROP INDEX IF EXISTS idx_tushare_norm_opt_basic_date;
DROP INDEX IF EXISTS idx_tushare_norm_us_basic_date;
