-- 两融数据（4个接口）
-- margin, margin_detail, margin_secs, slb_len

CREATE TABLE IF NOT EXISTS margin (
    trade_date   VARCHAR(10) NOT NULL,
    exchange_id  VARCHAR(10) NOT NULL,
    rzye         NUMERIC,
    rzmre        NUMERIC,
    rzche        NUMERIC,
    rqye         NUMERIC,
    rqmcl        NUMERIC,
    rzrqye       NUMERIC,
    rqyl         NUMERIC,
    PRIMARY KEY (trade_date, exchange_id)
);
COMMENT ON TABLE margin IS '融资融券交易汇总';

CREATE TABLE IF NOT EXISTS margin_detail (
    trade_date  VARCHAR(10) NOT NULL,
    ts_code     VARCHAR(20) NOT NULL,
    name        VARCHAR(50),
    rzye        NUMERIC,
    rqye        NUMERIC,
    rzmre       NUMERIC,
    rqyl        NUMERIC,
    rzche       NUMERIC,
    rqchl       NUMERIC,
    rqmcl       NUMERIC,
    rzrqye      NUMERIC,
    PRIMARY KEY (trade_date, ts_code)
);
COMMENT ON TABLE margin_detail IS '融资融券交易明细';

CREATE TABLE IF NOT EXISTS margin_secs (
    trade_date  VARCHAR(10) NOT NULL,
    ts_code     VARCHAR(20) NOT NULL,
    name        VARCHAR(50),
    exchange    VARCHAR(10),
    PRIMARY KEY (trade_date, ts_code)
);
COMMENT ON TABLE margin_secs IS '融资融券标的';

CREATE TABLE IF NOT EXISTS slb_len (
    trade_date   VARCHAR(10) NOT NULL PRIMARY KEY,
    ob           NUMERIC,
    auc_amount   NUMERIC,
    repo_amount  NUMERIC,
    repay_amount NUMERIC,
    cb           NUMERIC
);
COMMENT ON TABLE slb_len IS '转融资交易汇总';
