-- =============================================================================
-- 资金流向数据 8 张建表 SQL
-- =============================================================================
-- Tushare Pro 接口文档：
--   moneyflow        — https://tushare.pro/document/2?doc_id=340
--   moneyflow_ths    — https://tushare.pro/document/2?doc_id=347
--   moneyflow_dc     — https://tushare.pro/document/2?doc_id=349
--   moneyflow_cnt_ths— https://tushare.pro/document/2?doc_id=348
--   moneyflow_ind_ths— https://tushare.pro/document/2?doc_id=264
--   moneyflow_ind_dc — https://tushare.pro/document/2?doc_id=350
--   moneyflow_mkt_dc — https://tushare.pro/document/2?doc_id=351
--   moneyflow_hsgt   — https://tushare.pro/document/2?doc_id=47
-- =============================================================================

-- 1. 个股资金流向
DROP TABLE IF EXISTS moneyflow;
CREATE TABLE moneyflow (
    ts_code         VARCHAR(16)     NOT NULL,
    trade_date      DATE            NOT NULL,
    buy_sm_vol      DECIMAL(20,4),
    buy_sm_amount   DECIMAL(20,4),
    sell_sm_vol     DECIMAL(20,4),
    sell_sm_amount  DECIMAL(20,4),
    buy_md_vol      DECIMAL(20,4),
    buy_md_amount   DECIMAL(20,4),
    sell_md_vol     DECIMAL(20,4),
    sell_md_amount  DECIMAL(20,4),
    buy_lg_vol      DECIMAL(20,4),
    buy_lg_amount   DECIMAL(20,4),
    sell_lg_vol     DECIMAL(20,4),
    sell_lg_amount  DECIMAL(20,4),
    buy_elg_vol     DECIMAL(20,4),
    buy_elg_amount  DECIMAL(20,4),
    sell_elg_vol    DECIMAL(20,4),
    sell_elg_amount DECIMAL(20,4),
    net_mf_vol      DECIMAL(20,4),
    net_mf_amount   DECIMAL(20,4),
    PRIMARY KEY (ts_code, trade_date)
);
COMMENT ON TABLE moneyflow IS '个股资金流向';
COMMENT ON COLUMN moneyflow.ts_code IS 'TS代码';
COMMENT ON COLUMN moneyflow.trade_date IS '交易日';
COMMENT ON COLUMN moneyflow.buy_sm_vol IS '小单买入量（手）';
COMMENT ON COLUMN moneyflow.buy_sm_amount IS '小单买入金额（万元）';
COMMENT ON COLUMN moneyflow.sell_sm_vol IS '小单卖出量（手）';
COMMENT ON COLUMN moneyflow.sell_sm_amount IS '小单卖出金额（万元）';
COMMENT ON COLUMN moneyflow.buy_md_vol IS '中单买入量（手）';
COMMENT ON COLUMN moneyflow.buy_md_amount IS '中单买入金额（万元）';
COMMENT ON COLUMN moneyflow.sell_md_vol IS '中单卖出量（手）';
COMMENT ON COLUMN moneyflow.sell_md_amount IS '中单卖出金额（万元）';
COMMENT ON COLUMN moneyflow.buy_lg_vol IS '大单买入量（手）';
COMMENT ON COLUMN moneyflow.buy_lg_amount IS '大单买入金额（万元）';
COMMENT ON COLUMN moneyflow.sell_lg_vol IS '大单卖出量（手）';
COMMENT ON COLUMN moneyflow.sell_lg_amount IS '大单卖出金额（万元）';
COMMENT ON COLUMN moneyflow.buy_elg_vol IS '特大单买入量（手）';
COMMENT ON COLUMN moneyflow.buy_elg_amount IS '特大单买入金额（万元）';
COMMENT ON COLUMN moneyflow.sell_elg_vol IS '特大单卖出量（手）';
COMMENT ON COLUMN moneyflow.sell_elg_amount IS '特大单卖出金额（万元）';
COMMENT ON COLUMN moneyflow.net_mf_vol IS '净流量（手）';
COMMENT ON COLUMN moneyflow.net_mf_amount IS '净流量（万元）';


