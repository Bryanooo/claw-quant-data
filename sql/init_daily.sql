-- A股日线行情（Tushare daily）
CREATE TABLE IF NOT EXISTS daily (
    ts_code         VARCHAR(16) NOT NULL,
    trade_date      DATE NOT NULL,
    open            NUMERIC(18,4),
    high            NUMERIC(18,4),
    low             NUMERIC(18,4),
    close           NUMERIC(18,4),
    pre_close       NUMERIC(18,4),
    change          NUMERIC(18,4),
    pct_chg         NUMERIC(18,6),
    vol             NUMERIC(24,4),
    amount          NUMERIC(24,4),
    PRIMARY KEY (ts_code, trade_date)
);

CREATE INDEX IF NOT EXISTS idx_daily_trade_date ON daily(trade_date);
CREATE INDEX IF NOT EXISTS idx_daily_ts_code ON daily(ts_code);
