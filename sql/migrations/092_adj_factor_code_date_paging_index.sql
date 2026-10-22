-- migrate: no-transaction
-- adj_factor is one of the largest versioned tables (~19M rows) and every
-- technicals request pages through it three times (1000 rows per page).
-- Migration 082 added a partial index that only applies when the query
-- mentions "adj_factor IS NOT NULL"; the governed dataset query filters by
-- ts_code plus a date range instead, so PostgreSQL fell back to a parallel
-- sequential scan (~500ms per page, ~1.5s per request).
--
-- This index matches the real access path (single ts_code, newest dates first,
-- deterministic tie-break on _record_hash) so each page becomes an index scan.

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_tushare_norm_adj_factor_code_date_hash
    ON tushare_norm_adj_factor (ts_code, trade_date DESC, _record_hash DESC);
