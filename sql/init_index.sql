-- ============================================================
-- 指数数据建表 SQL
-- 采集器：collectors/index/
-- ============================================================

-- 1. 指数基本信息
CREATE TABLE IF NOT EXISTS index_basic (
    ts_code     VARCHAR(50) NOT NULL,
    name        VARCHAR(100),
    market      VARCHAR(10),
    publisher   VARCHAR(100),
    category    VARCHAR(50),
    base_date   VARCHAR(8),
    base_point  NUMERIC(16,2),
    list_date   VARCHAR(8),
    PRIMARY KEY (ts_code)
);

-- 2. 指数日线行情
CREATE TABLE IF NOT EXISTS index_daily (
    ts_code     VARCHAR(50) NOT NULL,
    trade_date  VARCHAR(8) NOT NULL,
    open        NUMERIC(16,2),
    high        NUMERIC(16,2),
    low         NUMERIC(16,2),
    close       NUMERIC(16,2),
    pre_close   NUMERIC(16,2),
    change      NUMERIC(16,2),
    pct_chg     NUMERIC(10,4),
    vol         NUMERIC(20,2),
    amount      NUMERIC(20,2),
    PRIMARY KEY (ts_code, trade_date)
);

-- 3. 指数周线行情
CREATE TABLE IF NOT EXISTS index_weekly (
    ts_code     VARCHAR(50) NOT NULL,
    trade_date  VARCHAR(8) NOT NULL,
    open        NUMERIC(16,2),
    high        NUMERIC(16,2),
    low         NUMERIC(16,2),
    close       NUMERIC(16,2),
    pre_close   NUMERIC(16,2),
    change      NUMERIC(16,2),
    pct_chg     NUMERIC(10,4),
    vol         NUMERIC(20,2),
    amount      NUMERIC(20,2),
    PRIMARY KEY (ts_code, trade_date)
);

-- 4. 指数月线行情
CREATE TABLE IF NOT EXISTS index_monthly (
    ts_code     VARCHAR(50) NOT NULL,
    trade_date  VARCHAR(8) NOT NULL,
    open        NUMERIC(16,2),
    high        NUMERIC(16,2),
    low         NUMERIC(16,2),
    close       NUMERIC(16,2),
    pre_close   NUMERIC(16,2),
    change      NUMERIC(16,2),
    pct_chg     NUMERIC(10,4),
    vol         NUMERIC(20,2),
    amount      NUMERIC(20,2),
    PRIMARY KEY (ts_code, trade_date)
);

-- 5. 大盘指数每日指标
CREATE TABLE IF NOT EXISTS index_dailybasic (
    ts_code         VARCHAR(50) NOT NULL,
    trade_date      VARCHAR(8) NOT NULL,
    total_mv        NUMERIC(20,2),
    float_mv        NUMERIC(20,2),
    total_share     NUMERIC(20,2),
    float_share     NUMERIC(20,2),
    free_share      NUMERIC(20,2),
    turnover_rate   NUMERIC(10,4),
    turnover_rate_f NUMERIC(10,4),
    pe              NUMERIC(16,2),
    pe_ttm          NUMERIC(16,2),
    pb              NUMERIC(16,2),
    PRIMARY KEY (ts_code, trade_date)
);

-- 6. 国际指数行情
CREATE TABLE IF NOT EXISTS index_global (
    ts_code     VARCHAR(50) NOT NULL,
    trade_date  VARCHAR(8) NOT NULL,
    open        NUMERIC(16,2),
    close       NUMERIC(16,2),
    high        NUMERIC(16,2),
    low         NUMERIC(16,2),
    pre_close   NUMERIC(16,2),
    change      NUMERIC(16,2),
    pct_chg     NUMERIC(10,4),
    swing       NUMERIC(10,4),
    vol         NUMERIC(20,2),
    PRIMARY KEY (ts_code, trade_date)
);

-- 7. 申万行业日线行情
CREATE TABLE IF NOT EXISTS ths_daily (
    ts_code        VARCHAR(50) NOT NULL,
    trade_date     VARCHAR(8) NOT NULL,
    open           NUMERIC(16,2),
    high           NUMERIC(16,2),
    low            NUMERIC(16,2),
    close          NUMERIC(16,2),
    pre_close      NUMERIC(16,2),
    avg_price      NUMERIC(16,4),
    change         NUMERIC(16,2),
    pct_change     NUMERIC(10,4),
    vol            NUMERIC(20,2),
    turnover_rate  NUMERIC(10,4),
    PRIMARY KEY (ts_code, trade_date)
);

-- 8. 申万行业成分构成
CREATE TABLE IF NOT EXISTS ths_member (
    ts_code    VARCHAR(50) NOT NULL,
    con_code   VARCHAR(50) NOT NULL,
    con_name   VARCHAR(100),
    PRIMARY KEY (ts_code, con_code)
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_index_daily_date ON index_daily(trade_date);
CREATE INDEX IF NOT EXISTS idx_index_dailybasic_date ON index_dailybasic(trade_date);
CREATE INDEX IF NOT EXISTS idx_index_global_date ON index_global(trade_date);
CREATE INDEX IF NOT EXISTS idx_ths_daily_date ON ths_daily(trade_date);
