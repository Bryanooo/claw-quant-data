-- The former Tushare ggt_monthly endpoint is no longer accepted. Monthly
-- values are derived from ggt_daily, so totals need wider numeric columns.

ALTER TABLE ggt_monthly
    ALTER COLUMN day_buy_amt TYPE NUMERIC(20, 4),
    ALTER COLUMN day_buy_vol TYPE NUMERIC(20, 4),
    ALTER COLUMN day_sell_amt TYPE NUMERIC(20, 4),
    ALTER COLUMN day_sell_vol TYPE NUMERIC(20, 4),
    ALTER COLUMN total_buy_amt TYPE NUMERIC(20, 4),
    ALTER COLUMN total_buy_vol TYPE NUMERIC(20, 4),
    ALTER COLUMN total_sell_amt TYPE NUMERIC(20, 4),
    ALTER COLUMN total_sell_vol TYPE NUMERIC(20, 4);
