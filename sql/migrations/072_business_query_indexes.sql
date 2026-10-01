-- migrate: no-transaction
-- Online indexes for proven coverage and research query shapes.  The migration
-- runner executes these statements one at a time in autocommit mode because
-- PostgreSQL forbids CREATE INDEX CONCURRENTLY inside a transaction block.

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_tushare_norm_factor_value_business_current
    ON tushare_norm_factor_value
       (trade_date, ts_code, factor_name, _source_collected_at DESC,
        _last_seen_at DESC, _record_hash DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_tushare_norm_fund_portfolio_business_current
    ON tushare_norm_fund_portfolio
       (ts_code, end_date, symbol, ann_date DESC NULLS LAST,
        _source_collected_at DESC, _last_seen_at DESC, _record_hash DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_tushare_norm_index_weight_business_current
    ON tushare_norm_index_weight
       (trade_date, index_code, con_code, _source_collected_at DESC,
        _last_seen_at DESC, _record_hash DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_tushare_norm_slb_sec_detail_business_current
    ON tushare_norm_slb_sec_detail
       (trade_date, ts_code, tenor, _source_collected_at DESC,
        _last_seen_at DESC, _record_hash DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_tushare_norm_eco_cal_business_current
    ON tushare_norm_eco_cal
       (date, time, currency, country, event, _source_collected_at DESC,
        _last_seen_at DESC, _record_hash DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_tushare_norm_major_news_business_current
    ON tushare_norm_major_news
       (src, pub_time, title, _source_collected_at DESC,
        _last_seen_at DESC, _record_hash DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_tushare_norm_fund_nav_business_current
    ON tushare_norm_fund_nav
       (nav_date, ts_code, ann_date DESC NULLS LAST,
        _source_collected_at DESC, _last_seen_at DESC, _record_hash DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_tushare_norm_fina_audit_business_current
    ON tushare_norm_fina_audit
       (ts_code, end_date, ann_date DESC NULLS LAST,
        _source_collected_at DESC, _last_seen_at DESC, _record_hash DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_tushare_norm_fund_nav_ts_code_nav_date_current
    ON tushare_norm_fund_nav
       (ts_code, nav_date DESC, _last_seen_at DESC, _record_hash DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_tushare_norm_daily_basic_ts_code_trade_date_current
    ON tushare_norm_daily_basic
       (ts_code, trade_date DESC, _source_collected_at DESC,
        _last_seen_at DESC, _record_hash DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_tushare_norm_index_weight_index_date_component
    ON tushare_norm_index_weight (index_code, trade_date DESC, con_code);
