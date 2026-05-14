-- =============================================================================
-- 打板 / 板块 / 热榜 数据表创建（23 张表）
-- =============================================================================
-- 使用说明：
--   psql -h <host> -U <user> -d <dbname> -f sql/init_board.sql

-- =============================================================================
-- 1. top_list — 龙虎榜每日明细
-- =============================================================================
CREATE TABLE IF NOT EXISTS top_list (
    trade_date     VARCHAR(8)   NOT NULL,
    ts_code        VARCHAR(16)  NOT NULL,
    name           VARCHAR(64),
    close          NUMERIC(12,2),
    pct_change     NUMERIC(8,3),
    turnover_rate  NUMERIC(8,3),
    amount         NUMERIC(18,2),
    l_sell         NUMERIC(18,2),
    l_buy          NUMERIC(18,2),
    l_amount       NUMERIC(18,2),
    net_amount     NUMERIC(18,2),
    net_rate       NUMERIC(8,3),
    amount_rate    NUMERIC(8,3),
    float_values   NUMERIC(18,2),
    reason         TEXT,
    PRIMARY KEY (ts_code, trade_date)
);
COMMENT ON TABLE  top_list         IS '龙虎榜每日明细';
COMMENT ON COLUMN top_list.trade_date   IS '交易日期';
COMMENT ON COLUMN top_list.ts_code      IS '股票代码';
COMMENT ON COLUMN top_list.name         IS '股票名称';
COMMENT ON COLUMN top_list.close        IS '收盘价';
COMMENT ON COLUMN top_list.pct_change   IS '涨跌幅%';
COMMENT ON COLUMN top_list.turnover_rate IS '换手率%';
COMMENT ON COLUMN top_list.amount       IS '总成交额(万)';
COMMENT ON COLUMN top_list.l_sell       IS '龙虎榜卖出额(万)';
COMMENT ON COLUMN top_list.l_buy        IS '龙虎榜买入额(万)';
COMMENT ON COLUMN top_list.l_amount     IS '龙虎榜成交额(万)';
COMMENT ON COLUMN top_list.net_amount   IS '龙虎榜净买入额(万)';
COMMENT ON COLUMN top_list.net_rate     IS '龙虎榜净买额占比%';
COMMENT ON COLUMN top_list.amount_rate  IS '龙虎榜成交额占比%';
COMMENT ON COLUMN top_list.float_values IS '当日流通市值(万)';
COMMENT ON COLUMN top_list.reason       IS '上榜原因';

-- =============================================================================
-- 2. top_inst — 龙虎榜机构明细
-- =============================================================================
CREATE TABLE IF NOT EXISTS top_inst (
    trade_date    VARCHAR(8)   NOT NULL,
    ts_code       VARCHAR(16)  NOT NULL,
    exalter       VARCHAR(128) NOT NULL,
    side          VARCHAR(8)   NOT NULL,
    buy           NUMERIC(18,2),
    buy_rate      NUMERIC(8,3),
    sell          NUMERIC(18,2),
    sell_rate     NUMERIC(8,3),
    net_buy       NUMERIC(18,2),
    reason        TEXT,
    PRIMARY KEY (ts_code, trade_date, exalter, side)
);
COMMENT ON TABLE  top_inst          IS '龙虎榜机构明细';
COMMENT ON COLUMN top_inst.trade_date IS '交易日期';
COMMENT ON COLUMN top_inst.ts_code    IS '股票代码';
COMMENT ON COLUMN top_inst.exalter    IS '营业部/机构名称';
COMMENT ON COLUMN top_inst.side       IS '买卖类型 BUY/SELL';
COMMENT ON COLUMN top_inst.buy        IS '买入金额(万)';
COMMENT ON COLUMN top_inst.buy_rate   IS '买入占比%';
COMMENT ON COLUMN top_inst.sell       IS '卖出金额(万)';
COMMENT ON COLUMN top_inst.sell_rate  IS '卖出占比%';
COMMENT ON COLUMN top_inst.net_buy    IS '净买入金额(万)';
COMMENT ON COLUMN top_inst.reason     IS '上榜原因';

