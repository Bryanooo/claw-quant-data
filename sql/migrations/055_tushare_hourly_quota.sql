-- Bound low-quota interfaces before the provider rejects a request. The
-- counter is shared by every worker using the same PostgreSQL database/token.

CREATE TABLE IF NOT EXISTS sys_tushare_hourly_quota (
    api_name          VARCHAR(128) PRIMARY KEY,
    window_started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    reservations      INTEGER NOT NULL DEFAULT 0 CHECK (reservations >= 0),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE sys_tushare_hourly_quota IS
    'Cross-process fixed-window reservation counter for low hourly Tushare quotas';
