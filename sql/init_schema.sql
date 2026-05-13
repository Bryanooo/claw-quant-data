-- ============================================================
-- claw-quant-data 建表脚本
-- ============================================================
-- 用法: psql -h 127.0.0.1 -U tushare -d tushare_db -f init_schema.sql
-- ============================================================

-- 1. 系统配置表
CREATE TABLE IF NOT EXISTS sys_config (
    id              SERIAL PRIMARY KEY,
    cfg_key         VARCHAR(128) NOT NULL UNIQUE,
    cfg_value       TEXT,
    cfg_type        VARCHAR(32) NOT NULL DEFAULT 'string',
    description     VARCHAR(500),
    is_encrypted    BOOLEAN NOT NULL DEFAULT FALSE,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    updated_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_by      VARCHAR(64) DEFAULT 'system'
);

-- 2. 股票基础信息
CREATE TABLE IF NOT EXISTS stock_basic (
    ts_code         VARCHAR(16) PRIMARY KEY,
    symbol          VARCHAR(8),
    name            VARCHAR(32),
    area            VARCHAR(32),
    industry        VARCHAR(64),
    fullname        VARCHAR(128),
    enname          VARCHAR(128),
    cnspell         VARCHAR(16),
    market          VARCHAR(16),
    exchange        VARCHAR(8),
    curr_type       VARCHAR(8),
    list_status     VARCHAR(4),
    list_date       VARCHAR(16),
    delist_date     VARCHAR(16),
    is_hs           VARCHAR(4),
    act_name        VARCHAR(64),
    act_ent_type    VARCHAR(64)
);

-- 3. 交易日历
CREATE TABLE IF NOT EXISTS trade_cal (
    exchange        VARCHAR(8) NOT NULL,
    cal_date        DATE NOT NULL,
    is_open         SMALLINT NOT NULL DEFAULT 0,
    pretrade_date   DATE,
    PRIMARY KEY (exchange, cal_date)
);

-- 4. ST股票列表（历史每日ST）
CREATE TABLE IF NOT EXISTS stock_st (
    ts_code         VARCHAR(16) NOT NULL,
    name            VARCHAR(32),
    trade_date      DATE NOT NULL,
    type            VARCHAR(16),
    type_name       VARCHAR(64),
    PRIMARY KEY (ts_code, trade_date)
);

-- 5. ST风险警示板（含变更原因）
CREATE TABLE IF NOT EXISTS st_risk_warning (
    ts_code         VARCHAR(16) NOT NULL,
    name            VARCHAR(32),
    pub_date        DATE,
    imp_date        DATE NOT NULL,
    st_type         VARCHAR(32),
    st_reason       VARCHAR(500),
    st_explain      TEXT,
    PRIMARY KEY (ts_code, imp_date)
);

-- 6. 沪深港通股票列表
CREATE TABLE IF NOT EXISTS stock_hsgt (
    ts_code         VARCHAR(16) NOT NULL,
    trade_date      DATE NOT NULL,
    type            VARCHAR(8) NOT NULL,
    name            VARCHAR(64),
    type_name       VARCHAR(32),
    PRIMARY KEY (ts_code, trade_date, type)
);

-- 7. 股票曾用名
CREATE TABLE IF NOT EXISTS namechange (
    ts_code         VARCHAR(16) NOT NULL,
    name            VARCHAR(32),
    start_date      DATE,
    end_date        DATE,
    ann_date        DATE,
    change_reason   VARCHAR(128),
    PRIMARY KEY (ts_code, start_date)
);

-- 8. 上市公司基本信息
CREATE TABLE IF NOT EXISTS stock_company (
    ts_code         VARCHAR(16) PRIMARY KEY,
    com_name        VARCHAR(128),
    com_id          VARCHAR(32),
    exchange        VARCHAR(8),
    chairman        VARCHAR(32),
    manager         VARCHAR(32),
    secretary       VARCHAR(32),
    reg_capital     DECIMAL(20,2),
    setup_date      DATE,
    province        VARCHAR(32),
    city            VARCHAR(32),
    introduction    TEXT,
    website         VARCHAR(256),
    email           VARCHAR(128),
    office          VARCHAR(256),
    employees       INTEGER,
    main_business   TEXT,
    business_scope  TEXT
);