-- =============================================================================
-- 3. limit_list_d — 涨跌停列表（新）
-- =============================================================================
CREATE TABLE IF NOT EXISTS limit_list_d (
    trade_date     VARCHAR(8)   NOT NULL,
    ts_code        VARCHAR(16)  NOT NULL,
    industry       VARCHAR(64),
    name           VARCHAR(64),
    close          NUMERIC(12,2),
    pct_chg        NUMERIC(8,3),
    amount         NUMERIC(18,2),
    limit_amount   NUMERIC(18,2),
    float_mv       NUMERIC(18,2),
    total_mv       NUMERIC(18,2),
    turnover_ratio NUMERIC(8,3),
    fd_amount      NUMERIC(18,2),
    first_time     VARCHAR(8),
    last_time      VARCHAR(8),
    open_times     INTEGER,
    up_stat        VARCHAR(4),
    limit_times    INTEGER,
    limit          VARCHAR(2),
    PRIMARY KEY (ts_code, trade_date, limit_type)
);
COMMENT ON TABLE  limit_list_d          IS '涨跌停列表';
COMMENT ON COLUMN limit_list_d.trade_date IS '交易日期';
COMMENT ON COLUMN limit_list_d.ts_code    IS '股票代码';
COMMENT ON COLUMN limit_list_d.industry   IS '所属行业';
COMMENT ON COLUMN limit_list_d.name       IS '股票名称';
COMMENT ON COLUMN limit_list_d.close      IS '收盘价';
COMMENT ON COLUMN limit_list_d.pct_chg    IS '涨跌幅%';
COMMENT ON COLUMN limit_list_d.amount     IS '成交额(元)';
COMMENT ON COLUMN limit_list_d.limit_amount IS '封单资金额(元)';
COMMENT ON COLUMN limit_list_d.float_mv   IS '流通市值(元)';
COMMENT ON COLUMN limit_list_d.total_mv   IS '总市值(元)';
COMMENT ON COLUMN limit_list_d.turnover_ratio IS '换手率%';
COMMENT ON COLUMN limit_list_d.fd_amount  IS '封单金额';
COMMENT ON COLUMN limit_list_d.first_time IS '首次封板时间';
COMMENT ON COLUMN limit_list_d.last_time  IS '最后封板时间';
COMMENT ON COLUMN limit_list_d.open_times IS '炸板次数';
COMMENT ON COLUMN limit_list_d.up_stat    IS '涨停状态';
COMMENT ON COLUMN limit_list_d.limit_times IS '连板数';
COMMENT ON COLUMN limit_list_d.limit      IS '涨跌停类型';

-- Add limit_type column to limit_list_d for PK
ALTER TABLE limit_list_d ADD COLUMN IF NOT EXISTS limit_type VARCHAR(4) DEFAULT 'D';

-- =============================================================================
-- 4. limit_step — 连板天梯
-- =============================================================================
CREATE TABLE IF NOT EXISTS limit_step (
    trade_date VARCHAR(8)  NOT NULL,
    ts_code    VARCHAR(16) NOT NULL,
    name       VARCHAR(64),
    nums       INTEGER,
    PRIMARY KEY (ts_code, trade_date)
);
COMMENT ON TABLE  limit_step          IS '连板天梯';
COMMENT ON COLUMN limit_step.trade_date IS '交易日期';
COMMENT ON COLUMN limit_step.ts_code    IS '股票代码';
COMMENT ON COLUMN limit_step.name       IS '股票名称';
COMMENT ON COLUMN limit_step.nums       IS '连板天数';

-- =============================================================================
-- 5. limit_cpt_list — 最强板块统计
-- =============================================================================
CREATE TABLE IF NOT EXISTS limit_cpt_list (
    trade_date VARCHAR(8)  NOT NULL,
    ts_code    VARCHAR(16) NOT NULL,
    name       VARCHAR(64),
    days       INTEGER,
    up_stat    VARCHAR(4),
    cons_nums  INTEGER,
    up_nums    INTEGER,
    pct_chg    NUMERIC(8,3),
    rank       INTEGER,
    PRIMARY KEY (ts_code, trade_date)
);
COMMENT ON TABLE  limit_cpt_list          IS '最强板块统计';
COMMENT ON COLUMN limit_cpt_list.trade_date IS '交易日期';
COMMENT ON COLUMN limit_cpt_list.ts_code    IS '板块代码';
COMMENT ON COLUMN limit_cpt_list.name       IS '板块名称';
COMMENT ON COLUMN limit_cpt_list.days       IS '持续天数';
COMMENT ON COLUMN limit_cpt_list.up_stat    IS '统计类型';
COMMENT ON COLUMN limit_cpt_list.cons_nums  IS '连续涨停数';
COMMENT ON COLUMN limit_cpt_list.up_nums    IS '涨停数';
COMMENT ON COLUMN limit_cpt_list.pct_chg    IS '板块涨幅%';
COMMENT ON COLUMN limit_cpt_list.rank       IS '排名';

