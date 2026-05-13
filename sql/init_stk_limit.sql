-- stk_limit: 每日涨跌停价格（A/B股和基金）
-- 每个交易日 8:40 更新当日涨跌停价格
-- 积分门槛: 2000

CREATE TABLE IF NOT EXISTS stk_limit (
    trade_date    DATE         NOT NULL,   -- 交易日期
    ts_code       VARCHAR(16)  NOT NULL,   -- TS代码
    pre_close     NUMERIC(12, 2),          -- 昨日收盘价
    up_limit      NUMERIC(12, 2) NOT NULL, -- 涨停价
    down_limit    NUMERIC(12, 2) NOT NULL, -- 跌停价
    created_at    TIMESTAMP    NOT NULL DEFAULT NOW(),
    PRIMARY KEY (trade_date, ts_code)
);

CREATE INDEX IF NOT EXISTS idx_stk_limit_date ON stk_limit (trade_date);
CREATE INDEX IF NOT EXISTS idx_stk_limit_code ON stk_limit (ts_code);