-- 2. 个股资金流向（同花顺）
DROP TABLE IF EXISTS moneyflow_ths;
CREATE TABLE moneyflow_ths (
    trade_date          DATE            NOT NULL,
    ts_code             VARCHAR(16)     NOT NULL,
    name                VARCHAR(32),
    pct_change          DECIMAL(10,2),
    latest              DECIMAL(16,4),
    net_amount          DECIMAL(20,4),
    net_d5_amount       DECIMAL(20,4),
    buy_lg_amount       DECIMAL(20,4),
    buy_lg_amount_rate  DECIMAL(10,4),
    buy_md_amount       DECIMAL(20,4),
    buy_md_amount_rate  DECIMAL(10,4),
    buy_sm_amount       DECIMAL(20,4),
    buy_sm_amount_rate  DECIMAL(10,4),
    PRIMARY KEY (ts_code, trade_date)
);
COMMENT ON TABLE moneyflow_ths IS '个股资金流向（同花顺）';
COMMENT ON COLUMN moneyflow_ths.trade_date IS '交易日期';
COMMENT ON COLUMN moneyflow_ths.ts_code IS 'TS代码';
COMMENT ON COLUMN moneyflow_ths.name IS '股票名称';
COMMENT ON COLUMN moneyflow_ths.pct_change IS '涨跌幅';
COMMENT ON COLUMN moneyflow_ths.latest IS '最新价';
COMMENT ON COLUMN moneyflow_ths.net_amount IS '主力净额（万元）';
COMMENT ON COLUMN moneyflow_ths.net_d5_amount IS '5日主力净额（万元）';
COMMENT ON COLUMN moneyflow_ths.buy_lg_amount IS '大单买入净额（万元）';
COMMENT ON COLUMN moneyflow_ths.buy_lg_amount_rate IS '大单买入占比';
COMMENT ON COLUMN moneyflow_ths.buy_md_amount IS '中单买入净额（万元）';
COMMENT ON COLUMN moneyflow_ths.buy_md_amount_rate IS '中单买入占比';
COMMENT ON COLUMN moneyflow_ths.buy_sm_amount IS '小单买入净额（万元）';
COMMENT ON COLUMN moneyflow_ths.buy_sm_amount_rate IS '小单买入占比';


-- 3. 个股资金流向（东方财富 DC）
DROP TABLE IF EXISTS moneyflow_dc;
CREATE TABLE moneyflow_dc (
    trade_date          DATE            NOT NULL,
    ts_code             VARCHAR(16)     NOT NULL,
    name                VARCHAR(32),
    pct_change          DECIMAL(10,2),
    close               DECIMAL(16,4),
    net_amount          DECIMAL(20,4),
    net_amount_rate     DECIMAL(10,4),
    buy_elg_amount      DECIMAL(20,4),
    buy_elg_amount_rate DECIMAL(10,4),
    buy_lg_amount       DECIMAL(20,4),
    buy_lg_amount_rate  DECIMAL(10,4),
    buy_md_amount       DECIMAL(20,4),
    buy_md_amount_rate  DECIMAL(10,4),
    buy_sm_amount       DECIMAL(20,4),
    buy_sm_amount_rate  DECIMAL(10,4),
    PRIMARY KEY (ts_code, trade_date)
);
COMMENT ON TABLE moneyflow_dc IS '个股资金流向（东方财富 DC）';
COMMENT ON COLUMN moneyflow_dc.trade_date IS '交易日期';
COMMENT ON COLUMN moneyflow_dc.ts_code IS 'TS代码';
COMMENT ON COLUMN moneyflow_dc.name IS '股票名称';
COMMENT ON COLUMN moneyflow_dc.pct_change IS '涨跌幅';
COMMENT ON COLUMN moneyflow_dc.close IS '收盘价';
COMMENT ON COLUMN moneyflow_dc.net_amount IS '主力净额（万元）';
COMMENT ON COLUMN moneyflow_dc.net_amount_rate IS '主力净额占比';
COMMENT ON COLUMN moneyflow_dc.buy_elg_amount IS '超大单净额（万元）';
COMMENT ON COLUMN moneyflow_dc.buy_elg_amount_rate IS '超大单占比';
COMMENT ON COLUMN moneyflow_dc.buy_lg_amount IS '大单净额（万元）';
COMMENT ON COLUMN moneyflow_dc.buy_lg_amount_rate IS '大单占比';
COMMENT ON COLUMN moneyflow_dc.buy_md_amount IS '中单净额（万元）';
COMMENT ON COLUMN moneyflow_dc.buy_md_amount_rate IS '中单占比';
COMMENT ON COLUMN moneyflow_dc.buy_sm_amount IS '小单净额（万元）';
COMMENT ON COLUMN moneyflow_dc.buy_sm_amount_rate IS '小单占比';


