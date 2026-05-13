-- claw-quant-data/sql/init_forex.sql
-- 外汇数据建表（FXCM 交易商）

-- 1. 外汇基础信息
CREATE TABLE IF NOT EXISTS fx_obasic (
    ts_code          VARCHAR(32) NOT NULL,        -- 外汇代码
    name             VARCHAR(128),                 -- 名称
    classify         VARCHAR(32),                  -- 分类(FX/INDEX/COMMODITY/METAL/BUND/CRYPTO/FX_BASKET)
    exchange         VARCHAR(32),                  -- 交易商(FXCM)
    min_unit         NUMERIC(16,4),                -- 最小交易单位
    max_unit         NUMERIC(16,4),                -- 最大交易单位
    pip              NUMERIC(12,4),                -- 点
    pip_cost         NUMERIC(12,4),                -- 点值
    target_spread    NUMERIC(12,4),                -- 目标差价
    min_stop_distance NUMERIC(12,4),               -- 最小止损距离（点子）
    trading_hours    VARCHAR(256),                 -- 交易时间
    break_time       VARCHAR(256),                 -- 休市时间

    created_at      TIMESTAMP NOT NULL DEFAULT NOW(),
    PRIMARY KEY (ts_code)
);

-- 2. 外汇日线行情
CREATE TABLE IF NOT EXISTS fx_daily (
    ts_code          VARCHAR(32) NOT NULL,        -- 外汇代码
    trade_date       DATE        NOT NULL,        -- 交易日期(GMT)
    bid_open         NUMERIC(16,6),               -- 买入开盘价
    bid_close        NUMERIC(16,6),               -- 买入收盘价
    bid_high         NUMERIC(16,6),               -- 买入最高价
    bid_low          NUMERIC(16,6),               -- 买入最低价
    ask_open         NUMERIC(16,6),               -- 卖出开盘价
    ask_close        NUMERIC(16,6),               -- 卖出收盘价
    ask_high         NUMERIC(16,6),               -- 卖出最高价
    ask_low          NUMERIC(16,6),               -- 卖出最低价
    tick_qty         INTEGER,                     -- 报价笔数
    exchange         VARCHAR(32),                 -- 交易商

    created_at      TIMESTAMP NOT NULL DEFAULT NOW(),
    PRIMARY KEY (ts_code, trade_date)
);

CREATE INDEX IF NOT EXISTS idx_fx_daily_trade_date ON fx_daily (trade_date);
CREATE INDEX IF NOT EXISTS fx_daily_classify ON fx_daily (ts_code);

COMMENT ON TABLE fx_obasic IS '外汇基础信息（FXCM）';
COMMENT ON TABLE fx_daily IS '外汇日线行情';
