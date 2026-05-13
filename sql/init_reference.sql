-- =============================================================================
-- 参考数据表 — 12 张表
-- 包括：异常波动、质押、股东、回购、解禁、大宗交易等
-- =============================================================================

-- 1. stk_shock: 个股异常波动
CREATE TABLE IF NOT EXISTS stk_shock (
    ts_code      VARCHAR(16)  NOT NULL,
    trade_date   DATE         NOT NULL,
    name         VARCHAR(32),
    trade_market VARCHAR(16),
    reason       TEXT,
    period       VARCHAR(32),
    created_at   TIMESTAMP    NOT NULL DEFAULT NOW(),
    PRIMARY KEY (ts_code, trade_date)
);

CREATE INDEX IF NOT EXISTS idx_stk_shock_date ON stk_shock (trade_date);
CREATE INDEX IF NOT EXISTS idx_stk_shock_code ON stk_shock (ts_code);

-- 2. stk_high_shock: 个股严重异常波动
CREATE TABLE IF NOT EXISTS stk_high_shock (
    ts_code      VARCHAR(16)  NOT NULL,
    trade_date   DATE         NOT NULL,
    name         VARCHAR(32),
    trade_market VARCHAR(16),
    reason       TEXT,
    period       VARCHAR(32),
    created_at   TIMESTAMP    NOT NULL DEFAULT NOW(),
    PRIMARY KEY (ts_code, trade_date)
);

CREATE INDEX IF NOT EXISTS idx_stk_high_shock_date ON stk_high_shock (trade_date);
CREATE INDEX IF NOT EXISTS idx_stk_high_shock_code ON stk_high_shock (ts_code);

-- 3. stk_alert: 交易所重点提示证券
CREATE TABLE IF NOT EXISTS stk_alert (
    ts_code    VARCHAR(16)  NOT NULL,
    name       VARCHAR(32),
    start_date DATE,
    end_date   DATE,
    type       VARCHAR(16),
    created_at TIMESTAMP    NOT NULL DEFAULT NOW(),
    PRIMARY KEY (ts_code, start_date)
);

CREATE INDEX IF NOT EXISTS idx_stk_alert_start ON stk_alert (start_date);

-- 4. top10_holders: 前十大股东
CREATE TABLE IF NOT EXISTS top10_holders (
    ts_code         VARCHAR(16)   NOT NULL,
    ann_date        DATE,
    end_date        DATE          NOT NULL,
    holder_name     VARCHAR(128)  NOT NULL,
    hold_amount     NUMERIC(20,4),
    hold_ratio      NUMERIC(10,4),
    hold_float_ratio NUMERIC(10,4),
    hold_change     NUMERIC(20,4),
    holder_type     VARCHAR(32),
    created_at      TIMESTAMP     NOT NULL DEFAULT NOW(),
    PRIMARY KEY (ts_code, end_date, holder_name)
);

CREATE INDEX IF NOT EXISTS idx_top10_holders_code ON top10_holders (ts_code);
CREATE INDEX IF NOT EXISTS idx_top10_holders_end ON top10_holders (end_date);

-- 5. top10_floatholders: 前十大流通股东
CREATE TABLE IF NOT EXISTS top10_floatholders (
    ts_code         VARCHAR(16)   NOT NULL,
    ann_date        DATE,
    end_date        DATE          NOT NULL,
    holder_name     VARCHAR(128)  NOT NULL,
    hold_amount     NUMERIC(20,4),
    hold_ratio      NUMERIC(10,4),
    hold_float_ratio NUMERIC(10,4),
    hold_change     NUMERIC(20,4),
    holder_type     VARCHAR(32),
    created_at      TIMESTAMP     NOT NULL DEFAULT NOW(),
    PRIMARY KEY (ts_code, end_date, holder_name)
);

CREATE INDEX IF NOT EXISTS idx_top10_floatholders_code ON top10_floatholders (ts_code);
CREATE INDEX IF NOT EXISTS idx_top10_floatholders_end ON top10_floatholders (end_date);

-- 6. pledge_stat: 股权质押统计
CREATE TABLE IF NOT EXISTS pledge_stat (
    ts_code       VARCHAR(16)  NOT NULL,
    end_date      DATE         NOT NULL,
    pledge_count  NUMERIC(10),
    unrest_pledge NUMERIC(20,4),
    rest_pledge   NUMERIC(20,4),
    total_share   NUMERIC(20,4),
    pledge_ratio  NUMERIC(10,4),
    created_at    TIMESTAMP    NOT NULL DEFAULT NOW(),
    PRIMARY KEY (ts_code, end_date)
);

CREATE INDEX IF NOT EXISTS idx_pledge_stat_code ON pledge_stat (ts_code);
CREATE INDEX IF NOT EXISTS idx_pledge_stat_end ON pledge_stat (end_date);

