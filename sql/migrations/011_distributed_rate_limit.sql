-- Shared rate reservations make multiple workers safe for one Tushare token.

CREATE TABLE IF NOT EXISTS sys_tushare_rate_limit (
    api_name        VARCHAR(128) PRIMARY KEY,
    next_allowed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE sys_tushare_rate_limit IS
    'Cross-process next request slot for each Tushare interface';
