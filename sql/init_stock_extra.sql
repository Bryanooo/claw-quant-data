-- =============================================================================
-- 股票特色数据表 — 13 张表
-- 包括：卖方盈利预测、筹码分布、技术面因子、港股通、集合竞价、机构调研等
-- =============================================================================

-- 1. report_rc: 卖方盈利预测数据
CREATE TABLE IF NOT EXISTS report_rc (
    ts_code      VARCHAR(16)    NOT NULL,
    name         VARCHAR(64),
    report_date  DATE           NOT NULL,
    report_title VARCHAR(256),
    report_type  VARCHAR(16),
    classify     VARCHAR(32),
    org_name     VARCHAR(128),
    author_name  VARCHAR(128),
    quarter      VARCHAR(16)    NOT NULL,
    op_rt        NUMERIC(20,4),
    op_pr        NUMERIC(20,4),
    tp           NUMERIC(20,4),
    np           NUMERIC(20,4),
    eps          NUMERIC(12,4),
    pe           NUMERIC(12,4),
    rd           NUMERIC(12,4),
    roe          NUMERIC(12,4),
    ev_ebitda    NUMERIC(20,4),
    rating       VARCHAR(16),
    max_price    NUMERIC(12,4),
    min_price    NUMERIC(12,4),
    imp_dg       VARCHAR(16),
    create_time  TIMESTAMP      NOT NULL DEFAULT NOW(),
    PRIMARY KEY (ts_code, report_date, quarter)
);

CREATE INDEX IF NOT EXISTS idx_report_rc_date ON report_rc (report_date);
CREATE INDEX IF NOT EXISTS idx_report_rc_code ON report_rc (ts_code);

-- 2. cyq_perf: 每日筹码及胜率
CREATE TABLE IF NOT EXISTS cyq_perf (
    ts_code     VARCHAR(16)  NOT NULL,
    trade_date  DATE         NOT NULL,
    his_low     NUMERIC(12,4),
    his_high    NUMERIC(12,4),
    cost_5pct   NUMERIC(12,4),
    cost_15pct  NUMERIC(12,4),
    cost_50pct  NUMERIC(12,4),
    cost_85pct  NUMERIC(12,4),
    cost_95pct  NUMERIC(12,4),
    weight_avg  NUMERIC(12,4),
    winner_rate NUMERIC(10,4),
    created_at  TIMESTAMP    NOT NULL DEFAULT NOW(),
    PRIMARY KEY (ts_code, trade_date)
);

CREATE INDEX IF NOT EXISTS idx_cyq_perf_date ON cyq_perf (trade_date);
CREATE INDEX IF NOT EXISTS idx_cyq_perf_code ON cyq_perf (ts_code);

-- 3. cyq_chips: 每日筹码分布
CREATE TABLE IF NOT EXISTS cyq_chips (
    ts_code    VARCHAR(16)  NOT NULL,
    trade_date DATE         NOT NULL,
    price      NUMERIC(12,4) NOT NULL,
    percent    NUMERIC(10,4),
    created_at TIMESTAMP    NOT NULL DEFAULT NOW(),
    PRIMARY KEY (ts_code, trade_date, price)
);

CREATE INDEX IF NOT EXISTS idx_cyq_chips_date ON cyq_chips (trade_date);
CREATE INDEX IF NOT EXISTS idx_cyq_chips_code ON cyq_chips (ts_code);

-- 4. stk_factor_pro: 股票技术面因子（专业版）
CREATE TABLE IF NOT EXISTS stk_factor_pro (
    ts_code        VARCHAR(16)  NOT NULL,
    trade_date     DATE         NOT NULL,
    open           NUMERIC(12,4),
    open_hfq       NUMERIC(12,4),
    open_qfq       NUMERIC(12,4),
    high           NUMERIC(12,4),
    high_hfq       NUMERIC(12,4),
    high_qfq       NUMERIC(12,4),
    low            NUMERIC(12,4),
    low_hfq        NUMERIC(12,4),
    low_qfq        NUMERIC(12,4),
    close          NUMERIC(12,4),
    close_hfq      NUMERIC(12,4),
    close_qfq      NUMERIC(12,4),
    pre_close      NUMERIC(12,4),
    change         NUMERIC(12,4),
    pct_chg        NUMERIC(12,4),
    vol            NUMERIC(20,4),
    amount         NUMERIC(20,4),
    turnover_rate  NUMERIC(12,4),
    turnover_rate_f NUMERIC(12,4),
    volume_ratio   NUMERIC(12,4),
    pe             NUMERIC(12,4),
    pe_ttm         NUMERIC(12,4),
    pb             NUMERIC(12,4),
    ps             NUMERIC(12,4),
    ps_ttm         NUMERIC(12,4),
    dv_ratio       NUMERIC(12,4),
    dv_ttm         NUMERIC(12,4),
    total_share    NUMERIC(20,4),
    float_share    NUMERIC(20,4),
    free_share     NUMERIC(20,4),
    total_mv       NUMERIC(20,4),
    circ_mv        NUMERIC(20,4),
    adj_factor     NUMERIC(12,4),
    created_at     TIMESTAMP    NOT NULL DEFAULT NOW(),
    PRIMARY KEY (ts_code, trade_date)
);