-- 7. pledge_detail: 股权质押明细
CREATE TABLE IF NOT EXISTS pledge_detail (
    ts_code        VARCHAR(16)   NOT NULL,
    ann_date       DATE          NOT NULL,
    holder_name    VARCHAR(128)  NOT NULL,
    pledge_amount  NUMERIC(20,4),
    start_date     DATE          NOT NULL,
    end_date       DATE,
    is_release     VARCHAR(4),
    release_date   DATE,
    pledgor        VARCHAR(128),
    holding_amount NUMERIC(20,4),
    pledged_amount NUMERIC(20,4),
    p_total_ratio  NUMERIC(10,4),
    h_total_ratio  NUMERIC(10,4),
    is_buyback     VARCHAR(4),
    created_at     TIMESTAMP     NOT NULL DEFAULT NOW(),
    PRIMARY KEY (ts_code, ann_date, holder_name, start_date)
);

CREATE INDEX IF NOT EXISTS idx_pledge_detail_code ON pledge_detail (ts_code);
CREATE INDEX IF NOT EXISTS idx_pledge_detail_ann ON pledge_detail (ann_date);

-- 8. repurchase: 股票回购
CREATE TABLE IF NOT EXISTS repurchase (
    ts_code    VARCHAR(16)  NOT NULL,
    ann_date   DATE         NOT NULL,
    end_date   DATE,
    proc       NUMERIC(10,4),
    exp_date   DATE,
    vol        NUMERIC(20,4),
    amount     NUMERIC(20,4),
    high_limit NUMERIC(12,2),
    low_limit  NUMERIC(12,2),
    created_at TIMESTAMP    NOT NULL DEFAULT NOW(),
    PRIMARY KEY (ts_code, ann_date)
);

CREATE INDEX IF NOT EXISTS idx_repurchase_code ON repurchase (ts_code);
CREATE INDEX IF NOT EXISTS idx_repurchase_ann ON repurchase (ann_date);

-- 9. share_float: 限售股解禁
CREATE TABLE IF NOT EXISTS share_float (
    ts_code     VARCHAR(16)  NOT NULL,
    ann_date    DATE,
    float_date  DATE         NOT NULL,
    float_share NUMERIC(20,4),
    float_ratio NUMERIC(10,4),
    holder_name VARCHAR(128) NOT NULL,
    share_type  VARCHAR(16)  NOT NULL,
    created_at  TIMESTAMP    NOT NULL DEFAULT NOW(),
    PRIMARY KEY (ts_code, float_date, holder_name, share_type)
);

CREATE INDEX IF NOT EXISTS idx_share_float_date ON share_float (float_date);
CREATE INDEX IF NOT EXISTS idx_share_float_code ON share_float (ts_code);

-- 10. block_trade: 大宗交易
CREATE TABLE IF NOT EXISTS block_trade (
    ts_code    VARCHAR(16)  NOT NULL,
    trade_date DATE         NOT NULL,
    price      NUMERIC(12,4) NOT NULL,
    vol        NUMERIC(20,2),
    amount     NUMERIC(20,4),
    buyer      VARCHAR(128) NOT NULL,
    seller     VARCHAR(128) NOT NULL,
    created_at TIMESTAMP    NOT NULL DEFAULT NOW(),
    PRIMARY KEY (ts_code, trade_date, price, buyer, seller)
);

CREATE INDEX IF NOT EXISTS idx_block_trade_date ON block_trade (trade_date);
CREATE INDEX IF NOT EXISTS idx_block_trade_code ON block_trade (ts_code);

-- 11. stk_holdernumber: 股东人数
CREATE TABLE IF NOT EXISTS stk_holdernumber (
    ts_code    VARCHAR(16)  NOT NULL,
    ann_date   DATE,
    end_date   DATE         NOT NULL,
    holder_num NUMERIC(10),
    created_at TIMESTAMP    NOT NULL DEFAULT NOW(),
    PRIMARY KEY (ts_code, end_date)
);

CREATE INDEX IF NOT EXISTS idx_stk_holdernumber_code ON stk_holdernumber (ts_code);
CREATE INDEX IF NOT EXISTS idx_stk_holdernumber_end ON stk_holdernumber (end_date);

-- 12. stk_holdertrade: 股东增减持
CREATE TABLE IF NOT EXISTS stk_holdertrade (
    ts_code        VARCHAR(16)   NOT NULL,
    ann_date       DATE          NOT NULL,
    holder_name    VARCHAR(128)  NOT NULL,
    holder_type    VARCHAR(32),
    in_de          VARCHAR(4),
    change_vol     NUMERIC(20,4),
    change_ratio   NUMERIC(10,4),
    after_share    NUMERIC(20,4),
    after_ratio    NUMERIC(10,4),
    avg_price      NUMERIC(12,4),
    total_share    NUMERIC(20,4),
    begin_date     DATE          NOT NULL,
    close_date     DATE,
    created_at     TIMESTAMP     NOT NULL DEFAULT NOW(),
    PRIMARY KEY (ts_code, ann_date, holder_name, begin_date)
);

CREATE INDEX IF NOT EXISTS idx_stk_holdertrade_code ON stk_holdertrade (ts_code);
CREATE INDEX IF NOT EXISTS idx_stk_holdertrade_ann ON stk_holdertrade (ann_date);