-- =============================================================================
-- 6. ths_index — 同花顺概念和行业指数
-- =============================================================================
CREATE TABLE IF NOT EXISTS ths_index (
    ts_code   VARCHAR(16) NOT NULL PRIMARY KEY,
    name      VARCHAR(64),
    count     INTEGER,
    exchange  VARCHAR(8),
    list_date VARCHAR(8),
    type      VARCHAR(4)
);
COMMENT ON TABLE  ths_index          IS '同花顺概念和行业指数';
COMMENT ON COLUMN ths_index.ts_code   IS '指数代码';
COMMENT ON COLUMN ths_index.name      IS '指数名称';
COMMENT ON COLUMN ths_index.count     IS '成分数量';
COMMENT ON COLUMN ths_index.exchange  IS '交易所';
COMMENT ON COLUMN ths_index.list_date IS '上市日期';
COMMENT ON COLUMN ths_index.type      IS '类型 N/S/I/R/ST/TH/BB';

-- =============================================================================
-- 7. ths_daily — 同花顺板块指数行情
-- =============================================================================
CREATE TABLE IF NOT EXISTS ths_daily (
    ts_code      VARCHAR(16) NOT NULL,
    trade_date   VARCHAR(8)  NOT NULL,
    close        NUMERIC(12,2),
    open         NUMERIC(12,2),
    high         NUMERIC(12,2),
    low          NUMERIC(12,2),
    pre_close    NUMERIC(12,2),
    avg_price    NUMERIC(12,2),
    change       NUMERIC(12,2),
    pct_change   NUMERIC(8,3),
    vol          NUMERIC(18,2),
    turnover_rate NUMERIC(8,3),
    total_mv     NUMERIC(18,2),
    float_mv     NUMERIC(18,2),
    PRIMARY KEY (ts_code, trade_date)
);
COMMENT ON TABLE  ths_daily          IS '同花顺板块指数行情';
COMMENT ON COLUMN ths_daily.ts_code      IS '指数代码';
COMMENT ON COLUMN ths_daily.trade_date   IS '交易日期';
COMMENT ON COLUMN ths_daily.close        IS '收盘价';
COMMENT ON COLUMN ths_daily.open         IS '开盘价';
COMMENT ON COLUMN ths_daily.high         IS '最高价';
COMMENT ON COLUMN ths_daily.low          IS '最低价';
COMMENT ON COLUMN ths_daily.pre_close    IS '昨收价';
COMMENT ON COLUMN ths_daily.avg_price    IS '均价';
COMMENT ON COLUMN ths_daily.change       IS '涨跌额';
COMMENT ON COLUMN ths_daily.pct_change   IS '涨跌幅%';
COMMENT ON COLUMN ths_daily.vol          IS '成交量(股)';
COMMENT ON COLUMN ths_daily.turnover_rate IS '换手率%';
COMMENT ON COLUMN ths_daily.total_mv     IS '总市值(万)';
COMMENT ON COLUMN ths_daily.float_mv     IS '流通市值(万)';

-- =============================================================================
-- 8. ths_member — 同花顺概念板块成分
-- =============================================================================
CREATE TABLE IF NOT EXISTS ths_member (
    ts_code  VARCHAR(16) NOT NULL,
    con_code VARCHAR(16) NOT NULL,
    con_name VARCHAR(64),
    weight   NUMERIC(8,3),
    in_date  VARCHAR(8),
    out_date VARCHAR(8),
    is_new   VARCHAR(4),
    PRIMARY KEY (ts_code, con_code)
);
COMMENT ON TABLE  ths_member          IS '同花顺概念板块成分';
COMMENT ON COLUMN ths_member.ts_code   IS '板块代码';
COMMENT ON COLUMN ths_member.con_code  IS '成分股票代码';
COMMENT ON COLUMN ths_member.con_name  IS '成分股票名称';
COMMENT ON COLUMN ths_member.weight    IS '权重%';
COMMENT ON COLUMN ths_member.in_date   IS '纳入日期';
COMMENT ON COLUMN ths_member.out_date  IS '剔除日期';
COMMENT ON COLUMN ths_member.is_new    IS '是否最新';

-- =============================================================================
-- 9. dc_index — 东方财富概念板块
-- =============================================================================
CREATE TABLE IF NOT EXISTS dc_index (
    trade_date   VARCHAR(8)  NOT NULL,
    ts_code      VARCHAR(16) NOT NULL,
    name         VARCHAR(64),
    leading      VARCHAR(64),
    leading_code VARCHAR(16),
    pct_change   NUMERIC(8,3),
    leading_pct  NUMERIC(8,3),
    total_mv     NUMERIC(18,2),
    turnover_rate NUMERIC(8,3),
    up_num       INTEGER,
    down_num     INTEGER,
    idx_type     VARCHAR(8),
    level        VARCHAR(8),
    PRIMARY KEY (ts_code, trade_date)
);
COMMENT ON TABLE  dc_index              IS '东方财富概念板块';
COMMENT ON COLUMN dc_index.trade_date    IS '交易日期';
COMMENT ON COLUMN dc_index.ts_code       IS '板块代码';
COMMENT ON COLUMN dc_index.name          IS '板块名称';
COMMENT ON COLUMN dc_index.leading       IS '领涨股名称';
COMMENT ON COLUMN dc_index.leading_code  IS '领涨股代码';
COMMENT ON COLUMN dc_index.pct_change    IS '板块涨幅%';
COMMENT ON COLUMN dc_index.leading_pct   IS '领涨股涨幅%';
COMMENT ON COLUMN dc_index.total_mv      IS '总市值';
COMMENT ON COLUMN dc_index.turnover_rate IS '换手率%';
COMMENT ON COLUMN dc_index.up_num        IS '上涨家数';
COMMENT ON COLUMN dc_index.down_num      IS '下跌家数';
COMMENT ON COLUMN dc_index.idx_type      IS '板块类型';
COMMENT ON COLUMN dc_index.level         IS '板块级别';