-- 4. 同花顺概念板块资金流向
DROP TABLE IF EXISTS moneyflow_cnt_ths;
CREATE TABLE moneyflow_cnt_ths (
    trade_date          DATE            NOT NULL,
    ts_code             VARCHAR(16)     NOT NULL,
    name                VARCHAR(64),
    lead_stock          VARCHAR(32),
    close_price         DECIMAL(16,4),
    pct_change          DECIMAL(10,2),
    industry_index      DECIMAL(16,4),
    company_num         INTEGER,
    pct_change_stock    VARCHAR(32),
    net_buy_amount      DECIMAL(20,4),
    net_sell_amount     DECIMAL(20,4),
    net_amount          DECIMAL(20,4),
    PRIMARY KEY (ts_code, trade_date)
);
COMMENT ON TABLE moneyflow_cnt_ths IS '同花顺概念板块资金流向';
COMMENT ON COLUMN moneyflow_cnt_ths.trade_date IS '交易日期';
COMMENT ON COLUMN moneyflow_cnt_ths.ts_code IS '板块代码';
COMMENT ON COLUMN moneyflow_cnt_ths.name IS '板块名称';
COMMENT ON COLUMN moneyflow_cnt_ths.lead_stock IS '领涨股票';
COMMENT ON COLUMN moneyflow_cnt_ths.close_price IS '板块指数';
COMMENT ON COLUMN moneyflow_cnt_ths.pct_change IS '板块涨跌幅';
COMMENT ON COLUMN moneyflow_cnt_ths.industry_index IS '板块指数（原始字段）';
COMMENT ON COLUMN moneyflow_cnt_ths.company_num IS '公司数量';
COMMENT ON COLUMN moneyflow_cnt_ths.pct_change_stock IS '涨跌股数';
COMMENT ON COLUMN moneyflow_cnt_ths.net_buy_amount IS '主动买入额（万元）';
COMMENT ON COLUMN moneyflow_cnt_ths.net_sell_amount IS '主动卖出额（万元）';
COMMENT ON COLUMN moneyflow_cnt_ths.net_amount IS '净流入额（万元）';


-- 5. 同花顺行业资金流向
DROP TABLE IF EXISTS moneyflow_ind_ths;
CREATE TABLE moneyflow_ind_ths (
    trade_date          DATE            NOT NULL,
    ts_code             VARCHAR(16)     NOT NULL,
    industry            VARCHAR(64),
    lead_stock          VARCHAR(32),
    close               DECIMAL(16,4),
    pct_change          DECIMAL(10,2),
    company_num         INTEGER,
    pct_change_stock    VARCHAR(32),
    close_price         DECIMAL(16,4),
    net_buy_amount      DECIMAL(20,4),
    net_sell_amount     DECIMAL(20,4),
    net_amount          DECIMAL(20,4),
    PRIMARY KEY (ts_code, trade_date)
);
COMMENT ON TABLE moneyflow_ind_ths IS '同花顺行业资金流向';
COMMENT ON COLUMN moneyflow_ind_ths.trade_date IS '交易日期';
COMMENT ON COLUMN moneyflow_ind_ths.ts_code IS '板块代码';
COMMENT ON COLUMN moneyflow_ind_ths.industry IS '行业名称';
COMMENT ON COLUMN moneyflow_ind_ths.lead_stock IS '领涨股票';
COMMENT ON COLUMN moneyflow_ind_ths.close IS '板块指数';
COMMENT ON COLUMN moneyflow_ind_ths.pct_change IS '板块涨跌幅';
COMMENT ON COLUMN moneyflow_ind_ths.company_num IS '公司数量';
COMMENT ON COLUMN moneyflow_ind_ths.pct_change_stock IS '涨跌股数';
COMMENT ON COLUMN moneyflow_ind_ths.close_price IS '板块指数（原始字段）';
COMMENT ON COLUMN moneyflow_ind_ths.net_buy_amount IS '主动买入额（万元）';
COMMENT ON COLUMN moneyflow_ind_ths.net_sell_amount IS '主动卖出额（万元）';
COMMENT ON COLUMN moneyflow_ind_ths.net_amount IS '净流入额（万元）';