CREATE INDEX IF NOT EXISTS idx_stk_factor_pro_date ON stk_factor_pro (trade_date);
CREATE INDEX IF NOT EXISTS idx_stk_factor_pro_code ON stk_factor_pro (ts_code);

-- 5. ccass_hold: 中央结算系统持股汇总
CREATE TABLE IF NOT EXISTS ccass_hold (
    trade_date   DATE         NOT NULL,
    ts_code      VARCHAR(16)  NOT NULL,
    name         VARCHAR(64),
    shareholding NUMERIC(20,4),
    hold_nums    NUMERIC(10),
    hold_ratio   NUMERIC(10,4),
    created_at   TIMESTAMP    NOT NULL DEFAULT NOW(),
    PRIMARY KEY (ts_code, trade_date)
);

CREATE INDEX IF NOT EXISTS idx_ccass_hold_date ON ccass_hold (trade_date);
CREATE INDEX IF NOT EXISTS idx_ccass_hold_code ON ccass_hold (ts_code);

-- 6. ccass_hold_detail: 中央结算系统持股明细
CREATE TABLE IF NOT EXISTS ccass_hold_detail (
    trade_date               DATE         NOT NULL,
    ts_code                  VARCHAR(16)  NOT NULL,
    name                     VARCHAR(64),
    col_participant_id       VARCHAR(32)  NOT NULL,
    col_participant_name     VARCHAR(128),
    col_shareholding         NUMERIC(20,4),
    col_shareholding_percent NUMERIC(10,4),
    created_at               TIMESTAMP    NOT NULL DEFAULT NOW(),
    PRIMARY KEY (ts_code, trade_date, col_participant_id)
);

CREATE INDEX IF NOT EXISTS idx_ccass_hold_detail_date ON ccass_hold_detail (trade_date);
CREATE INDEX IF NOT EXISTS idx_ccass_hold_detail_code ON ccass_hold_detail (ts_code);

-- 7. hk_hold: 沪深港股通持股明细
CREATE TABLE IF NOT EXISTS hk_hold (
    code       VARCHAR(16)  NOT NULL,
    trade_date DATE         NOT NULL,
    ts_code    VARCHAR(16)  NOT NULL,
    name       VARCHAR(64),
    vol        NUMERIC(20,4),
    ratio      NUMERIC(10,4),
    exchange   VARCHAR(8),
    created_at TIMESTAMP    NOT NULL DEFAULT NOW(),
    PRIMARY KEY (ts_code, trade_date)
);

CREATE INDEX IF NOT EXISTS idx_hk_hold_date ON hk_hold (trade_date);
CREATE INDEX IF NOT EXISTS idx_hk_hold_code ON hk_hold (ts_code);

-- 8. stk_auction_o: 股票开盘集合竞价
CREATE TABLE IF NOT EXISTS stk_auction_o (
    ts_code    VARCHAR(16)  NOT NULL,
    trade_date DATE         NOT NULL,
    close      NUMERIC(12,4),
    open       NUMERIC(12,4),
    high       NUMERIC(12,4),
    low        NUMERIC(12,4),
    vol        NUMERIC(20,4),
    amount     NUMERIC(20,4),
    vwap       NUMERIC(12,4),
    created_at TIMESTAMP    NOT NULL DEFAULT NOW(),
    PRIMARY KEY (ts_code, trade_date)
);

CREATE INDEX IF NOT EXISTS idx_stk_auction_o_date ON stk_auction_o (trade_date);
CREATE INDEX IF NOT EXISTS idx_stk_auction_o_code ON stk_auction_o (ts_code);

