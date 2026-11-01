-- Five-minute intraday observation control plane and durable evidence.

ALTER TABLE sys_stock_watchlist
    ADD COLUMN IF NOT EXISTS intraday_observation_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS observation_profile VARCHAR(32) NOT NULL DEFAULT 'balanced',
    ADD COLUMN IF NOT EXISTS observation_enabled_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS observation_muted_until TIMESTAMPTZ;

CREATE TABLE IF NOT EXISTS sys_intraday_collection_run (
    run_id BIGSERIAL PRIMARY KEY,
    scheduled_for TIMESTAMPTZ NOT NULL UNIQUE,
    status VARCHAR(24) NOT NULL CHECK (status IN ('running', 'success', 'attention', 'failed')),
    trigger_source VARCHAR(24) NOT NULL DEFAULT 'schedule',
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    outer_calls INTEGER NOT NULL DEFAULT 0,
    subrequests INTEGER NOT NULL DEFAULT 0,
    fetched_rows INTEGER NOT NULL DEFAULT 0,
    stored_rows INTEGER NOT NULL DEFAULT 0,
    error_message TEXT,
    evidence JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_intraday_run_latest
    ON sys_intraday_collection_run (scheduled_for DESC);

CREATE TABLE IF NOT EXISTS intraday_quote_bar (
    symbol VARCHAR(24) NOT NULL,
    bar_time TIMESTAMPTZ NOT NULL,
    period VARCHAR(16) NOT NULL,
    scope_type VARCHAR(24) NOT NULL,
    name TEXT,
    open NUMERIC,
    high NUMERIC,
    low NUMERIC,
    close NUMERIC,
    previous_close NUMERIC,
    volume NUMERIC,
    amount NUMERIC,
    pct_chg NUMERIC,
    trade_status VARCHAR(40),
    limit_status VARCHAR(24),
    run_id BIGINT REFERENCES sys_intraday_collection_run(run_id) ON DELETE SET NULL,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    collected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (symbol, bar_time, period)
);

CREATE INDEX IF NOT EXISTS idx_intraday_quote_bar_time
    ON intraday_quote_bar (bar_time DESC, scope_type);

CREATE TABLE IF NOT EXISTS intraday_flow_snapshot (
    symbol VARCHAR(24) NOT NULL,
    snapshot_time TIMESTAMPTZ NOT NULL,
    period VARCHAR(16) NOT NULL,
    main_in NUMERIC,
    main_out NUMERIC,
    main_net_inflow NUMERIC,
    retail_net_in NUMERIC,
    total_net_in NUMERIC,
    run_id BIGINT REFERENCES sys_intraday_collection_run(run_id) ON DELETE SET NULL,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    collected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (symbol, snapshot_time, period)
);

CREATE TABLE IF NOT EXISTS intraday_analysis_snapshot (
    analysis_id BIGSERIAL PRIMARY KEY,
    run_id BIGINT NOT NULL REFERENCES sys_intraday_collection_run(run_id) ON DELETE CASCADE,
    as_of TIMESTAMPTZ NOT NULL,
    scope_type VARCHAR(24) NOT NULL,
    scope_code VARCHAR(24) NOT NULL,
    scope_name TEXT NOT NULL,
    state VARCHAR(40) NOT NULL,
    score NUMERIC NOT NULL CHECK (score BETWEEN 0 AND 100),
    confidence VARCHAR(16) NOT NULL,
    conclusion TEXT NOT NULL,
    metrics JSONB NOT NULL DEFAULT '{}'::jsonb,
    signals JSONB NOT NULL DEFAULT '[]'::jsonb,
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    data_quality JSONB NOT NULL DEFAULT '{}'::jsonb,
    rule_version VARCHAR(40) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (run_id, scope_type, scope_code)
);

CREATE INDEX IF NOT EXISTS idx_intraday_analysis_latest
    ON intraday_analysis_snapshot (scope_type, scope_code, as_of DESC);

COMMENT ON TABLE intraday_analysis_snapshot IS
    '盘中观察结论；每条结论保留指标、信号、证据、质量与规则版本。';