-- 6. 东财板块资金流向（行业+概念，由 content_type 区分）
DROP TABLE IF EXISTS moneyflow_ind_dc;
CREATE TABLE moneyflow_ind_dc (
    trade_date              DATE            NOT NULL,
    content_type            VARCHAR(16)     NOT NULL,
    ts_code                 VARCHAR(16)     NOT NULL,
    name                    VARCHAR(64),
    pct_change              DECIMAL(10,2),
    close                   DECIMAL(16,4),
    net_amount              DECIMAL(20,4),
    net_amount_rate         DECIMAL(10,4),
    buy_elg_amount          DECIMAL(20,4),
    buy_elg_amount_rate     DECIMAL(10,4),
    buy_lg_amount           DECIMAL(20,4),
    buy_lg_amount_rate      DECIMAL(10,4),
    buy_md_amount           DECIMAL(20,4),
    buy_md_amount_rate      DECIMAL(10,4),
    buy_sm_amount           DECIMAL(20,4),
    buy_sm_amount_rate      DECIMAL(10,4),
    buy_sm_amount_stock     DECIMAL(20,4),
    rank                    INTEGER,
    PRIMARY KEY (ts_code, trade_date, content_type)
);
COMMENT ON TABLE moneyflow_ind_dc IS '东财板块资金流向';
COMMENT ON COLUMN moneyflow_ind_dc.trade_date IS '交易日期';
COMMENT ON COLUMN moneyflow_ind_dc.content_type IS '内容类型（行业/概念）';
COMMENT ON COLUMN moneyflow_ind_dc.ts_code IS '板块代码';
COMMENT ON COLUMN moneyflow_ind_dc.name IS '板块名称';
COMMENT ON COLUMN moneyflow_ind_dc.pct_change IS '涨跌幅';
COMMENT ON COLUMN moneyflow_ind_dc.close IS '收盘价';
COMMENT ON COLUMN moneyflow_ind_dc.net_amount IS '主力净额（万元）';
COMMENT ON COLUMN moneyflow_ind_dc.net_amount_rate IS '主力净额占比';
COMMENT ON COLUMN moneyflow_ind_dc.buy_elg_amount IS '超大单净额（万元）';
COMMENT ON COLUMN moneyflow_ind_dc.buy_elg_amount_rate IS '超大单占比';
COMMENT ON COLUMN moneyflow_ind_dc.buy_lg_amount IS '大单净额（万元）';
COMMENT ON COLUMN moneyflow_ind_dc.buy_lg_amount_rate IS '大单占比';
COMMENT ON COLUMN moneyflow_ind_dc.buy_md_amount IS '中单净额（万元）';
COMMENT ON COLUMN moneyflow_ind_dc.buy_md_amount_rate IS '中单占比';
COMMENT ON COLUMN moneyflow_ind_dc.buy_sm_amount IS '小单净额（万元）';
COMMENT ON COLUMN moneyflow_ind_dc.buy_sm_amount_rate IS '小单占比';
COMMENT ON COLUMN moneyflow_ind_dc.buy_sm_amount_stock IS '小单净额股票（万元）';
COMMENT ON COLUMN moneyflow_ind_dc.rank IS '排名';


