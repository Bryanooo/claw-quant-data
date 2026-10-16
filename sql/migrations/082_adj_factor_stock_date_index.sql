-- migrate: no-transaction
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_tushare_norm_adj_factor_code_date_current ON tushare_norm_adj_factor(ts_code, trade_date DESC, _last_seen_at DESC, _record_hash DESC) WHERE adj_factor IS NOT NULL;