-- =============================================================================
-- 10. dc_member — 东方财富板块成分
-- =============================================================================
CREATE TABLE IF NOT EXISTS dc_member (
    trade_date VARCHAR(8)  NOT NULL,
    ts_code    VARCHAR(16) NOT NULL,
    con_code   VARCHAR(16) NOT NULL,
    name       VARCHAR(64),
    PRIMARY KEY (ts_code, trade_date, con_code)
);
COMMENT ON TABLE  dc_member          IS '东方财富板块成分';
COMMENT ON COLUMN dc_member.trade_date IS '交易日期';
COMMENT ON COLUMN dc_member.ts_code    IS '板块代码';
COMMENT ON COLUMN dc_member.con_code   IS '成分股票代码';
COMMENT ON COLUMN dc_member.name       IS '成分股票名称';

-- =============================================================================
-- 11. dc_daily — 东财概念板块行情
-- =============================================================================
CREATE TABLE IF NOT EXISTS dc_daily (
    ts_code      VARCHAR(16) NOT NULL,
    trade_date   VARCHAR(8)  NOT NULL,
    close        NUMERIC(12,2),
    open         NUMERIC(12,2),
    high         NUMERIC(12,2),
    low          NUMERIC(12,2),
    change       NUMERIC(12,2),
    pct_change   NUMERIC(8,3),
    vol          NUMERIC(18,2),
    amount       NUMERIC(18,2),
    swing        NUMERIC(8,3),
    turnover_rate NUMERIC(8,3),
    PRIMARY KEY (ts_code, trade_date)
);
COMMENT ON TABLE  dc_daily          IS '东财概念板块行情';
COMMENT ON COLUMN dc_daily.ts_code      IS '板块代码';
COMMENT ON COLUMN dc_daily.trade_date   IS '交易日期';
COMMENT ON COLUMN dc_daily.close        IS '收盘价';
COMMENT ON COLUMN dc_daily.open         IS '开盘价';
COMMENT ON COLUMN dc_daily.high         IS '最高价';
COMMENT ON COLUMN dc_daily.low          IS '最低价';
COMMENT ON COLUMN dc_daily.change       IS '涨跌额';
COMMENT ON COLUMN dc_daily.pct_change   IS '涨跌幅%';
COMMENT ON COLUMN dc_daily.vol          IS '成交量';
COMMENT ON COLUMN dc_daily.amount       IS '成交额';
COMMENT ON COLUMN dc_daily.swing        IS '振幅%';
COMMENT ON COLUMN dc_daily.turnover_rate IS '换手率%';

-- =============================================================================
-- 12. stk_auction — 当日集合竞价
-- =============================================================================
CREATE TABLE IF NOT EXISTS stk_auction (
    ts_code      VARCHAR(16) NOT NULL,
    trade_date   VARCHAR(8)  NOT NULL,
    vol          NUMERIC(18,2),
    price        NUMERIC(12,2),
    amount       NUMERIC(18,2),
    pre_close    NUMERIC(12,2),
    turnover_rate NUMERIC(8,3),
    volume_ratio NUMERIC(8,3),
    float_share  NUMERIC(18,2),
    PRIMARY KEY (ts_code, trade_date)
);
COMMENT ON TABLE  stk_auction          IS '当日集合竞价';
COMMENT ON COLUMN stk_auction.ts_code       IS '股票代码';
COMMENT ON COLUMN stk_auction.trade_date    IS '交易日期';
COMMENT ON COLUMN stk_auction.vol           IS '集合竞价成交量(股)';
COMMENT ON COLUMN stk_auction.price         IS '集合竞价价格';
COMMENT ON COLUMN stk_auction.amount        IS '集合竞价成交额';
COMMENT ON COLUMN stk_auction.pre_close     IS '昨收盘价';
COMMENT ON COLUMN stk_auction.turnover_rate IS '换手率%';
COMMENT ON COLUMN stk_auction.volume_ratio  IS '量比';
COMMENT ON COLUMN stk_auction.float_share   IS '流通股本';