-- 7. 大盘资金流向（东方财富 DC）
DROP TABLE IF EXISTS moneyflow_mkt_dc;
CREATE TABLE moneyflow_mkt_dc (
    trade_date              DATE            NOT NULL PRIMARY KEY,
    close_sh                DECIMAL(16,4),
    pct_change_sh           DECIMAL(10,2),
    close_sz                DECIMAL(16,4),
    pct_change_sz           DECIMAL(10,2),
    net_amount              DECIMAL(20,4),
    net_amount_rate         DECIMAL(10,4),
    buy_elg_amount          DECIMAL(20,4),
    buy_elg_amount_rate     DECIMAL(10,4),
    buy_lg_amount           DECIMAL(20,4),
    buy_lg_amount_rate      DECIMAL(10,4),
    buy_md_amount           DECIMAL(20,4),
    buy_md_amount_rate      DECIMAL(10,4),
    buy_sm_amount           DECIMAL(20,4),
    buy_sm_amount_rate      DECIMAL(10,4)
);
COMMENT ON TABLE moneyflow_mkt_dc IS '大盘资金流向（东方财富 DC）';
COMMENT ON COLUMN moneyflow_mkt_dc.trade_date IS '交易日期';
COMMENT ON COLUMN moneyflow_mkt_dc.close_sh IS '上证指数收盘';
COMMENT ON COLUMN moneyflow_mkt_dc.pct_change_sh IS '上证指数涨跌幅';
COMMENT ON COLUMN moneyflow_mkt_dc.close_sz IS '深证成指收盘';
COMMENT ON COLUMN moneyflow_mkt_dc.pct_change_sz IS '深证成指涨跌幅';
COMMENT ON COLUMN moneyflow_mkt_dc.net_amount IS '主力净额（万元）';
COMMENT ON COLUMN moneyflow_mkt_dc.net_amount_rate IS '主力净额占比';
COMMENT ON COLUMN moneyflow_mkt_dc.buy_elg_amount IS '超大单净额（万元）';
COMMENT ON COLUMN moneyflow_mkt_dc.buy_elg_amount_rate IS '超大单占比';
COMMENT ON COLUMN moneyflow_mkt_dc.buy_lg_amount IS '大单净额（万元）';
COMMENT ON COLUMN moneyflow_mkt_dc.buy_lg_amount_rate IS '大单占比';
COMMENT ON COLUMN moneyflow_mkt_dc.buy_md_amount IS '中单净额（万元）';
COMMENT ON COLUMN moneyflow_mkt_dc.buy_md_amount_rate IS '中单占比';
COMMENT ON COLUMN moneyflow_mkt_dc.buy_sm_amount IS '小单净额（万元）';
COMMENT ON COLUMN moneyflow_mkt_dc.buy_sm_amount_rate IS '小单占比';


-- 8. 沪深港通资金流向
DROP TABLE IF EXISTS moneyflow_hsgt;
CREATE TABLE moneyflow_hsgt (
    trade_date      DATE            NOT NULL PRIMARY KEY,
    ggt_ss          DECIMAL(20,4),
    ggt_sz          DECIMAL(20,4),
    hgt             DECIMAL(20,4),
    sgt             DECIMAL(20,4),
    north_money     DECIMAL(20,4),
    south_money     DECIMAL(20,4)
);
COMMENT ON TABLE moneyflow_hsgt IS '沪深港通资金流向';
COMMENT ON COLUMN moneyflow_hsgt.trade_date IS '交易日期';
COMMENT ON COLUMN moneyflow_hsgt.ggt_ss IS '港股通（沪）当日额度余额（亿元）';
COMMENT ON COLUMN moneyflow_hsgt.ggt_sz IS '港股通（深）当日额度余额（亿元）';
COMMENT ON COLUMN moneyflow_hsgt.hgt IS '沪股通当日额度余额（亿元）';
COMMENT ON COLUMN moneyflow_hsgt.sgt IS '深股通当日额度余额（亿元）';
COMMENT ON COLUMN moneyflow_hsgt.north_money IS '北向资金流入（亿元）';
COMMENT ON COLUMN moneyflow_hsgt.south_money IS '南向资金流入（亿元）';
