-- claw-quant-data/sql/init_sge.sql
-- 上海黄金交易所（SGE）现货数据

-- 1. 白银/黄金现货基础信息
CREATE TABLE IF NOT EXISTS sge_basic (
    ts_code          VARCHAR(32) NOT NULL,        -- 品种代码
    ts_name          VARCHAR(64),                  -- 品种名称
    trade_type       VARCHAR(64),                  -- 交易类型
    t_unit           NUMERIC(12,4),                -- 交易单位(克/手)
    p_unit           NUMERIC(12,4),                -- 报价单位
    min_change       NUMERIC(12,4),                -- 最小变动价位
    price_limit      NUMERIC(10,4),                -- 每日价格最大波动限制(%)
    min_vol          INTEGER,                      -- 最小单笔报价量(手)
    max_vol          INTEGER,                      -- 最大单笔报价量(手)
    trade_mode       VARCHAR(32),                  -- 交易期限
    margin_rate      NUMERIC(10,4),                -- 保证金比例(%)
    liq_rate         NUMERIC(10,4),                -- 违约金比例(%)
    trade_time       VARCHAR(256),                 -- 交易时间
    list_date        DATE,                         -- 上市日期

    created_at      TIMESTAMP NOT NULL DEFAULT NOW(),
    PRIMARY KEY (ts_code)
);

-- 2. 黄金现货日行情
CREATE TABLE IF NOT EXISTS sge_daily (
    ts_code          VARCHAR(32) NOT NULL,        -- 现货合约代码
    trade_date       DATE        NOT NULL,        -- 交易日
    close            NUMERIC(16,4),               -- 收盘价(元/克)
    open             NUMERIC(16,4),               -- 开盘价(元/克)
    high             NUMERIC(16,4),               -- 最高价(元/克)
    low              NUMERIC(16,4),               -- 最低价(元/克)
    price_avg        NUMERIC(16,4),               -- 加权平均价(元/克)
    change           NUMERIC(16,4),               -- 涨跌点位(元/克)
    pct_change       NUMERIC(10,4),               -- 涨跌幅(%)
    vol              NUMERIC(20,4),               -- 成交量(千克)
    amount           NUMERIC(20,2),               -- 成交金额(元)
    oi               NUMERIC(20,4),               -- 市场持仓
    settle_vol       NUMERIC(20,4),               -- 交收量
    settle_dire      VARCHAR(32),                 -- 持仓方向

    created_at      TIMESTAMP NOT NULL DEFAULT NOW(),
    PRIMARY KEY (ts_code, trade_date)
);

CREATE INDEX IF NOT EXISTS idx_sge_daily_trade_date ON sge_daily (trade_date);
CREATE INDEX IF NOT EXISTS idx_sge_daily_ts_code ON sge_daily (ts_code);

COMMENT ON TABLE sge_basic IS '上海黄金交易所现货合约基础信息';
COMMENT ON TABLE sge_daily IS '上海黄金交易所现货合约日线行情';