-- 9. stk_auction_c: 股票收盘集合竞价
CREATE TABLE IF NOT EXISTS stk_auction_c (
    ts_code    VARCHAR(16)  NOT NULL,
    trade_date DATE         NOT NULL,
    close      NUMERIC(12,4),
    open       NUMERIC(12,4),
    high       NUMERIC(12,4),
    low        NUMERIC(12,4),
    vol        NUMERIC(20,4),
    amount     NUMERIC(20,4),
    vwap       NUMERIC(12,4),
    created_at TIMESTAMP    NOT NULL DEFAULT NOW(),
    PRIMARY KEY (ts_code, trade_date)
);

CREATE INDEX IF NOT EXISTS idx_stk_auction_c_date ON stk_auction_c (trade_date);
CREATE INDEX IF NOT EXISTS idx_stk_auction_c_code ON stk_auction_c (ts_code);

-- 10. stk_nineturn: 神奇九转指标
CREATE TABLE IF NOT EXISTS stk_nineturn (
    ts_code       VARCHAR(16)  NOT NULL,
    trade_date    DATE         NOT NULL,
    freq          VARCHAR(8)   NOT NULL,
    open          NUMERIC(12,4),
    high          NUMERIC(12,4),
    low           NUMERIC(12,4),
    close         NUMERIC(12,4),
    vol           NUMERIC(20,4),
    amount        NUMERIC(20,4),
    up_count      NUMERIC(4),
    down_count    NUMERIC(4),
    nine_up_turn  NUMERIC(4),
    nine_down_turn NUMERIC(4),
    created_at    TIMESTAMP    NOT NULL DEFAULT NOW(),
    PRIMARY KEY (ts_code, trade_date, freq)
);

CREATE INDEX IF NOT EXISTS idx_stk_nineturn_date ON stk_nineturn (trade_date);
CREATE INDEX IF NOT EXISTS idx_stk_nineturn_code ON stk_nineturn (ts_code);

-- 11. stk_ah_comparison: AH股比价
CREATE TABLE IF NOT EXISTS stk_ah_comparison (
    hk_code      VARCHAR(16)  NOT NULL,
    ts_code      VARCHAR(16)  NOT NULL,
    trade_date   DATE         NOT NULL,
    hk_name      VARCHAR(64),
    hk_pct_chg   NUMERIC(12,4),
    hk_close     NUMERIC(12,4),
    name         VARCHAR(64),
    close        NUMERIC(12,4),
    pct_chg      NUMERIC(12,4),
    ah_comparison NUMERIC(12,4),
    ah_premium   NUMERIC(12,4),
    created_at   TIMESTAMP    NOT NULL DEFAULT NOW(),
    PRIMARY KEY (ts_code, hk_code, trade_date)
);

CREATE INDEX IF NOT EXISTS idx_stk_ah_comparison_date ON stk_ah_comparison (trade_date);
CREATE INDEX IF NOT EXISTS idx_stk_ah_comparison_code ON stk_ah_comparison (ts_code);

-- 12. stk_surv: 机构调研表
CREATE TABLE IF NOT EXISTS stk_surv (
    ts_code       VARCHAR(16)   NOT NULL,
    name          VARCHAR(64),
    surv_date     DATE          NOT NULL,
    fund_visitors VARCHAR(32)   NOT NULL,
    rece_place    VARCHAR(256),
    rece_mode     VARCHAR(64),
    rece_org      VARCHAR(256)  NOT NULL,
    org_type      VARCHAR(32),
    comp_rece     VARCHAR(128),
    content       TEXT,
    created_at    TIMESTAMP     NOT NULL DEFAULT NOW(),
    PRIMARY KEY (ts_code, surv_date, fund_visitors, rece_org)
);

CREATE INDEX IF NOT EXISTS idx_stk_surv_date ON stk_surv (surv_date);
CREATE INDEX IF NOT EXISTS idx_stk_surv_code ON stk_surv (ts_code);

-- 13. broker_recommend: 券商每月荐股
CREATE TABLE IF NOT EXISTS broker_recommend (
    month     VARCHAR(8)   NOT NULL,
    broker    VARCHAR(128) NOT NULL,
    ts_code   VARCHAR(16)  NOT NULL,
    name      VARCHAR(64),
    created_at TIMESTAMP   NOT NULL DEFAULT NOW(),
    PRIMARY KEY (month, broker, ts_code)
);

CREATE INDEX IF NOT EXISTS idx_broker_recommend_month ON broker_recommend (month);
CREATE INDEX IF NOT EXISTS idx_broker_recommend_code ON broker_recommend (ts_code);
