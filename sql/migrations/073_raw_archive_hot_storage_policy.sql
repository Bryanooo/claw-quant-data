-- Raw record queries and retention use last_seen_at.  The older collected_at
-- index duplicates the same leading api_name access path, costs >2 GB on the
-- current archive, and amplifies every anomaly upsert.
DROP INDEX IF EXISTS idx_tushare_raw_record_api_collected;
