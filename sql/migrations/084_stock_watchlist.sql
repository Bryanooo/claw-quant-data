-- Durable, single-user watchlist for the local research dashboard.
-- This is preference metadata only; market and research data remain in their
-- governed business tables.

CREATE TABLE IF NOT EXISTS sys_stock_watchlist (
    ts_code         VARCHAR(16) PRIMARY KEY
                    REFERENCES stock_basic(ts_code) ON UPDATE CASCADE ON DELETE CASCADE,
    sort_order      INTEGER NOT NULL DEFAULT 0 CHECK (sort_order >= 0),
    added_at        TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_sys_stock_watchlist_order
    ON sys_stock_watchlist (sort_order, added_at, ts_code);
