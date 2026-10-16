-- migrate: no-transaction
-- Stock-centric ownership research filters fund portfolios by held security,
-- while the normalization identity starts with the fund code.  Keep the
-- point-in-time aggregation indexed without changing the business identity.
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_tushare_norm_fund_portfolio_symbol_history
    ON tushare_norm_fund_portfolio (
        symbol,
        end_date,
        ann_date DESC NULLS LAST,
        ts_code,
        _last_seen_at DESC
    )
    INCLUDE (mkv, amount, stk_float_ratio);
