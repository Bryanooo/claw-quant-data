CREATE TABLE IF NOT EXISTS ant_request_budget (
    request_id BIGSERIAL PRIMARY KEY,
    requested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    category TEXT NOT NULL,
    units INTEGER NOT NULL CHECK(units>0),
    request_hash TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'reserved',
    http_status INTEGER
);
CREATE INDEX IF NOT EXISTS ant_request_budget_time ON ant_request_budget(requested_at);
CREATE UNIQUE INDEX IF NOT EXISTS ant_request_budget_import ON ant_request_budget(request_hash)
    WHERE category='legacy';
CREATE TABLE IF NOT EXISTS ant_query_cache (
    cache_key TEXT PRIMARY KEY,
    response JSONB NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL
);
CREATE TABLE IF NOT EXISTS ant_budget_control (
    singleton BOOLEAN PRIMARY KEY DEFAULT TRUE CHECK(singleton),
    blocked_until TIMESTAMPTZ,
    reason TEXT
);
INSERT INTO ant_budget_control(singleton) VALUES(TRUE) ON CONFLICT DO NOTHING;
-- Historical query batches are charged conservatively, including failures.
INSERT INTO ant_request_budget(requested_at,category,units,request_hash,status)
SELECT requested_at,'legacy',jsonb_array_length(request_params->'requests'),
       'source-audit:'||request_id,status
FROM source_raw_request_store WHERE source_id='financial_data'
  AND requested_at > NOW()-INTERVAL '7 days'
  AND jsonb_typeof(request_params->'requests')='array'
  AND jsonb_array_length(request_params->'requests')>0
ON CONFLICT DO NOTHING;