-- =============================================================================
-- 13. hm_list — 游资名录
-- =============================================================================
CREATE TABLE IF NOT EXISTS hm_list (
    name VARCHAR(64) NOT NULL PRIMARY KEY,
    desc TEXT,
    orgs TEXT
);
COMMENT ON TABLE  hm_list    IS '游资名录';
COMMENT ON COLUMN hm_list.name IS '游资名称';
COMMENT ON COLUMN hm_list.desc IS '描述';
COMMENT ON COLUMN hm_list.orgs IS '关联营业部';

-- =============================================================================

-- =============================================================================
-- 15. ths_hot — 同花顺热榜
-- =============================================================================
CREATE TABLE IF NOT EXISTS ths_hot (
    trade_date    VARCHAR(8)  NOT NULL,
    data_type     VARCHAR(8)  NOT NULL,
    ts_code       VARCHAR(16) NOT NULL,
    ts_name       VARCHAR(64),
    rank          INTEGER     NOT NULL,
    pct_change    NUMERIC(8,3),
    current_price NUMERIC(12,2),
    concept       VARCHAR(256),
    rank_reason   VARCHAR(512),
    hot           NUMERIC(10,2),
    rank_time     VARCHAR(20) NOT NULL DEFAULT '',
    PRIMARY KEY (trade_date, ts_code, rank, data_type, rank_time)
);
COMMENT ON TABLE  ths_hot              IS '同花顺热榜';
COMMENT ON COLUMN ths_hot.trade_date    IS '交易日期';
COMMENT ON COLUMN ths_hot.data_type     IS '数据类型';
COMMENT ON COLUMN ths_hot.ts_code       IS '股票代码';
COMMENT ON COLUMN ths_hot.ts_name       IS '股票名称';
COMMENT ON COLUMN ths_hot.rank          IS '排名';
COMMENT ON COLUMN ths_hot.pct_change    IS '涨跌幅%';
COMMENT ON COLUMN ths_hot.current_price IS '当前价格';
COMMENT ON COLUMN ths_hot.concept       IS '所属概念';
COMMENT ON COLUMN ths_hot.rank_reason   IS '上榜理由';
COMMENT ON COLUMN ths_hot.hot           IS '热度值';
COMMENT ON COLUMN ths_hot.rank_time     IS '排名时间';

-- =============================================================================
-- 16. dc_hot — 东方财富热榜
-- =============================================================================
CREATE TABLE IF NOT EXISTS dc_hot (
    trade_date    VARCHAR(8)  NOT NULL,
    data_type     VARCHAR(8)  NOT NULL,
    ts_code       VARCHAR(16) NOT NULL,
    ts_name       VARCHAR(64),
    rank          INTEGER     NOT NULL,
    pct_change    NUMERIC(8,3),
    current_price NUMERIC(12,2),
    rank_time     VARCHAR(20) NOT NULL DEFAULT '',
    PRIMARY KEY (trade_date, ts_code, rank, data_type, rank_time)
);
COMMENT ON TABLE  dc_hot              IS '东方财富热榜';
COMMENT ON COLUMN dc_hot.trade_date    IS '交易日期';
COMMENT ON COLUMN dc_hot.data_type     IS '数据类型';
COMMENT ON COLUMN dc_hot.ts_code       IS '股票代码';
COMMENT ON COLUMN dc_hot.ts_name       IS '股票名称';
COMMENT ON COLUMN dc_hot.rank          IS '排名';
COMMENT ON COLUMN dc_hot.pct_change    IS '涨跌幅%';
COMMENT ON COLUMN dc_hot.current_price IS '当前价格';
COMMENT ON COLUMN dc_hot.rank_time     IS '排名时间';

-- =============================================================================
-- 17. tdx_index — 通达信板块信息
-- =============================================================================
CREATE TABLE IF NOT EXISTS tdx_index (
    ts_code     VARCHAR(16) NOT NULL,
    trade_date  VARCHAR(8)  NOT NULL,
    name        VARCHAR(64),
    idx_type    VARCHAR(8),
    idx_count   INTEGER,
    total_share NUMERIC(18,2),
    float_share NUMERIC(18,2),
    total_mv    NUMERIC(18,2),
    float_mv    NUMERIC(18,2),
    PRIMARY KEY (ts_code, trade_date)
);
COMMENT ON TABLE  tdx_index          IS '通达信板块信息';
COMMENT ON COLUMN tdx_index.ts_code     IS '板块代码';
COMMENT ON COLUMN tdx_index.trade_date  IS '交易日期';
COMMENT ON COLUMN tdx_index.name        IS '板块名称';
COMMENT ON COLUMN tdx_index.idx_type    IS '板块类型';
COMMENT ON COLUMN tdx_index.idx_count   IS '成分数量';
COMMENT ON COLUMN tdx_index.total_share IS '总股本';
COMMENT ON COLUMN tdx_index.float_share IS '流通股本';
COMMENT ON COLUMN tdx_index.total_mv    IS '总市值';
COMMENT ON COLUMN tdx_index.float_mv    IS '流通市值';

