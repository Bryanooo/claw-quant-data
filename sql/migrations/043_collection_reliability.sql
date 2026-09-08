-- Preserve canonical API lineage for purpose-built jobs created before the
-- application began assigning api_name automatically. This makes historical
-- partition failures visible to the interface-level monitor.
UPDATE sys_collection_job
SET api_name = CASE task_name
    WHEN 'trade_calendar' THEN 'trade_cal'
    WHEN 'stock_basic' THEN 'stock_basic'
    WHEN 'stock_daily' THEN 'daily'
    WHEN 'stock_daily_basic' THEN 'daily_basic'
    WHEN 'moneyflow' THEN 'moneyflow'
    WHEN 'stock_limit' THEN 'stk_limit'
    WHEN 'stock_suspend' THEN 'suspend_d'
    WHEN 'income_period' THEN 'income'
    WHEN 'balancesheet_period' THEN 'balancesheet'
    WHEN 'cashflow_period' THEN 'cashflow'
    WHEN 'financial_indicator_period' THEN 'fina_indicator'
END
WHERE api_name IS NULL
  AND task_name IN (
      'trade_calendar', 'stock_basic', 'stock_daily', 'stock_daily_basic',
      'moneyflow', 'stock_limit', 'stock_suspend', 'income_period',
      'balancesheet_period', 'cashflow_period', 'financial_indicator_period'
  );

-- Date-scoped money-flow reads and coverage checks previously required a
-- parallel scan of the entire table because the primary key begins with
-- ts_code. Match the indexes already present on the other core daily tables.
CREATE INDEX IF NOT EXISTS idx_moneyflow_trade_date
ON moneyflow (trade_date);
