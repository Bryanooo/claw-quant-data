-- hsgt_top10: 沪深股通十大成交股
-- 更新时间: 每个交易日 18:00~20:00

CREATE TABLE IF NOT EXISTS hsgt_top10 (
    trade_date    DATE         NOT NULL,
    ts_code       VARCHAR(16)  NOT NULL,
    name          VARCHAR(64),
    close         NUMERIC(12, 2),
    change        NUMERIC(12, 2),
    rank          INT,
    market_type   INT          NOT NULL,   -- 1=沪市 3=深市
    amount        NUMERIC(16, 2),
    net_amount    NUMERIC(16, 2),
    buy           NUMERIC(16, 2),
    sell          NUMERIC(16, 2),
    created_at    TIMESTAMP    NOT NULL DEFAULT NOW(),
    PRIMARY KEY (trade_date, ts_code, market_type)
);

-- ggt_top10: 港股通十大成交股
CREATE TABLE IF NOT EXISTS ggt_top10 (
    trade_date     DATE         NOT NULL,
    ts_code        VARCHAR(16)  NOT NULL,
    name           VARCHAR(64),
    close          NUMERIC(12, 2),
    p_change       NUMERIC(8, 2),
    rank           INT,
    market_type    INT          NOT NULL,   -- 2=港股通(沪) 4=港股通(深)
    amount         NUMERIC(16, 2),
    net_amount     NUMERIC(16, 2),
    sh_amount      NUMERIC(16, 2),
    sh_net_amount  NUMERIC(16, 2),
    sh_buy         NUMERIC(16, 2),
    sh_sell        NUMERIC(16, 2),
    sz_amount      NUMERIC(16, 2),
    sz_net_amount  NUMERIC(16, 2),
    sz_buy         NUMERIC(16, 2),
    sz_sell        NUMERIC(16, 2),
    created_at     TIMESTAMP    NOT NULL DEFAULT NOW(),
    PRIMARY KEY (trade_date, ts_code, market_type)
);

-- ggt_daily: 港股通每日成交统计
CREATE TABLE IF NOT EXISTS ggt_daily (
    trade_date   DATE         NOT NULL PRIMARY KEY,
    buy_amount   NUMERIC(12, 2),
    buy_volume   NUMERIC(12, 2),
    sell_amount  NUMERIC(12, 2),
    sell_volume  NUMERIC(12, 2),
    created_at   TIMESTAMP    NOT NULL DEFAULT NOW()
);

-- ggt_monthly: 港股通每月成交统计
CREATE TABLE IF NOT EXISTS ggt_monthly (
    month           VARCHAR(6)   NOT NULL PRIMARY KEY,
    day_buy_amt     NUMERIC(12, 2),
    day_buy_vol     NUMERIC(12, 2),
    day_sell_amt    NUMERIC(12, 2),
    day_sell_vol    NUMERIC(12, 2),
    total_buy_amt   NUMERIC(12, 2),
    total_buy_vol   NUMERIC(12, 2),
    total_sell_amt  NUMERIC(12, 2),
    total_sell_vol  NUMERIC(12, 2),
    created_at      TIMESTAMP    NOT NULL DEFAULT NOW()
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_hsgt_top10_date ON hsgt_top10 (trade_date);
CREATE INDEX IF NOT EXISTS idx_ggt_top10_date ON ggt_top10 (trade_date);