-- =============================================================================
-- 18. tdx_member — 通达信板块成分
-- =============================================================================
CREATE TABLE IF NOT EXISTS tdx_member (
    ts_code    VARCHAR(16) NOT NULL,
    trade_date VARCHAR(8)  NOT NULL,
    con_code   VARCHAR(16) NOT NULL,
    con_name   VARCHAR(64),
    PRIMARY KEY (ts_code, trade_date, con_code)
);
COMMENT ON TABLE  tdx_member          IS '通达信板块成分';
COMMENT ON COLUMN tdx_member.ts_code    IS '板块代码';
COMMENT ON COLUMN tdx_member.trade_date IS '交易日期';
COMMENT ON COLUMN tdx_member.con_code   IS '成分股票代码';
COMMENT ON COLUMN tdx_member.con_name   IS '成分股票名称';

-- =============================================================================
-- 19. tdx_daily — 通达信板块行情
-- =============================================================================
CREATE TABLE IF NOT EXISTS tdx_daily (
    ts_code        VARCHAR(16) NOT NULL,
    trade_date     VARCHAR(8)  NOT NULL,
    close          NUMERIC(12,2),
    open           NUMERIC(12,2),
    high           NUMERIC(12,2),
    low            NUMERIC(12,2),
    pre_close      NUMERIC(12,2),
    change         NUMERIC(12,2),
    pct_change     NUMERIC(8,3),
    vol            NUMERIC(18,2),
    amount         NUMERIC(18,2),
    rise           NUMERIC(8,3),
    vol_ratio      NUMERIC(8,3),
    turnover_rate  NUMERIC(8,3),
    swing          NUMERIC(8,3),
    up_num         INTEGER,
    down_num       INTEGER,
    limit_up_num   INTEGER,
    limit_down_num INTEGER,
    lu_days        INTEGER,
    "3day"         NUMERIC(8,3),
    "5day"         NUMERIC(8,3),
    "10day"        NUMERIC(8,3),
    "20day"        NUMERIC(8,3),
    "60day"        NUMERIC(8,3),
    mtd            NUMERIC(8,3),
    ytd            NUMERIC(8,3),
    "1year"        NUMERIC(8,3),
    pe             NUMERIC(12,2),
    pb             NUMERIC(12,2),
    float_mv       NUMERIC(18,2),
    ab_total_mv    NUMERIC(18,2),
    float_share    NUMERIC(18,2),
    total_share    NUMERIC(18,2),
    bm_buy_net     NUMERIC(18,2),
    bm_buy_ratio   NUMERIC(8,3),
    bm_net         NUMERIC(18,2),
    bm_ratio       NUMERIC(8,3),
    PRIMARY KEY (ts_code, trade_date)
);
COMMENT ON TABLE  tdx_daily               IS '通达信板块行情';
COMMENT ON COLUMN tdx_daily.ts_code        IS '板块代码';
COMMENT ON COLUMN tdx_daily.trade_date     IS '交易日期';
COMMENT ON COLUMN tdx_daily.close          IS '收盘价';
COMMENT ON COLUMN tdx_daily.open           IS '开盘价';
COMMENT ON COLUMN tdx_daily.high           IS '最高价';
COMMENT ON COLUMN tdx_daily.low            IS '最低价';
COMMENT ON COLUMN tdx_daily.pre_close      IS '昨收价';
COMMENT ON COLUMN tdx_daily.change         IS '涨跌额';
COMMENT ON COLUMN tdx_daily.pct_change     IS '涨跌幅%';
COMMENT ON COLUMN tdx_daily.vol            IS '成交量';
COMMENT ON COLUMN tdx_daily.amount         IS '成交额';
COMMENT ON COLUMN tdx_daily.rise           IS '涨速%';
COMMENT ON COLUMN tdx_daily.vol_ratio      IS '量比';
COMMENT ON COLUMN tdx_daily.turnover_rate  IS '换手率%';
COMMENT ON COLUMN tdx_daily.swing          IS '振幅%';
COMMENT ON COLUMN tdx_daily.up_num         IS '上涨家数';
COMMENT ON COLUMN tdx_daily.down_num       IS '下跌家数';
COMMENT ON COLUMN tdx_daily.limit_up_num   IS '涨停家数';
COMMENT ON COLUMN tdx_daily.limit_down_num IS '跌停家数';
COMMENT ON COLUMN tdx_daily.lu_days        IS '连涨天数';
COMMENT ON COLUMN tdx_daily."3day"         IS '3日涨幅%';
COMMENT ON COLUMN tdx_daily."5day"         IS '5日涨幅%';
COMMENT ON COLUMN tdx_daily."10day"        IS '10日涨幅%';
COMMENT ON COLUMN tdx_daily."20day"        IS '20日涨幅%';
COMMENT ON COLUMN tdx_daily."60day"        IS '60日涨幅%';
COMMENT ON COLUMN tdx_daily.mtd            IS '月涨幅%';
COMMENT ON COLUMN tdx_daily.ytd            IS '年涨幅%';
COMMENT ON COLUMN tdx_daily."1year"        IS '1年涨幅%';
COMMENT ON COLUMN tdx_daily.pe             IS '市盈率';
COMMENT ON COLUMN tdx_daily.pb             IS '市净率';
COMMENT ON COLUMN tdx_daily.float_mv       IS '流通市值';
COMMENT ON COLUMN tdx_daily.ab_total_mv    IS '总市值(A+B)';
COMMENT ON COLUMN tdx_daily.float_share    IS '流通股本';
COMMENT ON COLUMN tdx_daily.total_share    IS '总股本';
COMMENT ON COLUMN tdx_daily.bm_buy_net     IS '主力净买入额';
COMMENT ON COLUMN tdx_daily.bm_buy_ratio   IS '主力净买入占比%';
COMMENT ON COLUMN tdx_daily.bm_net         IS '净主动买入额';
COMMENT ON COLUMN tdx_daily.bm_ratio       IS '净主动买入占比%';

