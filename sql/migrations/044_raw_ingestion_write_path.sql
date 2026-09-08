-- The payload GIN index was added before the normalized data-service tables
-- existed. Runtime reads now use api_name/request_hash/record_hash and never
-- search arbitrary JSON payload members, while every raw upsert still had to
-- maintain this multi-gigabyte index. Remove it to keep the lossless raw copy
-- without paying an unnecessary write-amplification penalty.
DROP INDEX IF EXISTS idx_tushare_raw_record_payload;