-- 9. 上市公司管理层
CREATE TABLE IF NOT EXISTS stk_managers (
    ts_code         VARCHAR(16) NOT NULL,
    ann_date        DATE,
    name            VARCHAR(32),
    gender          VARCHAR(4),
    lev             VARCHAR(32),
    title           VARCHAR(64),
    edu             VARCHAR(16),
    national        VARCHAR(16),
    birthday        VARCHAR(16),
    begin_date      DATE,
    end_date        DATE,
    resume          TEXT,
    PRIMARY KEY (ts_code, name, begin_date)
);

-- 10. 管理层薪酬和持股
CREATE TABLE IF NOT EXISTS stk_rewards (
    ts_code         VARCHAR(16) NOT NULL,
    ann_date        DATE,
    end_date        DATE NOT NULL,
    name            VARCHAR(32),
    title           VARCHAR(64),
    reward          DECIMAL(16,2),
    hold_vol        DECIMAL(20,2),
    PRIMARY KEY (ts_code, name, end_date)
);

-- 11. 北交所新旧代码对照
CREATE TABLE IF NOT EXISTS bse_mapping (
    name            VARCHAR(32),
    o_code          VARCHAR(16) PRIMARY KEY,
    n_code          VARCHAR(16),
    list_date       DATE
);

-- 12. IPO新股列表
CREATE TABLE IF NOT EXISTS new_share (
    ts_code         VARCHAR(16) PRIMARY KEY,
    sub_code        VARCHAR(16),
    name            VARCHAR(32),
    ipo_date        DATE,
    issue_date      DATE,
    amount          DECIMAL(20,2),
    market_amount   DECIMAL(20,2),
    price           DECIMAL(10,2),
    pe              DECIMAL(10,2),
    limit_amount    DECIMAL(10,4),
    funds           DECIMAL(16,2),
    ballot          DECIMAL(10,4)
);

-- 13. 股票历史列表（每日）
CREATE TABLE IF NOT EXISTS bak_basic (
    trade_date      DATE NOT NULL,
    ts_code         VARCHAR(16) NOT NULL,
    name            VARCHAR(32),
    industry        VARCHAR(64),
    area            VARCHAR(32),
    pe              DECIMAL(16,4),
    float_share     DECIMAL(20,4),
    total_share     DECIMAL(20,4),
    total_assets    DECIMAL(20,4),
    liquid_assets   DECIMAL(20,4),
    fixed_assets    DECIMAL(20,4),
    reserved        DECIMAL(20,4),
    reserved_pershare DECIMAL(16,4),
    eps             DECIMAL(16,4),
    bvps            DECIMAL(16,4),
    pb              DECIMAL(16,4),
    list_date       DATE,
    undp            DECIMAL(20,4),
    per_undp        DECIMAL(16,4),
    rev_yoy         DECIMAL(10,2),
    profit_yoy      DECIMAL(10,2),
    gpr             DECIMAL(10,2),
    npr             DECIMAL(10,2),
    holder_num      INTEGER,
    PRIMARY KEY (trade_date, ts_code)
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_stock_st_trade ON stock_st(trade_date);
CREATE INDEX IF NOT EXISTS idx_stock_hsgt_date ON stock_hsgt(trade_date);
CREATE INDEX IF NOT EXISTS idx_namechange_ts ON namechange(ts_code);
CREATE INDEX IF NOT EXISTS idx_stk_managers_ts ON stk_managers(ts_code);
CREATE INDEX IF NOT EXISTS idx_stk_rewards_ts ON stk_rewards(ts_code);
CREATE INDEX IF NOT EXISTS idx_bak_basic_date ON bak_basic(trade_date);
CREATE INDEX IF NOT EXISTS idx_bak_basic_ts ON bak_basic(ts_code);