-- =============================================================================
-- 20. kpl_list — 开盘啦榜单数据
-- =============================================================================
CREATE TABLE IF NOT EXISTS kpl_list (
    ts_code       VARCHAR(16) NOT NULL,
    name          VARCHAR(64),
    trade_date    VARCHAR(8)  NOT NULL,
    lu_time       VARCHAR(8),
    ld_time       VARCHAR(8),
    open_time     VARCHAR(8),
    last_time     VARCHAR(8),
    lu_desc       VARCHAR(128),
    tag           VARCHAR(16) NOT NULL DEFAULT '',
    theme         VARCHAR(64),
    net_change    NUMERIC(8,3),
    bid_amount    NUMERIC(18,2),
    status        VARCHAR(8),
    bid_change    NUMERIC(8,3),
    bid_turnover  NUMERIC(8,3),
    lu_bid_vol    NUMERIC(18,2),
    pct_chg       NUMERIC(8,3),
    bid_pct_chg   NUMERIC(8,3),
    rt_pct_chg    NUMERIC(8,3),
    limit_order   NUMERIC(18,2),
    amount        NUMERIC(18,2),
    turnover_rate NUMERIC(8,3),
    free_float    NUMERIC(18,2),
    lu_limit_order NUMERIC(18,2),
    PRIMARY KEY (ts_code, trade_date, tag)
);
COMMENT ON TABLE  kpl_list              IS '开盘啦榜单数据';
COMMENT ON COLUMN kpl_list.ts_code       IS '股票代码';
COMMENT ON COLUMN kpl_list.name          IS '股票名称';
COMMENT ON COLUMN kpl_list.trade_date    IS '交易日期';
COMMENT ON COLUMN kpl_list.lu_time       IS '涨停时间';
COMMENT ON COLUMN kpl_list.ld_time       IS '跌停时间';
COMMENT ON COLUMN kpl_list.open_time     IS '开板时间';
COMMENT ON COLUMN kpl_list.last_time     IS '最后封板时间';
COMMENT ON COLUMN kpl_list.lu_desc       IS '涨停描述';
COMMENT ON COLUMN kpl_list.tag           IS '标签';
COMMENT ON COLUMN kpl_list.theme         IS '题材';
COMMENT ON COLUMN kpl_list.net_change    IS '涨跌幅%';
COMMENT ON COLUMN kpl_list.bid_amount    IS '竞价金额';
COMMENT ON COLUMN kpl_list.status        IS '状态';
COMMENT ON COLUMN kpl_list.bid_change    IS '竞价涨跌幅%';
COMMENT ON COLUMN kpl_list.bid_turnover  IS '竞价换手%';
COMMENT ON COLUMN kpl_list.lu_bid_vol    IS '涨停封单量';
COMMENT ON COLUMN kpl_list.pct_chg       IS '涨跌幅%';
COMMENT ON COLUMN kpl_list.bid_pct_chg   IS '竞价涨跌幅%';
COMMENT ON COLUMN kpl_list.rt_pct_chg    IS '实时涨跌幅%';
COMMENT ON COLUMN kpl_list.limit_order   IS '封单额';
COMMENT ON COLUMN kpl_list.amount        IS '成交额';
COMMENT ON COLUMN kpl_list.turnover_rate IS '换手率%';
COMMENT ON COLUMN kpl_list.free_float    IS '流通市值';
COMMENT ON COLUMN kpl_list.lu_limit_order IS '涨停封单额';

-- =============================================================================
-- 21. kpl_concept_cons — 开盘啦题材成分
-- =============================================================================
CREATE TABLE IF NOT EXISTS kpl_concept_cons (
    ts_code   VARCHAR(16) NOT NULL,
    name      VARCHAR(64),
    con_name  VARCHAR(64),
    con_code  VARCHAR(16) NOT NULL,
    trade_date VARCHAR(8) NOT NULL,
    desc      VARCHAR(512),
    hot_num   INTEGER,
    PRIMARY KEY (ts_code, con_code, trade_date)
);
COMMENT ON TABLE  kpl_concept_cons          IS '开盘啦题材成分';
COMMENT ON COLUMN kpl_concept_cons.ts_code   IS '题材代码';
COMMENT ON COLUMN kpl_concept_cons.name      IS '题材名称';
COMMENT ON COLUMN kpl_concept_cons.con_name  IS '成分股名称';
COMMENT ON COLUMN kpl_concept_cons.con_code  IS '成分股代码';
COMMENT ON COLUMN kpl_concept_cons.trade_date IS '交易日期';
COMMENT ON COLUMN kpl_concept_cons.desc      IS '描述';
COMMENT ON COLUMN kpl_concept_cons.hot_num   IS '热度';

-- =============================================================================
-- 22. dc_concept — 东方财富题材库
-- =============================================================================
CREATE TABLE IF NOT EXISTS dc_concept (
    theme_code      VARCHAR(16) NOT NULL,
    trade_date      VARCHAR(8)  NOT NULL,
    name            VARCHAR(64),
    pct_change      NUMERIC(8,3),
    hot             NUMERIC(10,2),
    sort            INTEGER,
    strength        NUMERIC(8,3),
    z_t_num         INTEGER,
    main_change     NUMERIC(18,2),
    lead_stock      VARCHAR(64),
    lead_stock_code VARCHAR(16),
    lead_stock_pct_change NUMERIC(8,3),
    PRIMARY KEY (theme_code, trade_date)
);
COMMENT ON TABLE  dc_concept                    IS '东方财富题材库';
COMMENT ON COLUMN dc_concept.theme_code          IS '题材代码';
COMMENT ON COLUMN dc_concept.trade_date          IS '交易日期';
COMMENT ON COLUMN dc_concept.name                 IS '题材名称';
COMMENT ON COLUMN dc_concept.pct_change            IS '涨幅%';
COMMENT ON COLUMN dc_concept.hot                   IS '热度';
COMMENT ON COLUMN dc_concept.sort                  IS '排序';
COMMENT ON COLUMN dc_concept.strength              IS '强度';
COMMENT ON COLUMN dc_concept.z_t_num               IS '涨停数';
COMMENT ON COLUMN dc_concept.main_change           IS '主力净流入';
COMMENT ON COLUMN dc_concept.lead_stock            IS '领涨股';
COMMENT ON COLUMN dc_concept.lead_stock_code       IS '领涨股代码';
COMMENT ON COLUMN dc_concept.lead_stock_pct_change IS '领涨股涨幅%';

-- =============================================================================
-- 23. dc_concept_cons — 东方财富题材成分
-- =============================================================================
CREATE TABLE IF NOT EXISTS dc_concept_cons (
    ts_code      VARCHAR(16) NOT NULL,
    trade_date   VARCHAR(8)  NOT NULL,
    name         VARCHAR(64),
    theme_code   VARCHAR(16) NOT NULL,
    industry_code VARCHAR(16),
    industry     VARCHAR(64),
    reason       TEXT,
    hot_num      INTEGER,
    PRIMARY KEY (ts_code, trade_date, theme_code)
);
COMMENT ON TABLE  dc_concept_cons              IS '东方财富题材成分';
COMMENT ON COLUMN dc_concept_cons.ts_code       IS '股票代码';
COMMENT ON COLUMN dc_concept_cons.trade_date    IS '交易日期';
COMMENT ON COLUMN dc_concept_cons.name          IS '股票名称';
COMMENT ON COLUMN dc_concept_cons.theme_code    IS '题材代码';
COMMENT ON COLUMN dc_concept_cons.industry_code IS '行业代码';
COMMENT ON COLUMN dc_concept_cons.industry      IS '行业名称';
COMMENT ON COLUMN dc_concept_cons.reason        IS '入选理由';
COMMENT ON COLUMN dc_concept_cons.hot_num       IS '热度';