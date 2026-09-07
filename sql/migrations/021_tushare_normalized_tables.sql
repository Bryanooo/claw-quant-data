-- Generated typed standard layer for contract-driven Tushare interfaces.
-- Source: docs/tushare/contracts.json; generator: scripts/generate_tushare_normalized_schema.py

CREATE TABLE IF NOT EXISTS sys_tushare_normalization_run (
    normalization_run_id BIGSERIAL PRIMARY KEY,
    api_name VARCHAR(128) NOT NULL,
    request_hash CHAR(64) NOT NULL,
    schema_version INTEGER NOT NULL,
    status VARCHAR(16) NOT NULL CHECK (status IN ('complete', 'partial', 'failed')),
    raw_rows INTEGER NOT NULL,
    normalized_rows INTEGER NOT NULL,
    quarantined_rows INTEGER NOT NULL,
    unknown_fields JSONB NOT NULL DEFAULT '[]'::jsonb,
    missing_fields JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_tushare_normalization_run_api_created ON sys_tushare_normalization_run(api_name, created_at DESC);

CREATE TABLE IF NOT EXISTS sys_tushare_normalization_error (
    api_name VARCHAR(128) NOT NULL,
    request_hash CHAR(64) NOT NULL,
    record_hash CHAR(64) NOT NULL,
    payload JSONB NOT NULL,
    error_code VARCHAR(64) NOT NULL,
    error_message TEXT NOT NULL,
    attempts INTEGER NOT NULL DEFAULT 1,
    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at TIMESTAMPTZ,
    PRIMARY KEY (api_name, request_hash, record_hash)
);

CREATE TABLE IF NOT EXISTS sys_tushare_schema_drift (
    api_name VARCHAR(128) NOT NULL,
    field_name VARCHAR(128) NOT NULL,
    drift_type VARCHAR(32) NOT NULL,
    severity VARCHAR(16) NOT NULL,
    occurrences BIGINT NOT NULL DEFAULT 1,
    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at TIMESTAMPTZ,
    PRIMARY KEY (api_name, field_name, drift_type)
);

CREATE TABLE IF NOT EXISTS "tushare_norm_adj_factor" (
    _record_hash CHAR(64) PRIMARY KEY,
    _request_hash CHAR(64) NOT NULL,
    _source_doc_id INTEGER,
    _source_collected_at TIMESTAMPTZ NOT NULL,
    _first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _schema_version INTEGER NOT NULL DEFAULT 1,
    _extra_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    "ts_code" TEXT,
    "trade_date" DATE,
    "adj_factor" NUMERIC
);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_adj_factor_source" ON "tushare_norm_adj_factor" (_source_collected_at DESC);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_adj_factor_date" ON "tushare_norm_adj_factor" ("trade_date" DESC);
COMMENT ON TABLE "tushare_norm_adj_factor" IS '复权因子；契约驱动标准化表' ;
COMMENT ON COLUMN "tushare_norm_adj_factor"."ts_code" IS '股票代码';
COMMENT ON COLUMN "tushare_norm_adj_factor"."trade_date" IS '交易日期';
COMMENT ON COLUMN "tushare_norm_adj_factor"."adj_factor" IS '复权因子';

CREATE TABLE IF NOT EXISTS "tushare_norm_bak_daily" (
    _record_hash CHAR(64) PRIMARY KEY,
    _request_hash CHAR(64) NOT NULL,
    _source_doc_id INTEGER,
    _source_collected_at TIMESTAMPTZ NOT NULL,
    _first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _schema_version INTEGER NOT NULL DEFAULT 1,
    _extra_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    "ts_code" TEXT,
    "trade_date" DATE,
    "name" TEXT,
    "pct_change" NUMERIC,
    "close" NUMERIC,
    "change" NUMERIC,
    "open" NUMERIC,
    "high" NUMERIC,
    "low" NUMERIC,
    "pre_close" NUMERIC,
    "vol_ratio" NUMERIC,
    "turn_over" NUMERIC,
    "swing" NUMERIC,
    "vol" NUMERIC,
    "amount" NUMERIC,
    "selling" NUMERIC,
    "buying" NUMERIC,
    "total_share" NUMERIC,
    "float_share" NUMERIC,
    "pe" NUMERIC,
    "industry" TEXT,
    "area" TEXT,
    "float_mv" NUMERIC,
    "total_mv" NUMERIC,
    "avg_price" NUMERIC,
    "strength" NUMERIC,
    "activity" NUMERIC,
    "avg_turnover" NUMERIC,
    "attack" NUMERIC,
    "interval_3" NUMERIC,
    "interval_6" NUMERIC
);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_bak_daily_source" ON "tushare_norm_bak_daily" (_source_collected_at DESC);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_bak_daily_date" ON "tushare_norm_bak_daily" ("trade_date" DESC);
COMMENT ON TABLE "tushare_norm_bak_daily" IS '备用行情；契约驱动标准化表' ;
COMMENT ON COLUMN "tushare_norm_bak_daily"."ts_code" IS '股票代码';
COMMENT ON COLUMN "tushare_norm_bak_daily"."trade_date" IS '交易日期';
COMMENT ON COLUMN "tushare_norm_bak_daily"."name" IS '股票名称';
COMMENT ON COLUMN "tushare_norm_bak_daily"."pct_change" IS '涨跌幅';
COMMENT ON COLUMN "tushare_norm_bak_daily"."close" IS '收盘价';
COMMENT ON COLUMN "tushare_norm_bak_daily"."change" IS '涨跌额';
COMMENT ON COLUMN "tushare_norm_bak_daily"."open" IS '开盘价';
COMMENT ON COLUMN "tushare_norm_bak_daily"."high" IS '最高价';
COMMENT ON COLUMN "tushare_norm_bak_daily"."low" IS '最低价';
COMMENT ON COLUMN "tushare_norm_bak_daily"."pre_close" IS '昨收价';
COMMENT ON COLUMN "tushare_norm_bak_daily"."vol_ratio" IS '量比';
COMMENT ON COLUMN "tushare_norm_bak_daily"."turn_over" IS '换手率';
COMMENT ON COLUMN "tushare_norm_bak_daily"."swing" IS '振幅';
COMMENT ON COLUMN "tushare_norm_bak_daily"."vol" IS '成交量';
COMMENT ON COLUMN "tushare_norm_bak_daily"."amount" IS '成交额';
COMMENT ON COLUMN "tushare_norm_bak_daily"."selling" IS '内盘（主动卖，手）';
COMMENT ON COLUMN "tushare_norm_bak_daily"."buying" IS '外盘（主动买， 手）';
COMMENT ON COLUMN "tushare_norm_bak_daily"."total_share" IS '总股本(亿)';
COMMENT ON COLUMN "tushare_norm_bak_daily"."float_share" IS '流通股本(亿)';
COMMENT ON COLUMN "tushare_norm_bak_daily"."pe" IS '市盈(动)';
COMMENT ON COLUMN "tushare_norm_bak_daily"."industry" IS '所属行业';
COMMENT ON COLUMN "tushare_norm_bak_daily"."area" IS '所属地域';
COMMENT ON COLUMN "tushare_norm_bak_daily"."float_mv" IS '流通市值';
COMMENT ON COLUMN "tushare_norm_bak_daily"."total_mv" IS '总市值';
COMMENT ON COLUMN "tushare_norm_bak_daily"."avg_price" IS '平均价';
COMMENT ON COLUMN "tushare_norm_bak_daily"."strength" IS '强弱度(%)';
COMMENT ON COLUMN "tushare_norm_bak_daily"."activity" IS '活跃度(%)';
COMMENT ON COLUMN "tushare_norm_bak_daily"."avg_turnover" IS '笔换手';
COMMENT ON COLUMN "tushare_norm_bak_daily"."attack" IS '攻击波(%)';
COMMENT ON COLUMN "tushare_norm_bak_daily"."interval_3" IS '近3月涨幅';
COMMENT ON COLUMN "tushare_norm_bak_daily"."interval_6" IS '近6月涨幅';

CREATE TABLE IF NOT EXISTS "tushare_norm_bc_bestotcqt" (
    _record_hash CHAR(64) PRIMARY KEY,
    _request_hash CHAR(64) NOT NULL,
    _source_doc_id INTEGER,
    _source_collected_at TIMESTAMPTZ NOT NULL,
    _first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _schema_version INTEGER NOT NULL DEFAULT 1,
    _extra_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    "trade_date" DATE,
    "ts_code" TEXT,
    "name" TEXT,
    "remain_maturity" TEXT,
    "bond_type" TEXT,
    "best_buy_bank" TEXT,
    "best_buy_yield" NUMERIC,
    "best_buy_price" NUMERIC,
    "best_sell_bank" TEXT,
    "best_sell_yield" NUMERIC,
    "best_sell_price" NUMERIC
);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_bc_bestotcqt_source" ON "tushare_norm_bc_bestotcqt" (_source_collected_at DESC);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_bc_bestotcqt_date" ON "tushare_norm_bc_bestotcqt" ("trade_date" DESC);
COMMENT ON TABLE "tushare_norm_bc_bestotcqt" IS '柜台流通式债券最优报价；契约驱动标准化表' ;
COMMENT ON COLUMN "tushare_norm_bc_bestotcqt"."trade_date" IS '报价日期';
COMMENT ON COLUMN "tushare_norm_bc_bestotcqt"."ts_code" IS '债券编码';
COMMENT ON COLUMN "tushare_norm_bc_bestotcqt"."name" IS '债券简称';
COMMENT ON COLUMN "tushare_norm_bc_bestotcqt"."remain_maturity" IS '剩余期限';
COMMENT ON COLUMN "tushare_norm_bc_bestotcqt"."bond_type" IS '债券类型';
COMMENT ON COLUMN "tushare_norm_bc_bestotcqt"."best_buy_bank" IS '最优报买价方';
COMMENT ON COLUMN "tushare_norm_bc_bestotcqt"."best_buy_yield" IS '投资者最优买入价到期收益率（%）';
COMMENT ON COLUMN "tushare_norm_bc_bestotcqt"."best_buy_price" IS '投资者最优买入全价';
COMMENT ON COLUMN "tushare_norm_bc_bestotcqt"."best_sell_bank" IS '最优卖报价方';
COMMENT ON COLUMN "tushare_norm_bc_bestotcqt"."best_sell_yield" IS '投资者最优卖出价到期收益率（%）';
COMMENT ON COLUMN "tushare_norm_bc_bestotcqt"."best_sell_price" IS '投资者最优卖出全价';

CREATE TABLE IF NOT EXISTS "tushare_norm_bc_otcqt" (
    _record_hash CHAR(64) PRIMARY KEY,
    _request_hash CHAR(64) NOT NULL,
    _source_doc_id INTEGER,
    _source_collected_at TIMESTAMPTZ NOT NULL,
    _first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _schema_version INTEGER NOT NULL DEFAULT 1,
    _extra_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    "trade_date" DATE,
    "qt_time" TIME WITHOUT TIME ZONE,
    "bank" TEXT,
    "ts_code" TEXT,
    "name" TEXT,
    "maturity" TEXT,
    "remain_maturity" TEXT,
    "bond_type" TEXT,
    "coupon_rate" NUMERIC,
    "buy_price" NUMERIC,
    "sell_price" NUMERIC,
    "buy_yield" NUMERIC,
    "sell_yield" NUMERIC
);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_bc_otcqt_source" ON "tushare_norm_bc_otcqt" (_source_collected_at DESC);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_bc_otcqt_date" ON "tushare_norm_bc_otcqt" ("trade_date" DESC);
COMMENT ON TABLE "tushare_norm_bc_otcqt" IS '柜台流通式债券报价；契约驱动标准化表' ;
COMMENT ON COLUMN "tushare_norm_bc_otcqt"."trade_date" IS '报价日期';
COMMENT ON COLUMN "tushare_norm_bc_otcqt"."qt_time" IS '报价时间';
COMMENT ON COLUMN "tushare_norm_bc_otcqt"."bank" IS '报价机构';
COMMENT ON COLUMN "tushare_norm_bc_otcqt"."ts_code" IS '债券编码';
COMMENT ON COLUMN "tushare_norm_bc_otcqt"."name" IS '债券简称';
COMMENT ON COLUMN "tushare_norm_bc_otcqt"."maturity" IS '期限';
COMMENT ON COLUMN "tushare_norm_bc_otcqt"."remain_maturity" IS '剩余期限';
COMMENT ON COLUMN "tushare_norm_bc_otcqt"."bond_type" IS '债券类型';
COMMENT ON COLUMN "tushare_norm_bc_otcqt"."coupon_rate" IS '票面利率（%）';
COMMENT ON COLUMN "tushare_norm_bc_otcqt"."buy_price" IS '投资者买入全价';
COMMENT ON COLUMN "tushare_norm_bc_otcqt"."sell_price" IS '投资者卖出全价';
COMMENT ON COLUMN "tushare_norm_bc_otcqt"."buy_yield" IS '投资者买入到期收益率（%）';
COMMENT ON COLUMN "tushare_norm_bc_otcqt"."sell_yield" IS '投资者卖出到期收益率（%）';

CREATE TABLE IF NOT EXISTS "tushare_norm_bond_blk" (
    _record_hash CHAR(64) PRIMARY KEY,
    _request_hash CHAR(64) NOT NULL,
    _source_doc_id INTEGER,
    _source_collected_at TIMESTAMPTZ NOT NULL,
    _first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _schema_version INTEGER NOT NULL DEFAULT 1,
    _extra_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    "trade_date" DATE,
    "ts_code" TEXT,
    "name" TEXT,
    "price" NUMERIC,
    "vol" NUMERIC,
    "amount" NUMERIC
);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_bond_blk_source" ON "tushare_norm_bond_blk" (_source_collected_at DESC);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_bond_blk_date" ON "tushare_norm_bond_blk" ("trade_date" DESC);
COMMENT ON TABLE "tushare_norm_bond_blk" IS '债券大宗交易；契约驱动标准化表' ;
COMMENT ON COLUMN "tushare_norm_bond_blk"."trade_date" IS '交易日期';
COMMENT ON COLUMN "tushare_norm_bond_blk"."ts_code" IS '债券代码';
COMMENT ON COLUMN "tushare_norm_bond_blk"."name" IS '债券名称';
COMMENT ON COLUMN "tushare_norm_bond_blk"."price" IS '成交价（元）';
COMMENT ON COLUMN "tushare_norm_bond_blk"."vol" IS '累计成交数量（万股/万份/万张/万手）';
COMMENT ON COLUMN "tushare_norm_bond_blk"."amount" IS '累计成交金额（万元）';

CREATE TABLE IF NOT EXISTS "tushare_norm_bond_blk_detail" (
    _record_hash CHAR(64) PRIMARY KEY,
    _request_hash CHAR(64) NOT NULL,
    _source_doc_id INTEGER,
    _source_collected_at TIMESTAMPTZ NOT NULL,
    _first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _schema_version INTEGER NOT NULL DEFAULT 1,
    _extra_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    "trade_date" DATE,
    "ts_code" TEXT,
    "name" TEXT,
    "price" NUMERIC,
    "vol" NUMERIC,
    "amount" NUMERIC,
    "buy_dp" TEXT,
    "sell_dp" TEXT
);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_bond_blk_detail_source" ON "tushare_norm_bond_blk_detail" (_source_collected_at DESC);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_bond_blk_detail_date" ON "tushare_norm_bond_blk_detail" ("trade_date" DESC);
COMMENT ON TABLE "tushare_norm_bond_blk_detail" IS '大宗交易明细；契约驱动标准化表' ;
COMMENT ON COLUMN "tushare_norm_bond_blk_detail"."trade_date" IS '交易日期';
COMMENT ON COLUMN "tushare_norm_bond_blk_detail"."ts_code" IS '债券代码';
COMMENT ON COLUMN "tushare_norm_bond_blk_detail"."name" IS '债券名称';
COMMENT ON COLUMN "tushare_norm_bond_blk_detail"."price" IS '成交价（元）';
COMMENT ON COLUMN "tushare_norm_bond_blk_detail"."vol" IS '成交数量（万股/万份/万张/万手）';
COMMENT ON COLUMN "tushare_norm_bond_blk_detail"."amount" IS '成交金额（万元）';
COMMENT ON COLUMN "tushare_norm_bond_blk_detail"."buy_dp" IS '买方营业部';
COMMENT ON COLUMN "tushare_norm_bond_blk_detail"."sell_dp" IS '卖方营业部';

CREATE TABLE IF NOT EXISTS "tushare_norm_cb_basic" (
    _record_hash CHAR(64) PRIMARY KEY,
    _request_hash CHAR(64) NOT NULL,
    _source_doc_id INTEGER,
    _source_collected_at TIMESTAMPTZ NOT NULL,
    _first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _schema_version INTEGER NOT NULL DEFAULT 1,
    _extra_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    "ts_code" TEXT,
    "bond_full_name" TEXT,
    "bond_short_name" TEXT,
    "cb_code" TEXT,
    "cb_type" TEXT,
    "stk_code" TEXT,
    "stk_short_name" TEXT,
    "maturity" NUMERIC,
    "par" NUMERIC,
    "issue_price" NUMERIC,
    "issue_size" NUMERIC,
    "remain_size" NUMERIC,
    "value_date" DATE,
    "maturity_date" DATE,
    "rate_type" TEXT,
    "coupon_rate" NUMERIC,
    "add_rate" NUMERIC,
    "pay_per_year" BIGINT,
    "list_date" DATE,
    "delist_date" DATE,
    "exchange" TEXT,
    "conv_start_date" DATE,
    "conv_end_date" DATE,
    "conv_stop_date" DATE,
    "first_conv_price" NUMERIC,
    "conv_price" NUMERIC,
    "rate_clause" TEXT,
    "put_clause" TEXT,
    "maturity_call_price" NUMERIC,
    "maturity_put_price" NUMERIC,
    "call_clause" TEXT,
    "reset_clause" TEXT,
    "conv_clause" TEXT,
    "guarantor" TEXT,
    "guarantee_type" TEXT,
    "issue_rating" TEXT,
    "newest_rating" TEXT,
    "rating_comp" TEXT
);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_cb_basic_source" ON "tushare_norm_cb_basic" (_source_collected_at DESC);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_cb_basic_date" ON "tushare_norm_cb_basic" ("conv_end_date" DESC);
COMMENT ON TABLE "tushare_norm_cb_basic" IS '可转债基本信息；契约驱动标准化表' ;
COMMENT ON COLUMN "tushare_norm_cb_basic"."ts_code" IS '转债代码';
COMMENT ON COLUMN "tushare_norm_cb_basic"."bond_full_name" IS '转债名称';
COMMENT ON COLUMN "tushare_norm_cb_basic"."bond_short_name" IS '转债简称';
COMMENT ON COLUMN "tushare_norm_cb_basic"."cb_code" IS '转股申报代码';
COMMENT ON COLUMN "tushare_norm_cb_basic"."cb_type" IS '转债类型: CB-可转债,EB-可交换债';
COMMENT ON COLUMN "tushare_norm_cb_basic"."stk_code" IS '正股代码';
COMMENT ON COLUMN "tushare_norm_cb_basic"."stk_short_name" IS '正股简称';
COMMENT ON COLUMN "tushare_norm_cb_basic"."maturity" IS '发行期限（年）';
COMMENT ON COLUMN "tushare_norm_cb_basic"."par" IS '面值';
COMMENT ON COLUMN "tushare_norm_cb_basic"."issue_price" IS '发行价格';
COMMENT ON COLUMN "tushare_norm_cb_basic"."issue_size" IS '发行总额（元）';
COMMENT ON COLUMN "tushare_norm_cb_basic"."remain_size" IS '债券余额（元）';
COMMENT ON COLUMN "tushare_norm_cb_basic"."value_date" IS '起息日期';
COMMENT ON COLUMN "tushare_norm_cb_basic"."maturity_date" IS '到期日期';
COMMENT ON COLUMN "tushare_norm_cb_basic"."rate_type" IS '利率类型';
COMMENT ON COLUMN "tushare_norm_cb_basic"."coupon_rate" IS '票面利率（%）';
COMMENT ON COLUMN "tushare_norm_cb_basic"."add_rate" IS '补偿利率（%）';
COMMENT ON COLUMN "tushare_norm_cb_basic"."pay_per_year" IS '年付息次数';
COMMENT ON COLUMN "tushare_norm_cb_basic"."list_date" IS '上市日期';
COMMENT ON COLUMN "tushare_norm_cb_basic"."delist_date" IS '摘牌日';
COMMENT ON COLUMN "tushare_norm_cb_basic"."exchange" IS '上市交易所';
COMMENT ON COLUMN "tushare_norm_cb_basic"."conv_start_date" IS '转股起始日';
COMMENT ON COLUMN "tushare_norm_cb_basic"."conv_end_date" IS '转股截止日';
COMMENT ON COLUMN "tushare_norm_cb_basic"."conv_stop_date" IS '停止转股日(提前到期)';
COMMENT ON COLUMN "tushare_norm_cb_basic"."first_conv_price" IS '初始转股价';
COMMENT ON COLUMN "tushare_norm_cb_basic"."conv_price" IS '最新转股价';
COMMENT ON COLUMN "tushare_norm_cb_basic"."rate_clause" IS '利率说明';
COMMENT ON COLUMN "tushare_norm_cb_basic"."put_clause" IS '回售条款';
COMMENT ON COLUMN "tushare_norm_cb_basic"."maturity_call_price" IS '到期赎回价格(含税)';
COMMENT ON COLUMN "tushare_norm_cb_basic"."maturity_put_price" IS '到期赎回价格(含税)[更名停用，请使用maturity_call_price]';
COMMENT ON COLUMN "tushare_norm_cb_basic"."call_clause" IS '赎回条款';
COMMENT ON COLUMN "tushare_norm_cb_basic"."reset_clause" IS '特别向下修正条款';
COMMENT ON COLUMN "tushare_norm_cb_basic"."conv_clause" IS '转股条款';
COMMENT ON COLUMN "tushare_norm_cb_basic"."guarantor" IS '担保人';
COMMENT ON COLUMN "tushare_norm_cb_basic"."guarantee_type" IS '担保方式';
COMMENT ON COLUMN "tushare_norm_cb_basic"."issue_rating" IS '发行信用等级';
COMMENT ON COLUMN "tushare_norm_cb_basic"."newest_rating" IS '最新信用等级';
COMMENT ON COLUMN "tushare_norm_cb_basic"."rating_comp" IS '最新评级机构';

CREATE TABLE IF NOT EXISTS "tushare_norm_cb_call" (
    _record_hash CHAR(64) PRIMARY KEY,
    _request_hash CHAR(64) NOT NULL,
    _source_doc_id INTEGER,
    _source_collected_at TIMESTAMPTZ NOT NULL,
    _first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _schema_version INTEGER NOT NULL DEFAULT 1,
    _extra_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    "ts_code" TEXT,
    "call_type" TEXT,
    "is_call" TEXT,
    "ann_date" DATE,
    "call_date" DATE,
    "call_price" NUMERIC,
    "call_price_tax" NUMERIC,
    "call_vol" NUMERIC,
    "call_amount" NUMERIC,
    "payment_date" DATE,
    "call_reg_date" DATE
);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_cb_call_source" ON "tushare_norm_cb_call" (_source_collected_at DESC);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_cb_call_date" ON "tushare_norm_cb_call" ("ann_date" DESC);
COMMENT ON TABLE "tushare_norm_cb_call" IS '可转债赎回信息；契约驱动标准化表' ;
COMMENT ON COLUMN "tushare_norm_cb_call"."ts_code" IS '转债代码';
COMMENT ON COLUMN "tushare_norm_cb_call"."call_type" IS '赎回类型：到赎、强赎';
COMMENT ON COLUMN "tushare_norm_cb_call"."is_call" IS '是否赎回：已满足强赎条件、公告提示强赎、公告实施强赎、公告到期赎回、公告不强赎';
COMMENT ON COLUMN "tushare_norm_cb_call"."ann_date" IS '公告/提示日期';
COMMENT ON COLUMN "tushare_norm_cb_call"."call_date" IS '赎回日期';
COMMENT ON COLUMN "tushare_norm_cb_call"."call_price" IS '赎回价格(含税，元/张)';
COMMENT ON COLUMN "tushare_norm_cb_call"."call_price_tax" IS '赎回价格(扣税，元/张)';
COMMENT ON COLUMN "tushare_norm_cb_call"."call_vol" IS '赎回债券数量(张)';
COMMENT ON COLUMN "tushare_norm_cb_call"."call_amount" IS '赎回金额(万元)';
COMMENT ON COLUMN "tushare_norm_cb_call"."payment_date" IS '行权后款项到账日';
COMMENT ON COLUMN "tushare_norm_cb_call"."call_reg_date" IS '赎回登记日';

CREATE TABLE IF NOT EXISTS "tushare_norm_cb_daily" (
    _record_hash CHAR(64) PRIMARY KEY,
    _request_hash CHAR(64) NOT NULL,
    _source_doc_id INTEGER,
    _source_collected_at TIMESTAMPTZ NOT NULL,
    _first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _schema_version INTEGER NOT NULL DEFAULT 1,
    _extra_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    "ts_code" TEXT,
    "trade_date" DATE,
    "pre_close" NUMERIC,
    "open" NUMERIC,
    "high" NUMERIC,
    "low" NUMERIC,
    "close" NUMERIC,
    "change" NUMERIC,
    "pct_chg" NUMERIC,
    "vol" NUMERIC,
    "amount" NUMERIC,
    "bond_value" NUMERIC,
    "bond_over_rate" NUMERIC,
    "cb_value" NUMERIC,
    "cb_over_rate" NUMERIC
);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_cb_daily_source" ON "tushare_norm_cb_daily" (_source_collected_at DESC);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_cb_daily_date" ON "tushare_norm_cb_daily" ("trade_date" DESC);
COMMENT ON TABLE "tushare_norm_cb_daily" IS '可转债行情；契约驱动标准化表' ;
COMMENT ON COLUMN "tushare_norm_cb_daily"."ts_code" IS '转债代码';
COMMENT ON COLUMN "tushare_norm_cb_daily"."trade_date" IS '交易日期';
COMMENT ON COLUMN "tushare_norm_cb_daily"."pre_close" IS '昨收盘价(元)';
COMMENT ON COLUMN "tushare_norm_cb_daily"."open" IS '开盘价(元)';
COMMENT ON COLUMN "tushare_norm_cb_daily"."high" IS '最高价(元)';
COMMENT ON COLUMN "tushare_norm_cb_daily"."low" IS '最低价(元)';
COMMENT ON COLUMN "tushare_norm_cb_daily"."close" IS '收盘价(元)';
COMMENT ON COLUMN "tushare_norm_cb_daily"."change" IS '涨跌(元)';
COMMENT ON COLUMN "tushare_norm_cb_daily"."pct_chg" IS '涨跌幅(%)';
COMMENT ON COLUMN "tushare_norm_cb_daily"."vol" IS '成交量(手)';
COMMENT ON COLUMN "tushare_norm_cb_daily"."amount" IS '成交金额(万元)';
COMMENT ON COLUMN "tushare_norm_cb_daily"."bond_value" IS '纯债价值';
COMMENT ON COLUMN "tushare_norm_cb_daily"."bond_over_rate" IS '纯债溢价率(%)';
COMMENT ON COLUMN "tushare_norm_cb_daily"."cb_value" IS '转股价值';
COMMENT ON COLUMN "tushare_norm_cb_daily"."cb_over_rate" IS '转股溢价率(%)';

CREATE TABLE IF NOT EXISTS "tushare_norm_cb_factor_pro" (
    _record_hash CHAR(64) PRIMARY KEY,
    _request_hash CHAR(64) NOT NULL,
    _source_doc_id INTEGER,
    _source_collected_at TIMESTAMPTZ NOT NULL,
    _first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _schema_version INTEGER NOT NULL DEFAULT 1,
    _extra_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    "ts_code" TEXT,
    "trade_date" DATE,
    "open" NUMERIC,
    "high" NUMERIC,
    "low" NUMERIC,
    "close" NUMERIC,
    "pre_close" NUMERIC,
    "change" NUMERIC,
    "pct_change" NUMERIC,
    "vol" NUMERIC,
    "amount" NUMERIC,
    "asi_bfq" NUMERIC,
    "asit_bfq" NUMERIC,
    "atr_bfq" NUMERIC,
    "bbi_bfq" NUMERIC,
    "bias1_bfq" NUMERIC,
    "bias2_bfq" NUMERIC,
    "bias3_bfq" NUMERIC,
    "boll_lower_bfq" NUMERIC,
    "boll_mid_bfq" NUMERIC,
    "boll_upper_bfq" NUMERIC,
    "brar_ar_bfq" NUMERIC,
    "brar_br_bfq" NUMERIC,
    "cci_bfq" NUMERIC,
    "cr_bfq" NUMERIC,
    "dfma_dif_bfq" NUMERIC,
    "dfma_difma_bfq" NUMERIC,
    "dmi_adx_bfq" NUMERIC,
    "dmi_adxr_bfq" NUMERIC,
    "dmi_mdi_bfq" NUMERIC,
    "dmi_pdi_bfq" NUMERIC,
    "downdays" NUMERIC,
    "updays" NUMERIC,
    "dpo_bfq" NUMERIC,
    "madpo_bfq" NUMERIC,
    "ema_bfq_10" NUMERIC,
    "ema_bfq_20" NUMERIC,
    "ema_bfq_250" NUMERIC,
    "ema_bfq_30" NUMERIC,
    "ema_bfq_5" NUMERIC,
    "ema_bfq_60" NUMERIC,
    "ema_bfq_90" NUMERIC,
    "emv_bfq" NUMERIC,
    "maemv_bfq" NUMERIC,
    "expma_12_bfq" NUMERIC,
    "expma_50_bfq" NUMERIC,
    "kdj_bfq" NUMERIC,
    "kdj_d_bfq" NUMERIC,
    "kdj_k_bfq" NUMERIC,
    "ktn_down_bfq" NUMERIC,
    "ktn_mid_bfq" NUMERIC,
    "ktn_upper_bfq" NUMERIC,
    "lowdays" NUMERIC,
    "topdays" NUMERIC,
    "ma_bfq_10" NUMERIC,
    "ma_bfq_20" NUMERIC,
    "ma_bfq_250" NUMERIC,
    "ma_bfq_30" NUMERIC,
    "ma_bfq_5" NUMERIC,
    "ma_bfq_60" NUMERIC,
    "ma_bfq_90" NUMERIC,
    "macd_bfq" NUMERIC,
    "macd_dea_bfq" NUMERIC,
    "macd_dif_bfq" NUMERIC,
    "mass_bfq" NUMERIC,
    "ma_mass_bfq" NUMERIC,
    "mfi_bfq" NUMERIC,
    "mtm_bfq" NUMERIC,
    "mtmma_bfq" NUMERIC,
    "obv_bfq" NUMERIC,
    "psy_bfq" NUMERIC,
    "psyma_bfq" NUMERIC,
    "roc_bfq" NUMERIC,
    "maroc_bfq" NUMERIC,
    "rsi_bfq_12" NUMERIC,
    "rsi_bfq_24" NUMERIC,
    "rsi_bfq_6" NUMERIC,
    "taq_down_bfq" NUMERIC,
    "taq_mid_bfq" NUMERIC,
    "taq_up_bfq" NUMERIC,
    "trix_bfq" NUMERIC,
    "trma_bfq" NUMERIC,
    "vr_bfq" NUMERIC,
    "wr_bfq" NUMERIC,
    "wr1_bfq" NUMERIC,
    "xsii_td1_bfq" NUMERIC,
    "xsii_td2_bfq" NUMERIC,
    "xsii_td3_bfq" NUMERIC,
    "xsii_td4_bfq" NUMERIC
);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_cb_factor_pro_source" ON "tushare_norm_cb_factor_pro" (_source_collected_at DESC);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_cb_factor_pro_date" ON "tushare_norm_cb_factor_pro" ("trade_date" DESC);
COMMENT ON TABLE "tushare_norm_cb_factor_pro" IS '可转债技术因子(专业版)；契约驱动标准化表' ;
COMMENT ON COLUMN "tushare_norm_cb_factor_pro"."ts_code" IS '转债代码';
COMMENT ON COLUMN "tushare_norm_cb_factor_pro"."trade_date" IS '交易日期';
COMMENT ON COLUMN "tushare_norm_cb_factor_pro"."open" IS '开盘价';
COMMENT ON COLUMN "tushare_norm_cb_factor_pro"."high" IS '最高价';
COMMENT ON COLUMN "tushare_norm_cb_factor_pro"."low" IS '最低价';
COMMENT ON COLUMN "tushare_norm_cb_factor_pro"."close" IS '收盘价';
COMMENT ON COLUMN "tushare_norm_cb_factor_pro"."pre_close" IS '昨收价';
COMMENT ON COLUMN "tushare_norm_cb_factor_pro"."change" IS '涨跌额';
COMMENT ON COLUMN "tushare_norm_cb_factor_pro"."pct_change" IS '涨跌幅 （未复权，如果是复权请用 通用行情接口 ）';
COMMENT ON COLUMN "tushare_norm_cb_factor_pro"."vol" IS '成交量 （手）';
COMMENT ON COLUMN "tushare_norm_cb_factor_pro"."amount" IS '成交金额(万元)';
COMMENT ON COLUMN "tushare_norm_cb_factor_pro"."asi_bfq" IS '振动升降指标-OPEN, CLOSE, HIGH, LOW, M1=26, M2=10';
COMMENT ON COLUMN "tushare_norm_cb_factor_pro"."asit_bfq" IS '振动升降指标-OPEN, CLOSE, HIGH, LOW, M1=26, M2=10';
COMMENT ON COLUMN "tushare_norm_cb_factor_pro"."atr_bfq" IS '真实波动N日平均值-CLOSE, HIGH, LOW, N=20';
COMMENT ON COLUMN "tushare_norm_cb_factor_pro"."bbi_bfq" IS 'BBI多空指标-CLOSE, M1=3, M2=6, M3=12, M4=20';
COMMENT ON COLUMN "tushare_norm_cb_factor_pro"."bias1_bfq" IS 'BIAS乖离率-CLOSE, L1=6, L2=12, L3=24';
COMMENT ON COLUMN "tushare_norm_cb_factor_pro"."bias2_bfq" IS 'BIAS乖离率-CLOSE, L1=6, L2=12, L3=24';
COMMENT ON COLUMN "tushare_norm_cb_factor_pro"."bias3_bfq" IS 'BIAS乖离率-CLOSE, L1=6, L2=12, L3=24';
COMMENT ON COLUMN "tushare_norm_cb_factor_pro"."boll_lower_bfq" IS 'BOLL指标，布林带-CLOSE, N=20, P=2';
COMMENT ON COLUMN "tushare_norm_cb_factor_pro"."boll_mid_bfq" IS 'BOLL指标，布林带-CLOSE, N=20, P=2';
COMMENT ON COLUMN "tushare_norm_cb_factor_pro"."boll_upper_bfq" IS 'BOLL指标，布林带-CLOSE, N=20, P=2';
COMMENT ON COLUMN "tushare_norm_cb_factor_pro"."brar_ar_bfq" IS 'BRAR情绪指标-OPEN, CLOSE, HIGH, LOW, M1=26';
COMMENT ON COLUMN "tushare_norm_cb_factor_pro"."brar_br_bfq" IS 'BRAR情绪指标-OPEN, CLOSE, HIGH, LOW, M1=26';
COMMENT ON COLUMN "tushare_norm_cb_factor_pro"."cci_bfq" IS '顺势指标又叫CCI指标-CLOSE, HIGH, LOW, N=14';
COMMENT ON COLUMN "tushare_norm_cb_factor_pro"."cr_bfq" IS 'CR价格动量指标-CLOSE, HIGH, LOW, N=20';
COMMENT ON COLUMN "tushare_norm_cb_factor_pro"."dfma_dif_bfq" IS '平行线差指标-CLOSE, N1=10, N2=50, M=10';
COMMENT ON COLUMN "tushare_norm_cb_factor_pro"."dfma_difma_bfq" IS '平行线差指标-CLOSE, N1=10, N2=50, M=10';
COMMENT ON COLUMN "tushare_norm_cb_factor_pro"."dmi_adx_bfq" IS '动向指标-CLOSE, HIGH, LOW, M1=14, M2=6';
COMMENT ON COLUMN "tushare_norm_cb_factor_pro"."dmi_adxr_bfq" IS '动向指标-CLOSE, HIGH, LOW, M1=14, M2=6';
COMMENT ON COLUMN "tushare_norm_cb_factor_pro"."dmi_mdi_bfq" IS '动向指标-CLOSE, HIGH, LOW, M1=14, M2=6';
COMMENT ON COLUMN "tushare_norm_cb_factor_pro"."dmi_pdi_bfq" IS '动向指标-CLOSE, HIGH, LOW, M1=14, M2=6';
COMMENT ON COLUMN "tushare_norm_cb_factor_pro"."downdays" IS '连跌天数';
COMMENT ON COLUMN "tushare_norm_cb_factor_pro"."updays" IS '连涨天数';
COMMENT ON COLUMN "tushare_norm_cb_factor_pro"."dpo_bfq" IS '区间震荡线-CLOSE, M1=20, M2=10, M3=6';
COMMENT ON COLUMN "tushare_norm_cb_factor_pro"."madpo_bfq" IS '区间震荡线-CLOSE, M1=20, M2=10, M3=6';
COMMENT ON COLUMN "tushare_norm_cb_factor_pro"."ema_bfq_10" IS '指数移动平均-N=10';
COMMENT ON COLUMN "tushare_norm_cb_factor_pro"."ema_bfq_20" IS '指数移动平均-N=20';
COMMENT ON COLUMN "tushare_norm_cb_factor_pro"."ema_bfq_250" IS '指数移动平均-N=250';
COMMENT ON COLUMN "tushare_norm_cb_factor_pro"."ema_bfq_30" IS '指数移动平均-N=30';
COMMENT ON COLUMN "tushare_norm_cb_factor_pro"."ema_bfq_5" IS '指数移动平均-N=5';
COMMENT ON COLUMN "tushare_norm_cb_factor_pro"."ema_bfq_60" IS '指数移动平均-N=60';
COMMENT ON COLUMN "tushare_norm_cb_factor_pro"."ema_bfq_90" IS '指数移动平均-N=90';
COMMENT ON COLUMN "tushare_norm_cb_factor_pro"."emv_bfq" IS '简易波动指标-HIGH, LOW, VOL, N=14, M=9';
COMMENT ON COLUMN "tushare_norm_cb_factor_pro"."maemv_bfq" IS '简易波动指标-HIGH, LOW, VOL, N=14, M=9';
COMMENT ON COLUMN "tushare_norm_cb_factor_pro"."expma_12_bfq" IS 'EMA指数平均数指标-CLOSE, N1=12, N2=50';
COMMENT ON COLUMN "tushare_norm_cb_factor_pro"."expma_50_bfq" IS 'EMA指数平均数指标-CLOSE, N1=12, N2=50';
COMMENT ON COLUMN "tushare_norm_cb_factor_pro"."kdj_bfq" IS 'KDJ指标-CLOSE, HIGH, LOW, N=9, M1=3, M2=3';
COMMENT ON COLUMN "tushare_norm_cb_factor_pro"."kdj_d_bfq" IS 'KDJ指标-CLOSE, HIGH, LOW, N=9, M1=3, M2=3';
COMMENT ON COLUMN "tushare_norm_cb_factor_pro"."kdj_k_bfq" IS 'KDJ指标-CLOSE, HIGH, LOW, N=9, M1=3, M2=3';
COMMENT ON COLUMN "tushare_norm_cb_factor_pro"."ktn_down_bfq" IS '肯特纳交易通道, N选20日，ATR选10日-CLOSE, HIGH, LOW, N=20, M=10';
COMMENT ON COLUMN "tushare_norm_cb_factor_pro"."ktn_mid_bfq" IS '肯特纳交易通道, N选20日，ATR选10日-CLOSE, HIGH, LOW, N=20, M=10';
COMMENT ON COLUMN "tushare_norm_cb_factor_pro"."ktn_upper_bfq" IS '肯特纳交易通道, N选20日，ATR选10日-CLOSE, HIGH, LOW, N=20, M=10';
COMMENT ON COLUMN "tushare_norm_cb_factor_pro"."lowdays" IS 'LOWRANGE(LOW)表示当前最低价是近多少周期内最低价的最小值';
COMMENT ON COLUMN "tushare_norm_cb_factor_pro"."topdays" IS 'TOPRANGE(HIGH)表示当前最高价是近多少周期内最高价的最大值';
COMMENT ON COLUMN "tushare_norm_cb_factor_pro"."ma_bfq_10" IS '简单移动平均-N=10';
COMMENT ON COLUMN "tushare_norm_cb_factor_pro"."ma_bfq_20" IS '简单移动平均-N=20';
COMMENT ON COLUMN "tushare_norm_cb_factor_pro"."ma_bfq_250" IS '简单移动平均-N=250';
COMMENT ON COLUMN "tushare_norm_cb_factor_pro"."ma_bfq_30" IS '简单移动平均-N=30';
COMMENT ON COLUMN "tushare_norm_cb_factor_pro"."ma_bfq_5" IS '简单移动平均-N=5';
COMMENT ON COLUMN "tushare_norm_cb_factor_pro"."ma_bfq_60" IS '简单移动平均-N=60';
COMMENT ON COLUMN "tushare_norm_cb_factor_pro"."ma_bfq_90" IS '简单移动平均-N=90';
COMMENT ON COLUMN "tushare_norm_cb_factor_pro"."macd_bfq" IS 'MACD指标-CLOSE, SHORT=12, LONG=26, M=9';
COMMENT ON COLUMN "tushare_norm_cb_factor_pro"."macd_dea_bfq" IS 'MACD指标-CLOSE, SHORT=12, LONG=26, M=9';
COMMENT ON COLUMN "tushare_norm_cb_factor_pro"."macd_dif_bfq" IS 'MACD指标-CLOSE, SHORT=12, LONG=26, M=9';
COMMENT ON COLUMN "tushare_norm_cb_factor_pro"."mass_bfq" IS '梅斯线-HIGH, LOW, N1=9, N2=25, M=6';
COMMENT ON COLUMN "tushare_norm_cb_factor_pro"."ma_mass_bfq" IS '梅斯线-HIGH, LOW, N1=9, N2=25, M=6';
COMMENT ON COLUMN "tushare_norm_cb_factor_pro"."mfi_bfq" IS 'MFI指标是成交量的RSI指标-CLOSE, HIGH, LOW, VOL, N=14';
COMMENT ON COLUMN "tushare_norm_cb_factor_pro"."mtm_bfq" IS '动量指标-CLOSE, N=12, M=6';
COMMENT ON COLUMN "tushare_norm_cb_factor_pro"."mtmma_bfq" IS '动量指标-CLOSE, N=12, M=6';
COMMENT ON COLUMN "tushare_norm_cb_factor_pro"."obv_bfq" IS '能量潮指标-CLOSE, VOL';
COMMENT ON COLUMN "tushare_norm_cb_factor_pro"."psy_bfq" IS '投资者对股市涨跌产生心理波动的情绪指标-CLOSE, N=12, M=6';
COMMENT ON COLUMN "tushare_norm_cb_factor_pro"."psyma_bfq" IS '投资者对股市涨跌产生心理波动的情绪指标-CLOSE, N=12, M=6';
COMMENT ON COLUMN "tushare_norm_cb_factor_pro"."roc_bfq" IS '变动率指标-CLOSE, N=12, M=6';
COMMENT ON COLUMN "tushare_norm_cb_factor_pro"."maroc_bfq" IS '变动率指标-CLOSE, N=12, M=6';
COMMENT ON COLUMN "tushare_norm_cb_factor_pro"."rsi_bfq_12" IS 'RSI指标-CLOSE, N=12';
COMMENT ON COLUMN "tushare_norm_cb_factor_pro"."rsi_bfq_24" IS 'RSI指标-CLOSE, N=24';
COMMENT ON COLUMN "tushare_norm_cb_factor_pro"."rsi_bfq_6" IS 'RSI指标-CLOSE, N=6';
COMMENT ON COLUMN "tushare_norm_cb_factor_pro"."taq_down_bfq" IS '唐安奇通道(海龟)交易指标-HIGH, LOW, 20';
COMMENT ON COLUMN "tushare_norm_cb_factor_pro"."taq_mid_bfq" IS '唐安奇通道(海龟)交易指标-HIGH, LOW, 20';
COMMENT ON COLUMN "tushare_norm_cb_factor_pro"."taq_up_bfq" IS '唐安奇通道(海龟)交易指标-HIGH, LOW, 20';
COMMENT ON COLUMN "tushare_norm_cb_factor_pro"."trix_bfq" IS '三重指数平滑平均线-CLOSE, M1=12, M2=20';
COMMENT ON COLUMN "tushare_norm_cb_factor_pro"."trma_bfq" IS '三重指数平滑平均线-CLOSE, M1=12, M2=20';
COMMENT ON COLUMN "tushare_norm_cb_factor_pro"."vr_bfq" IS 'VR容量比率-CLOSE, VOL, M1=26';
COMMENT ON COLUMN "tushare_norm_cb_factor_pro"."wr_bfq" IS 'W&R 威廉指标-CLOSE, HIGH, LOW, N=10, N1=6';
COMMENT ON COLUMN "tushare_norm_cb_factor_pro"."wr1_bfq" IS 'W&R 威廉指标-CLOSE, HIGH, LOW, N=10, N1=6';
COMMENT ON COLUMN "tushare_norm_cb_factor_pro"."xsii_td1_bfq" IS '薛斯通道II-CLOSE, HIGH, LOW, N=102, M=7';
COMMENT ON COLUMN "tushare_norm_cb_factor_pro"."xsii_td2_bfq" IS '薛斯通道II-CLOSE, HIGH, LOW, N=102, M=7';
COMMENT ON COLUMN "tushare_norm_cb_factor_pro"."xsii_td3_bfq" IS '薛斯通道II-CLOSE, HIGH, LOW, N=102, M=7';
COMMENT ON COLUMN "tushare_norm_cb_factor_pro"."xsii_td4_bfq" IS '薛斯通道II-CLOSE, HIGH, LOW, N=102, M=7';

CREATE TABLE IF NOT EXISTS "tushare_norm_cb_issue" (
    _record_hash CHAR(64) PRIMARY KEY,
    _request_hash CHAR(64) NOT NULL,
    _source_doc_id INTEGER,
    _source_collected_at TIMESTAMPTZ NOT NULL,
    _first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _schema_version INTEGER NOT NULL DEFAULT 1,
    _extra_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    "ts_code" TEXT,
    "ann_date" DATE,
    "res_ann_date" DATE,
    "plan_issue_size" NUMERIC,
    "issue_size" NUMERIC,
    "issue_price" NUMERIC,
    "issue_type" TEXT,
    "issue_cost" NUMERIC,
    "onl_code" TEXT,
    "onl_name" TEXT,
    "onl_date" DATE,
    "onl_size" NUMERIC,
    "onl_pch_vol" NUMERIC,
    "onl_pch_num" BIGINT,
    "onl_pch_excess" NUMERIC,
    "onl_winning_rate" NUMERIC,
    "shd_ration_code" TEXT,
    "shd_ration_name" TEXT,
    "shd_ration_date" DATE,
    "shd_ration_record_date" DATE,
    "shd_ration_pay_date" DATE,
    "shd_ration_price" NUMERIC,
    "shd_ration_ratio" NUMERIC,
    "shd_ration_size" NUMERIC,
    "shd_ration_vol" NUMERIC,
    "shd_ration_num" BIGINT,
    "shd_ration_excess" NUMERIC,
    "offl_size" NUMERIC,
    "offl_deposit" NUMERIC,
    "offl_pch_vol" NUMERIC,
    "offl_pch_num" BIGINT,
    "offl_pch_excess" NUMERIC,
    "offl_winning_rate" NUMERIC,
    "lead_underwriter" TEXT,
    "lead_underwriter_vol" NUMERIC
);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_cb_issue_source" ON "tushare_norm_cb_issue" (_source_collected_at DESC);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_cb_issue_date" ON "tushare_norm_cb_issue" ("ann_date" DESC);
COMMENT ON TABLE "tushare_norm_cb_issue" IS '可转债发行；契约驱动标准化表' ;
COMMENT ON COLUMN "tushare_norm_cb_issue"."ts_code" IS '转债代码';
COMMENT ON COLUMN "tushare_norm_cb_issue"."ann_date" IS '发行公告日';
COMMENT ON COLUMN "tushare_norm_cb_issue"."res_ann_date" IS '发行结果公告日';
COMMENT ON COLUMN "tushare_norm_cb_issue"."plan_issue_size" IS '计划发行总额（元）';
COMMENT ON COLUMN "tushare_norm_cb_issue"."issue_size" IS '发行总额（元）';
COMMENT ON COLUMN "tushare_norm_cb_issue"."issue_price" IS '发行价格';
COMMENT ON COLUMN "tushare_norm_cb_issue"."issue_type" IS '发行方式';
COMMENT ON COLUMN "tushare_norm_cb_issue"."issue_cost" IS '发行费用（元）';
COMMENT ON COLUMN "tushare_norm_cb_issue"."onl_code" IS '网上申购代码';
COMMENT ON COLUMN "tushare_norm_cb_issue"."onl_name" IS '网上申购简称';
COMMENT ON COLUMN "tushare_norm_cb_issue"."onl_date" IS '网上发行日期';
COMMENT ON COLUMN "tushare_norm_cb_issue"."onl_size" IS '网上发行总额（张）';
COMMENT ON COLUMN "tushare_norm_cb_issue"."onl_pch_vol" IS '网上发行有效申购数量（张）';
COMMENT ON COLUMN "tushare_norm_cb_issue"."onl_pch_num" IS '网上发行有效申购户数';
COMMENT ON COLUMN "tushare_norm_cb_issue"."onl_pch_excess" IS '网上发行超额认购倍数';
COMMENT ON COLUMN "tushare_norm_cb_issue"."onl_winning_rate" IS '网上发行中签率（%）';
COMMENT ON COLUMN "tushare_norm_cb_issue"."shd_ration_code" IS '老股东配售代码';
COMMENT ON COLUMN "tushare_norm_cb_issue"."shd_ration_name" IS '老股东配售简称';
COMMENT ON COLUMN "tushare_norm_cb_issue"."shd_ration_date" IS '老股东配售日';
COMMENT ON COLUMN "tushare_norm_cb_issue"."shd_ration_record_date" IS '老股东配售股权登记日';
COMMENT ON COLUMN "tushare_norm_cb_issue"."shd_ration_pay_date" IS '老股东配售缴款日';
COMMENT ON COLUMN "tushare_norm_cb_issue"."shd_ration_price" IS '老股东配售价格';
COMMENT ON COLUMN "tushare_norm_cb_issue"."shd_ration_ratio" IS '老股东配售比例';
COMMENT ON COLUMN "tushare_norm_cb_issue"."shd_ration_size" IS '老股东配售数量（张）';
COMMENT ON COLUMN "tushare_norm_cb_issue"."shd_ration_vol" IS '老股东配售有效申购数量（张）';
COMMENT ON COLUMN "tushare_norm_cb_issue"."shd_ration_num" IS '老股东配售有效申购户数';
COMMENT ON COLUMN "tushare_norm_cb_issue"."shd_ration_excess" IS '老股东配售超额认购倍数';
COMMENT ON COLUMN "tushare_norm_cb_issue"."offl_size" IS '网下发行总额（张）';
COMMENT ON COLUMN "tushare_norm_cb_issue"."offl_deposit" IS '网下发行定金比例（%）';
COMMENT ON COLUMN "tushare_norm_cb_issue"."offl_pch_vol" IS '网下发行有效申购数量（张）';
COMMENT ON COLUMN "tushare_norm_cb_issue"."offl_pch_num" IS '网下发行有效申购户数';
COMMENT ON COLUMN "tushare_norm_cb_issue"."offl_pch_excess" IS '网下发行超额认购倍数';
COMMENT ON COLUMN "tushare_norm_cb_issue"."offl_winning_rate" IS '网下发行中签率';
COMMENT ON COLUMN "tushare_norm_cb_issue"."lead_underwriter" IS '主承销商';
COMMENT ON COLUMN "tushare_norm_cb_issue"."lead_underwriter_vol" IS '主承销商包销数量（张）';

CREATE TABLE IF NOT EXISTS "tushare_norm_cb_rate" (
    _record_hash CHAR(64) PRIMARY KEY,
    _request_hash CHAR(64) NOT NULL,
    _source_doc_id INTEGER,
    _source_collected_at TIMESTAMPTZ NOT NULL,
    _first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _schema_version INTEGER NOT NULL DEFAULT 1,
    _extra_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    "ts_code" TEXT,
    "rate_freq" BIGINT,
    "rate_start_date" DATE,
    "rate_end_date" DATE,
    "coupon_rate" NUMERIC
);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_cb_rate_source" ON "tushare_norm_cb_rate" (_source_collected_at DESC);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_cb_rate_date" ON "tushare_norm_cb_rate" ("rate_end_date" DESC);
COMMENT ON TABLE "tushare_norm_cb_rate" IS '可转债票面利率；契约驱动标准化表' ;
COMMENT ON COLUMN "tushare_norm_cb_rate"."ts_code" IS '转债代码';
COMMENT ON COLUMN "tushare_norm_cb_rate"."rate_freq" IS '付息频率(次/年)';
COMMENT ON COLUMN "tushare_norm_cb_rate"."rate_start_date" IS '付息开始日期';
COMMENT ON COLUMN "tushare_norm_cb_rate"."rate_end_date" IS '付息结束日期';
COMMENT ON COLUMN "tushare_norm_cb_rate"."coupon_rate" IS '票面利率(%)';

CREATE TABLE IF NOT EXISTS "tushare_norm_cb_rating" (
    _record_hash CHAR(64) PRIMARY KEY,
    _request_hash CHAR(64) NOT NULL,
    _source_doc_id INTEGER,
    _source_collected_at TIMESTAMPTZ NOT NULL,
    _first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _schema_version INTEGER NOT NULL DEFAULT 1,
    _extra_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    "ts_code" TEXT,
    "ann_date" DATE,
    "rating_date" DATE,
    "rating_com_name" TEXT,
    "rating_way" TEXT,
    "rating_type" TEXT,
    "rating" TEXT,
    "rating_outlook" TEXT
);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_cb_rating_source" ON "tushare_norm_cb_rating" (_source_collected_at DESC);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_cb_rating_date" ON "tushare_norm_cb_rating" ("ann_date" DESC);
COMMENT ON TABLE "tushare_norm_cb_rating" IS '获取可转债评级历史记录；契约驱动标准化表' ;
COMMENT ON COLUMN "tushare_norm_cb_rating"."ts_code" IS '转债代码';
COMMENT ON COLUMN "tushare_norm_cb_rating"."ann_date" IS '评级发布日期';
COMMENT ON COLUMN "tushare_norm_cb_rating"."rating_date" IS '评级日期';
COMMENT ON COLUMN "tushare_norm_cb_rating"."rating_com_name" IS '评级机构';
COMMENT ON COLUMN "tushare_norm_cb_rating"."rating_way" IS '评级方式';
COMMENT ON COLUMN "tushare_norm_cb_rating"."rating_type" IS '评级类别';
COMMENT ON COLUMN "tushare_norm_cb_rating"."rating" IS '信用等级';
COMMENT ON COLUMN "tushare_norm_cb_rating"."rating_outlook" IS '评级展望';

CREATE TABLE IF NOT EXISTS "tushare_norm_cb_share" (
    _record_hash CHAR(64) PRIMARY KEY,
    _request_hash CHAR(64) NOT NULL,
    _source_doc_id INTEGER,
    _source_collected_at TIMESTAMPTZ NOT NULL,
    _first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _schema_version INTEGER NOT NULL DEFAULT 1,
    _extra_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    "ts_code" TEXT,
    "bond_short_name" TEXT,
    "publish_date" DATE,
    "end_date" DATE,
    "issue_size" NUMERIC,
    "convert_price_initial" NUMERIC,
    "convert_price" NUMERIC,
    "convert_val" NUMERIC,
    "convert_vol" NUMERIC,
    "convert_ratio" NUMERIC,
    "acc_convert_val" NUMERIC,
    "acc_convert_vol" NUMERIC,
    "acc_convert_ratio" NUMERIC,
    "remain_size" NUMERIC,
    "total_shares" NUMERIC
);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_cb_share_source" ON "tushare_norm_cb_share" (_source_collected_at DESC);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_cb_share_date" ON "tushare_norm_cb_share" ("end_date" DESC);
COMMENT ON TABLE "tushare_norm_cb_share" IS '可转债转股结果；契约驱动标准化表' ;
COMMENT ON COLUMN "tushare_norm_cb_share"."ts_code" IS '债券代码';
COMMENT ON COLUMN "tushare_norm_cb_share"."bond_short_name" IS '债券简称';
COMMENT ON COLUMN "tushare_norm_cb_share"."publish_date" IS '公告日期';
COMMENT ON COLUMN "tushare_norm_cb_share"."end_date" IS '统计截止日期';
COMMENT ON COLUMN "tushare_norm_cb_share"."issue_size" IS '可转债发行总额';
COMMENT ON COLUMN "tushare_norm_cb_share"."convert_price_initial" IS '初始转换价格';
COMMENT ON COLUMN "tushare_norm_cb_share"."convert_price" IS '本次转换价格';
COMMENT ON COLUMN "tushare_norm_cb_share"."convert_val" IS '本次转股金额';
COMMENT ON COLUMN "tushare_norm_cb_share"."convert_vol" IS '本次转股数量';
COMMENT ON COLUMN "tushare_norm_cb_share"."convert_ratio" IS '本次转股比例';
COMMENT ON COLUMN "tushare_norm_cb_share"."acc_convert_val" IS '累计转股金额';
COMMENT ON COLUMN "tushare_norm_cb_share"."acc_convert_vol" IS '累计转股数量';
COMMENT ON COLUMN "tushare_norm_cb_share"."acc_convert_ratio" IS '累计转股比例';
COMMENT ON COLUMN "tushare_norm_cb_share"."remain_size" IS '可转债剩余金额';
COMMENT ON COLUMN "tushare_norm_cb_share"."total_shares" IS '转股后总股本';

CREATE TABLE IF NOT EXISTS "tushare_norm_ci_daily" (
    _record_hash CHAR(64) PRIMARY KEY,
    _request_hash CHAR(64) NOT NULL,
    _source_doc_id INTEGER,
    _source_collected_at TIMESTAMPTZ NOT NULL,
    _first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _schema_version INTEGER NOT NULL DEFAULT 1,
    _extra_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    "ts_code" TEXT,
    "trade_date" DATE,
    "open" NUMERIC,
    "low" NUMERIC,
    "high" NUMERIC,
    "close" NUMERIC,
    "pre_close" NUMERIC,
    "change" NUMERIC,
    "pct_change" NUMERIC,
    "vol" NUMERIC,
    "amount" NUMERIC
);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_ci_daily_source" ON "tushare_norm_ci_daily" (_source_collected_at DESC);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_ci_daily_date" ON "tushare_norm_ci_daily" ("trade_date" DESC);
COMMENT ON TABLE "tushare_norm_ci_daily" IS '中信行业指数行情；契约驱动标准化表' ;
COMMENT ON COLUMN "tushare_norm_ci_daily"."ts_code" IS '指数代码';
COMMENT ON COLUMN "tushare_norm_ci_daily"."trade_date" IS '交易日期';
COMMENT ON COLUMN "tushare_norm_ci_daily"."open" IS '开盘点位';
COMMENT ON COLUMN "tushare_norm_ci_daily"."low" IS '最低点位';
COMMENT ON COLUMN "tushare_norm_ci_daily"."high" IS '最高点位';
COMMENT ON COLUMN "tushare_norm_ci_daily"."close" IS '收盘点位';
COMMENT ON COLUMN "tushare_norm_ci_daily"."pre_close" IS '昨日收盘点位';
COMMENT ON COLUMN "tushare_norm_ci_daily"."change" IS '涨跌点位';
COMMENT ON COLUMN "tushare_norm_ci_daily"."pct_change" IS '涨跌幅';
COMMENT ON COLUMN "tushare_norm_ci_daily"."vol" IS '成交量（万股）';
COMMENT ON COLUMN "tushare_norm_ci_daily"."amount" IS '成交额（万元）';

CREATE TABLE IF NOT EXISTS "tushare_norm_ci_index_member" (
    _record_hash CHAR(64) PRIMARY KEY,
    _request_hash CHAR(64) NOT NULL,
    _source_doc_id INTEGER,
    _source_collected_at TIMESTAMPTZ NOT NULL,
    _first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _schema_version INTEGER NOT NULL DEFAULT 1,
    _extra_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    "l1_code" TEXT,
    "l1_name" TEXT,
    "l2_code" TEXT,
    "l2_name" TEXT,
    "l3_code" TEXT,
    "l3_name" TEXT,
    "ts_code" TEXT,
    "name" TEXT,
    "in_date" DATE,
    "out_date" DATE,
    "is_new" TEXT
);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_ci_index_member_source" ON "tushare_norm_ci_index_member" (_source_collected_at DESC);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_ci_index_member_date" ON "tushare_norm_ci_index_member" ("in_date" DESC);
COMMENT ON TABLE "tushare_norm_ci_index_member" IS '中信行业成分；契约驱动标准化表' ;
COMMENT ON COLUMN "tushare_norm_ci_index_member"."l1_code" IS '一级行业代码';
COMMENT ON COLUMN "tushare_norm_ci_index_member"."l1_name" IS '一级行业名称';
COMMENT ON COLUMN "tushare_norm_ci_index_member"."l2_code" IS '二级行业代码';
COMMENT ON COLUMN "tushare_norm_ci_index_member"."l2_name" IS '二级行业名称';
COMMENT ON COLUMN "tushare_norm_ci_index_member"."l3_code" IS '三级行业代码';
COMMENT ON COLUMN "tushare_norm_ci_index_member"."l3_name" IS '三级行业名称';
COMMENT ON COLUMN "tushare_norm_ci_index_member"."ts_code" IS '成分股票代码';
COMMENT ON COLUMN "tushare_norm_ci_index_member"."name" IS '成分股票名称';
COMMENT ON COLUMN "tushare_norm_ci_index_member"."in_date" IS '纳入日期';
COMMENT ON COLUMN "tushare_norm_ci_index_member"."out_date" IS '剔除日期';
COMMENT ON COLUMN "tushare_norm_ci_index_member"."is_new" IS '是否最新Y是N否';

CREATE TABLE IF NOT EXISTS "tushare_norm_cn_cpi" (
    _record_hash CHAR(64) PRIMARY KEY,
    _request_hash CHAR(64) NOT NULL,
    _source_doc_id INTEGER,
    _source_collected_at TIMESTAMPTZ NOT NULL,
    _first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _schema_version INTEGER NOT NULL DEFAULT 1,
    _extra_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    "month" TEXT,
    "nt_val" NUMERIC,
    "nt_yoy" NUMERIC,
    "nt_mom" NUMERIC,
    "nt_accu" NUMERIC,
    "town_val" NUMERIC,
    "town_yoy" NUMERIC,
    "town_mom" NUMERIC,
    "town_accu" NUMERIC,
    "cnt_val" NUMERIC,
    "cnt_yoy" NUMERIC,
    "cnt_mom" NUMERIC,
    "cnt_accu" NUMERIC
);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_cn_cpi_source" ON "tushare_norm_cn_cpi" (_source_collected_at DESC);
COMMENT ON TABLE "tushare_norm_cn_cpi" IS '居民消费价格指数；契约驱动标准化表' ;
COMMENT ON COLUMN "tushare_norm_cn_cpi"."month" IS '月份YYYYMM';
COMMENT ON COLUMN "tushare_norm_cn_cpi"."nt_val" IS '全国当月值';
COMMENT ON COLUMN "tushare_norm_cn_cpi"."nt_yoy" IS '全国同比（%）';
COMMENT ON COLUMN "tushare_norm_cn_cpi"."nt_mom" IS '全国环比（%）';
COMMENT ON COLUMN "tushare_norm_cn_cpi"."nt_accu" IS '全国累计值';
COMMENT ON COLUMN "tushare_norm_cn_cpi"."town_val" IS '城市当月值';
COMMENT ON COLUMN "tushare_norm_cn_cpi"."town_yoy" IS '城市同比（%）';
COMMENT ON COLUMN "tushare_norm_cn_cpi"."town_mom" IS '城市环比（%）';
COMMENT ON COLUMN "tushare_norm_cn_cpi"."town_accu" IS '城市累计值';
COMMENT ON COLUMN "tushare_norm_cn_cpi"."cnt_val" IS '农村当月值';
COMMENT ON COLUMN "tushare_norm_cn_cpi"."cnt_yoy" IS '农村同比（%）';
COMMENT ON COLUMN "tushare_norm_cn_cpi"."cnt_mom" IS '农村环比（%）';
COMMENT ON COLUMN "tushare_norm_cn_cpi"."cnt_accu" IS '农村累计值';

CREATE TABLE IF NOT EXISTS "tushare_norm_cn_gdp" (
    _record_hash CHAR(64) PRIMARY KEY,
    _request_hash CHAR(64) NOT NULL,
    _source_doc_id INTEGER,
    _source_collected_at TIMESTAMPTZ NOT NULL,
    _first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _schema_version INTEGER NOT NULL DEFAULT 1,
    _extra_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    "quarter" TEXT,
    "gdp" NUMERIC,
    "gdp_yoy" NUMERIC,
    "pi" NUMERIC,
    "pi_yoy" NUMERIC,
    "si" NUMERIC,
    "si_yoy" NUMERIC,
    "ti" NUMERIC,
    "ti_yoy" NUMERIC
);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_cn_gdp_source" ON "tushare_norm_cn_gdp" (_source_collected_at DESC);
COMMENT ON TABLE "tushare_norm_cn_gdp" IS 'GDP数据；契约驱动标准化表' ;
COMMENT ON COLUMN "tushare_norm_cn_gdp"."quarter" IS '季度';
COMMENT ON COLUMN "tushare_norm_cn_gdp"."gdp" IS 'GDP累计值（亿元）';
COMMENT ON COLUMN "tushare_norm_cn_gdp"."gdp_yoy" IS '当季同比增速（%）';
COMMENT ON COLUMN "tushare_norm_cn_gdp"."pi" IS '第一产业累计值（亿元）';
COMMENT ON COLUMN "tushare_norm_cn_gdp"."pi_yoy" IS '第一产业同比增速（%）';
COMMENT ON COLUMN "tushare_norm_cn_gdp"."si" IS '第二产业累计值（亿元）';
COMMENT ON COLUMN "tushare_norm_cn_gdp"."si_yoy" IS '第二产业同比增速（%）';
COMMENT ON COLUMN "tushare_norm_cn_gdp"."ti" IS '第三产业累计值（亿元）';
COMMENT ON COLUMN "tushare_norm_cn_gdp"."ti_yoy" IS '第三产业同比增速（%）';

CREATE TABLE IF NOT EXISTS "tushare_norm_cn_m" (
    _record_hash CHAR(64) PRIMARY KEY,
    _request_hash CHAR(64) NOT NULL,
    _source_doc_id INTEGER,
    _source_collected_at TIMESTAMPTZ NOT NULL,
    _first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _schema_version INTEGER NOT NULL DEFAULT 1,
    _extra_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    "month" TEXT,
    "m0" NUMERIC,
    "m0_yoy" NUMERIC,
    "m0_mom" NUMERIC,
    "m1" NUMERIC,
    "m1_yoy" NUMERIC,
    "m1_mom" NUMERIC,
    "m2" NUMERIC,
    "m2_yoy" NUMERIC,
    "m2_mom" NUMERIC
);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_cn_m_source" ON "tushare_norm_cn_m" (_source_collected_at DESC);
COMMENT ON TABLE "tushare_norm_cn_m" IS '货币供应量；契约驱动标准化表' ;
COMMENT ON COLUMN "tushare_norm_cn_m"."month" IS '月份YYYYMM';
COMMENT ON COLUMN "tushare_norm_cn_m"."m0" IS 'M0（亿元）';
COMMENT ON COLUMN "tushare_norm_cn_m"."m0_yoy" IS 'M0同比（%）';
COMMENT ON COLUMN "tushare_norm_cn_m"."m0_mom" IS 'M0环比（%）';
COMMENT ON COLUMN "tushare_norm_cn_m"."m1" IS 'M1（亿元）';
COMMENT ON COLUMN "tushare_norm_cn_m"."m1_yoy" IS 'M1同比（%）';
COMMENT ON COLUMN "tushare_norm_cn_m"."m1_mom" IS 'M1环比（%）';
COMMENT ON COLUMN "tushare_norm_cn_m"."m2" IS 'M2（亿元）';
COMMENT ON COLUMN "tushare_norm_cn_m"."m2_yoy" IS 'M2同比（%）';
COMMENT ON COLUMN "tushare_norm_cn_m"."m2_mom" IS 'M2环比（%）';

CREATE TABLE IF NOT EXISTS "tushare_norm_cn_pmi" (
    _record_hash CHAR(64) PRIMARY KEY,
    _request_hash CHAR(64) NOT NULL,
    _source_doc_id INTEGER,
    _source_collected_at TIMESTAMPTZ NOT NULL,
    _first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _schema_version INTEGER NOT NULL DEFAULT 1,
    _extra_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    "month" TEXT,
    "pmi010000" NUMERIC,
    "pmi010100" NUMERIC,
    "pmi010200" NUMERIC,
    "pmi010300" NUMERIC,
    "pmi010400" NUMERIC,
    "pmi010401" NUMERIC,
    "pmi010402" NUMERIC,
    "pmi010403" NUMERIC,
    "pmi010500" NUMERIC,
    "pmi010501" NUMERIC,
    "pmi010502" NUMERIC,
    "pmi010503" NUMERIC,
    "pmi010600" NUMERIC,
    "pmi010601" NUMERIC,
    "pmi010602" NUMERIC,
    "pmi010603" NUMERIC,
    "pmi010700" NUMERIC,
    "pmi010701" NUMERIC,
    "pmi010702" NUMERIC,
    "pmi010703" NUMERIC,
    "pmi010800" NUMERIC,
    "pmi010801" NUMERIC,
    "pmi010802" NUMERIC,
    "pmi010803" NUMERIC,
    "pmi010900" NUMERIC,
    "pmi011000" NUMERIC,
    "pmi011100" NUMERIC,
    "pmi011200" NUMERIC,
    "pmi011300" NUMERIC,
    "pmi011400" NUMERIC,
    "pmi011500" NUMERIC,
    "pmi011600" NUMERIC,
    "pmi011700" NUMERIC,
    "pmi011800" NUMERIC,
    "pmi011900" NUMERIC,
    "pmi012000" NUMERIC,
    "pmi020100" NUMERIC,
    "pmi020101" NUMERIC,
    "pmi020102" NUMERIC,
    "pmi020200" NUMERIC,
    "pmi020201" NUMERIC,
    "pmi020202" NUMERIC,
    "pmi020300" NUMERIC,
    "pmi020301" NUMERIC,
    "pmi020302" NUMERIC,
    "pmi020400" NUMERIC,
    "pmi020401" NUMERIC,
    "pmi020402" NUMERIC,
    "pmi020500" NUMERIC,
    "pmi020501" NUMERIC,
    "pmi020502" NUMERIC,
    "pmi020600" NUMERIC,
    "pmi020601" NUMERIC,
    "pmi020602" NUMERIC,
    "pmi020700" NUMERIC,
    "pmi020800" NUMERIC,
    "pmi020900" NUMERIC,
    "pmi021000" NUMERIC,
    "pmi030000" NUMERIC
);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_cn_pmi_source" ON "tushare_norm_cn_pmi" (_source_collected_at DESC);
COMMENT ON TABLE "tushare_norm_cn_pmi" IS '采购经理人指数；契约驱动标准化表' ;
COMMENT ON COLUMN "tushare_norm_cn_pmi"."month" IS '月份YYYYMM';
COMMENT ON COLUMN "tushare_norm_cn_pmi"."pmi010000" IS '制造业PMI';
COMMENT ON COLUMN "tushare_norm_cn_pmi"."pmi010100" IS '制造业PMI:企业规模/大型企业';
COMMENT ON COLUMN "tushare_norm_cn_pmi"."pmi010200" IS '制造业PMI:企业规模/中型企业';
COMMENT ON COLUMN "tushare_norm_cn_pmi"."pmi010300" IS '制造业PMI:企业规模/小型企业';
COMMENT ON COLUMN "tushare_norm_cn_pmi"."pmi010400" IS '制造业PMI:构成指数/生产指数';
COMMENT ON COLUMN "tushare_norm_cn_pmi"."pmi010401" IS '制造业PMI:构成指数/生产指数:企业规模/大型企业';
COMMENT ON COLUMN "tushare_norm_cn_pmi"."pmi010402" IS '制造业PMI:构成指数/生产指数:企业规模/中型企业';
COMMENT ON COLUMN "tushare_norm_cn_pmi"."pmi010403" IS '制造业PMI:构成指数/生产指数:企业规模/小型企业';
COMMENT ON COLUMN "tushare_norm_cn_pmi"."pmi010500" IS '制造业PMI:构成指数/新订单指数';
COMMENT ON COLUMN "tushare_norm_cn_pmi"."pmi010501" IS '制造业PMI:构成指数/新订单指数:企业规模/大型企业';
COMMENT ON COLUMN "tushare_norm_cn_pmi"."pmi010502" IS '制造业PMI:构成指数/新订单指数:企业规模/中型企业';
COMMENT ON COLUMN "tushare_norm_cn_pmi"."pmi010503" IS '制造业PMI:构成指数/新订单指数:企业规模/小型企业';
COMMENT ON COLUMN "tushare_norm_cn_pmi"."pmi010600" IS '制造业PMI:构成指数/供应商配送时间指数';
COMMENT ON COLUMN "tushare_norm_cn_pmi"."pmi010601" IS '制造业PMI:构成指数/供应商配送时间指数:企业规模/大型企业';
COMMENT ON COLUMN "tushare_norm_cn_pmi"."pmi010602" IS '制造业PMI:构成指数/供应商配送时间指数:企业规模/中型企业';
COMMENT ON COLUMN "tushare_norm_cn_pmi"."pmi010603" IS '制造业PMI:构成指数/供应商配送时间指数:企业规模/小型企业';
COMMENT ON COLUMN "tushare_norm_cn_pmi"."pmi010700" IS '制造业PMI:构成指数/原材料库存指数';
COMMENT ON COLUMN "tushare_norm_cn_pmi"."pmi010701" IS '制造业PMI:构成指数/原材料库存指数:企业规模/大型企业';
COMMENT ON COLUMN "tushare_norm_cn_pmi"."pmi010702" IS '制造业PMI:构成指数/原材料库存指数:企业规模/中型企业';
COMMENT ON COLUMN "tushare_norm_cn_pmi"."pmi010703" IS '制造业PMI:构成指数/原材料库存指数:企业规模/小型企业';
COMMENT ON COLUMN "tushare_norm_cn_pmi"."pmi010800" IS '制造业PMI:构成指数/从业人员指数';
COMMENT ON COLUMN "tushare_norm_cn_pmi"."pmi010801" IS '制造业PMI:构成指数/从业人员指数:企业规模/大型企业';
COMMENT ON COLUMN "tushare_norm_cn_pmi"."pmi010802" IS '制造业PMI:构成指数/从业人员指数:企业规模/中型企业';
COMMENT ON COLUMN "tushare_norm_cn_pmi"."pmi010803" IS '制造业PMI:构成指数/从业人员指数:企业规模/小型企业';
COMMENT ON COLUMN "tushare_norm_cn_pmi"."pmi010900" IS '制造业PMI:其他/新出口订单';
COMMENT ON COLUMN "tushare_norm_cn_pmi"."pmi011000" IS '制造业PMI:其他/进口';
COMMENT ON COLUMN "tushare_norm_cn_pmi"."pmi011100" IS '制造业PMI:其他/采购量';
COMMENT ON COLUMN "tushare_norm_cn_pmi"."pmi011200" IS '制造业PMI:其他/主要原材料购进价格';
COMMENT ON COLUMN "tushare_norm_cn_pmi"."pmi011300" IS '制造业PMI:其他/出厂价格';
COMMENT ON COLUMN "tushare_norm_cn_pmi"."pmi011400" IS '制造业PMI:其他/产成品库存';
COMMENT ON COLUMN "tushare_norm_cn_pmi"."pmi011500" IS '制造业PMI:其他/在手订单';
COMMENT ON COLUMN "tushare_norm_cn_pmi"."pmi011600" IS '制造业PMI:其他/生产经营活动预期';
COMMENT ON COLUMN "tushare_norm_cn_pmi"."pmi011700" IS '制造业PMI:分行业/装备制造业';
COMMENT ON COLUMN "tushare_norm_cn_pmi"."pmi011800" IS '制造业PMI:分行业/高技术制造业';
COMMENT ON COLUMN "tushare_norm_cn_pmi"."pmi011900" IS '制造业PMI:分行业/基础原材料制造业';
COMMENT ON COLUMN "tushare_norm_cn_pmi"."pmi012000" IS '制造业PMI:分行业/消费品制造业';
COMMENT ON COLUMN "tushare_norm_cn_pmi"."pmi020100" IS '非制造业PMI:商务活动';
COMMENT ON COLUMN "tushare_norm_cn_pmi"."pmi020101" IS '非制造业PMI:商务活动:分行业/建筑业';
COMMENT ON COLUMN "tushare_norm_cn_pmi"."pmi020102" IS '非制造业PMI:商务活动:分行业/服务业业';
COMMENT ON COLUMN "tushare_norm_cn_pmi"."pmi020200" IS '非制造业PMI:新订单指数';
COMMENT ON COLUMN "tushare_norm_cn_pmi"."pmi020201" IS '非制造业PMI:新订单指数:分行业/建筑业';
COMMENT ON COLUMN "tushare_norm_cn_pmi"."pmi020202" IS '非制造业PMI:新订单指数:分行业/服务业';
COMMENT ON COLUMN "tushare_norm_cn_pmi"."pmi020300" IS '非制造业PMI:投入品价格指数';
COMMENT ON COLUMN "tushare_norm_cn_pmi"."pmi020301" IS '非制造业PMI:投入品价格指数:分行业/建筑业';
COMMENT ON COLUMN "tushare_norm_cn_pmi"."pmi020302" IS '非制造业PMI:投入品价格指数:分行业/服务业';
COMMENT ON COLUMN "tushare_norm_cn_pmi"."pmi020400" IS '非制造业PMI:销售价格指数';
COMMENT ON COLUMN "tushare_norm_cn_pmi"."pmi020401" IS '非制造业PMI:销售价格指数:分行业/建筑业';
COMMENT ON COLUMN "tushare_norm_cn_pmi"."pmi020402" IS '非制造业PMI:销售价格指数:分行业/服务业';
COMMENT ON COLUMN "tushare_norm_cn_pmi"."pmi020500" IS '非制造业PMI:从业人员指数';
COMMENT ON COLUMN "tushare_norm_cn_pmi"."pmi020501" IS '非制造业PMI:从业人员指数:分行业/建筑业';
COMMENT ON COLUMN "tushare_norm_cn_pmi"."pmi020502" IS '非制造业PMI:从业人员指数:分行业/服务业';
COMMENT ON COLUMN "tushare_norm_cn_pmi"."pmi020600" IS '非制造业PMI:业务活动预期指数';
COMMENT ON COLUMN "tushare_norm_cn_pmi"."pmi020601" IS '非制造业PMI:业务活动预期指数:分行业/建筑业';
COMMENT ON COLUMN "tushare_norm_cn_pmi"."pmi020602" IS '非制造业PMI:业务活动预期指数:分行业/服务业';
COMMENT ON COLUMN "tushare_norm_cn_pmi"."pmi020700" IS '非制造业PMI:新出口订单';
COMMENT ON COLUMN "tushare_norm_cn_pmi"."pmi020800" IS '非制造业PMI:在手订单';
COMMENT ON COLUMN "tushare_norm_cn_pmi"."pmi020900" IS '非制造业PMI:存货';
COMMENT ON COLUMN "tushare_norm_cn_pmi"."pmi021000" IS '非制造业PMI:供应商配送时间';
COMMENT ON COLUMN "tushare_norm_cn_pmi"."pmi030000" IS '中国综合PMI:产出指数';

CREATE TABLE IF NOT EXISTS "tushare_norm_cn_ppi" (
    _record_hash CHAR(64) PRIMARY KEY,
    _request_hash CHAR(64) NOT NULL,
    _source_doc_id INTEGER,
    _source_collected_at TIMESTAMPTZ NOT NULL,
    _first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _schema_version INTEGER NOT NULL DEFAULT 1,
    _extra_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    "month" TEXT,
    "ppi_yoy" NUMERIC,
    "ppi_mp_yoy" NUMERIC,
    "ppi_mp_qm_yoy" NUMERIC,
    "ppi_mp_rm_yoy" NUMERIC,
    "ppi_mp_p_yoy" NUMERIC,
    "ppi_cg_yoy" NUMERIC,
    "ppi_cg_f_yoy" NUMERIC,
    "ppi_cg_c_yoy" NUMERIC,
    "ppi_cg_adu_yoy" NUMERIC,
    "ppi_cg_dcg_yoy" NUMERIC,
    "ppi_mom" NUMERIC,
    "ppi_mp_mom" NUMERIC,
    "ppi_mp_qm_mom" NUMERIC,
    "ppi_mp_rm_mom" NUMERIC,
    "ppi_mp_p_mom" NUMERIC,
    "ppi_cg_mom" NUMERIC,
    "ppi_cg_f_mom" NUMERIC,
    "ppi_cg_c_mom" NUMERIC,
    "ppi_cg_adu_mom" NUMERIC,
    "ppi_cg_dcg_mom" NUMERIC,
    "ppi_accu" NUMERIC,
    "ppi_mp_accu" NUMERIC,
    "ppi_mp_qm_accu" NUMERIC,
    "ppi_mp_rm_accu" NUMERIC,
    "ppi_mp_p_accu" NUMERIC,
    "ppi_cg_accu" NUMERIC,
    "ppi_cg_f_accu" NUMERIC,
    "ppi_cg_c_accu" NUMERIC,
    "ppi_cg_adu_accu" NUMERIC,
    "ppi_cg_dcg_accu" NUMERIC
);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_cn_ppi_source" ON "tushare_norm_cn_ppi" (_source_collected_at DESC);
COMMENT ON TABLE "tushare_norm_cn_ppi" IS '工业生产者出厂价格指数；契约驱动标准化表' ;
COMMENT ON COLUMN "tushare_norm_cn_ppi"."month" IS '月份YYYYMM';
COMMENT ON COLUMN "tushare_norm_cn_ppi"."ppi_yoy" IS 'PPI：全部工业品：当月同比';
COMMENT ON COLUMN "tushare_norm_cn_ppi"."ppi_mp_yoy" IS 'PPI：生产资料：当月同比';
COMMENT ON COLUMN "tushare_norm_cn_ppi"."ppi_mp_qm_yoy" IS 'PPI：生产资料：采掘业：当月同比';
COMMENT ON COLUMN "tushare_norm_cn_ppi"."ppi_mp_rm_yoy" IS 'PPI：生产资料：原料业：当月同比';
COMMENT ON COLUMN "tushare_norm_cn_ppi"."ppi_mp_p_yoy" IS 'PPI：生产资料：加工业：当月同比';
COMMENT ON COLUMN "tushare_norm_cn_ppi"."ppi_cg_yoy" IS 'PPI：生活资料：当月同比';
COMMENT ON COLUMN "tushare_norm_cn_ppi"."ppi_cg_f_yoy" IS 'PPI：生活资料：食品类：当月同比';
COMMENT ON COLUMN "tushare_norm_cn_ppi"."ppi_cg_c_yoy" IS 'PPI：生活资料：衣着类：当月同比';
COMMENT ON COLUMN "tushare_norm_cn_ppi"."ppi_cg_adu_yoy" IS 'PPI：生活资料：一般日用品类：当月同比';
COMMENT ON COLUMN "tushare_norm_cn_ppi"."ppi_cg_dcg_yoy" IS 'PPI：生活资料：耐用消费品类：当月同比';
COMMENT ON COLUMN "tushare_norm_cn_ppi"."ppi_mom" IS 'PPI：全部工业品：环比';
COMMENT ON COLUMN "tushare_norm_cn_ppi"."ppi_mp_mom" IS 'PPI：生产资料：环比';
COMMENT ON COLUMN "tushare_norm_cn_ppi"."ppi_mp_qm_mom" IS 'PPI：生产资料：采掘业：环比';
COMMENT ON COLUMN "tushare_norm_cn_ppi"."ppi_mp_rm_mom" IS 'PPI：生产资料：原料业：环比';
COMMENT ON COLUMN "tushare_norm_cn_ppi"."ppi_mp_p_mom" IS 'PPI：生产资料：加工业：环比';
COMMENT ON COLUMN "tushare_norm_cn_ppi"."ppi_cg_mom" IS 'PPI：生活资料：环比';
COMMENT ON COLUMN "tushare_norm_cn_ppi"."ppi_cg_f_mom" IS 'PPI：生活资料：食品类：环比';
COMMENT ON COLUMN "tushare_norm_cn_ppi"."ppi_cg_c_mom" IS 'PPI：生活资料：衣着类：环比';
COMMENT ON COLUMN "tushare_norm_cn_ppi"."ppi_cg_adu_mom" IS 'PPI：生活资料：一般日用品类：环比';
COMMENT ON COLUMN "tushare_norm_cn_ppi"."ppi_cg_dcg_mom" IS 'PPI：生活资料：耐用消费品类：环比';
COMMENT ON COLUMN "tushare_norm_cn_ppi"."ppi_accu" IS 'PPI：全部工业品：累计同比';
COMMENT ON COLUMN "tushare_norm_cn_ppi"."ppi_mp_accu" IS 'PPI：生产资料：累计同比';
COMMENT ON COLUMN "tushare_norm_cn_ppi"."ppi_mp_qm_accu" IS 'PPI：生产资料：采掘业：累计同比';
COMMENT ON COLUMN "tushare_norm_cn_ppi"."ppi_mp_rm_accu" IS 'PPI：生产资料：原料业：累计同比';
COMMENT ON COLUMN "tushare_norm_cn_ppi"."ppi_mp_p_accu" IS 'PPI：生产资料：加工业：累计同比';
COMMENT ON COLUMN "tushare_norm_cn_ppi"."ppi_cg_accu" IS 'PPI：生活资料：累计同比';
COMMENT ON COLUMN "tushare_norm_cn_ppi"."ppi_cg_f_accu" IS 'PPI：生活资料：食品类：累计同比';
COMMENT ON COLUMN "tushare_norm_cn_ppi"."ppi_cg_c_accu" IS 'PPI：生活资料：衣着类：累计同比';
COMMENT ON COLUMN "tushare_norm_cn_ppi"."ppi_cg_adu_accu" IS 'PPI：生活资料：一般日用品类：累计同比';
COMMENT ON COLUMN "tushare_norm_cn_ppi"."ppi_cg_dcg_accu" IS 'PPI：生活资料：耐用消费品类：累计同比';

CREATE TABLE IF NOT EXISTS "tushare_norm_cn_schedule" (
    _record_hash CHAR(64) PRIMARY KEY,
    _request_hash CHAR(64) NOT NULL,
    _source_doc_id INTEGER,
    _source_collected_at TIMESTAMPTZ NOT NULL,
    _first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _schema_version INTEGER NOT NULL DEFAULT 1,
    _extra_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    "month" TEXT,
    "publish_date" DATE,
    "title" TEXT,
    "issuing_org" TEXT,
    "data_api" TEXT
);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_cn_schedule_source" ON "tushare_norm_cn_schedule" (_source_collected_at DESC);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_cn_schedule_date" ON "tushare_norm_cn_schedule" ("publish_date" DESC);
COMMENT ON TABLE "tushare_norm_cn_schedule" IS '中国经济数据发布日程；契约驱动标准化表' ;
COMMENT ON COLUMN "tushare_norm_cn_schedule"."month" IS '月份YYYYMM';
COMMENT ON COLUMN "tushare_norm_cn_schedule"."publish_date" IS '发布日期';
COMMENT ON COLUMN "tushare_norm_cn_schedule"."title" IS '发布数据';
COMMENT ON COLUMN "tushare_norm_cn_schedule"."issuing_org" IS '发布单位';
COMMENT ON COLUMN "tushare_norm_cn_schedule"."data_api" IS 'tushare对应接口';

CREATE TABLE IF NOT EXISTS "tushare_norm_daily_basic" (
    _record_hash CHAR(64) PRIMARY KEY,
    _request_hash CHAR(64) NOT NULL,
    _source_doc_id INTEGER,
    _source_collected_at TIMESTAMPTZ NOT NULL,
    _first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _schema_version INTEGER NOT NULL DEFAULT 1,
    _extra_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    "ts_code" TEXT,
    "trade_date" DATE,
    "close" NUMERIC,
    "turnover_rate" NUMERIC,
    "turnover_rate_f" NUMERIC,
    "volume_ratio" NUMERIC,
    "pe" NUMERIC,
    "pe_ttm" NUMERIC,
    "pb" NUMERIC,
    "ps" NUMERIC,
    "ps_ttm" NUMERIC,
    "dv_ratio" NUMERIC,
    "dv_ttm" NUMERIC,
    "total_share" NUMERIC,
    "float_share" NUMERIC,
    "free_share" NUMERIC,
    "total_mv" NUMERIC,
    "circ_mv" NUMERIC,
    "limit_status" BIGINT
);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_daily_basic_source" ON "tushare_norm_daily_basic" (_source_collected_at DESC);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_daily_basic_date" ON "tushare_norm_daily_basic" ("trade_date" DESC);
COMMENT ON TABLE "tushare_norm_daily_basic" IS '每日指标；契约驱动标准化表' ;
COMMENT ON COLUMN "tushare_norm_daily_basic"."ts_code" IS 'TS股票代码';
COMMENT ON COLUMN "tushare_norm_daily_basic"."trade_date" IS '交易日期';
COMMENT ON COLUMN "tushare_norm_daily_basic"."close" IS '当日收盘价';
COMMENT ON COLUMN "tushare_norm_daily_basic"."turnover_rate" IS '换手率 (成交量/无限售流通股数)';
COMMENT ON COLUMN "tushare_norm_daily_basic"."turnover_rate_f" IS '换手率（自由流通股）(成交量/自由流通股数)';
COMMENT ON COLUMN "tushare_norm_daily_basic"."volume_ratio" IS '量比 VOL/MA';
COMMENT ON COLUMN "tushare_norm_daily_basic"."pe" IS '市盈率（总市值/净利润， 亏损的PE为空）';
COMMENT ON COLUMN "tushare_norm_daily_basic"."pe_ttm" IS '市盈率（ 总市值/净利润TTM，亏损的PE为空）';
COMMENT ON COLUMN "tushare_norm_daily_basic"."pb" IS '市净率（总市值/(净资产-其他权益工具)）';
COMMENT ON COLUMN "tushare_norm_daily_basic"."ps" IS '市销率 (总市值/营业收入(最新年报))';
COMMENT ON COLUMN "tushare_norm_daily_basic"."ps_ttm" IS '市销率（TTM）(总市值/营业收入TTM)';
COMMENT ON COLUMN "tushare_norm_daily_basic"."dv_ratio" IS '股息率 （%），除息日发生在去年期间的派现';
COMMENT ON COLUMN "tushare_norm_daily_basic"."dv_ttm" IS '股息率（TTM）（%），除息日在近12个月且分红报告期在12个月以内的派现';
COMMENT ON COLUMN "tushare_norm_daily_basic"."total_share" IS '总股本 （万股）';
COMMENT ON COLUMN "tushare_norm_daily_basic"."float_share" IS '流通股本 （万股）';
COMMENT ON COLUMN "tushare_norm_daily_basic"."free_share" IS '自由流通股本 （万）';
COMMENT ON COLUMN "tushare_norm_daily_basic"."total_mv" IS '总市值 （万元）';
COMMENT ON COLUMN "tushare_norm_daily_basic"."circ_mv" IS '流通市值（万元）';
COMMENT ON COLUMN "tushare_norm_daily_basic"."limit_status" IS '收盘涨跌状态：0-平盘，1-上涨(不含涨停)，2-涨停(不含一字涨停)，3-一字涨停，4-下跌(不含跌停)，5-跌停(不含一字跌停)，6-一字跌停';

CREATE TABLE IF NOT EXISTS "tushare_norm_daily_info" (
    _record_hash CHAR(64) PRIMARY KEY,
    _request_hash CHAR(64) NOT NULL,
    _source_doc_id INTEGER,
    _source_collected_at TIMESTAMPTZ NOT NULL,
    _first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _schema_version INTEGER NOT NULL DEFAULT 1,
    _extra_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    "trade_date" DATE,
    "ts_code" TEXT,
    "ts_name" TEXT,
    "com_count" BIGINT,
    "total_share" NUMERIC,
    "float_share" NUMERIC,
    "total_mv" NUMERIC,
    "float_mv" NUMERIC,
    "amount" NUMERIC,
    "vol" NUMERIC,
    "trans_count" BIGINT,
    "pe" NUMERIC,
    "tr" NUMERIC,
    "exchange" TEXT
);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_daily_info_source" ON "tushare_norm_daily_info" (_source_collected_at DESC);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_daily_info_date" ON "tushare_norm_daily_info" ("trade_date" DESC);
COMMENT ON TABLE "tushare_norm_daily_info" IS '市场交易统计；契约驱动标准化表' ;
COMMENT ON COLUMN "tushare_norm_daily_info"."trade_date" IS '交易日期';
COMMENT ON COLUMN "tushare_norm_daily_info"."ts_code" IS '市场代码';
COMMENT ON COLUMN "tushare_norm_daily_info"."ts_name" IS '市场名称';
COMMENT ON COLUMN "tushare_norm_daily_info"."com_count" IS '挂牌数';
COMMENT ON COLUMN "tushare_norm_daily_info"."total_share" IS '总股本（亿股）';
COMMENT ON COLUMN "tushare_norm_daily_info"."float_share" IS '流通股本（亿股）';
COMMENT ON COLUMN "tushare_norm_daily_info"."total_mv" IS '总市值（亿元）';
COMMENT ON COLUMN "tushare_norm_daily_info"."float_mv" IS '流通市值（亿元）';
COMMENT ON COLUMN "tushare_norm_daily_info"."amount" IS '交易金额（亿元）';
COMMENT ON COLUMN "tushare_norm_daily_info"."vol" IS '成交量（亿股）';
COMMENT ON COLUMN "tushare_norm_daily_info"."trans_count" IS '成交笔数（万笔）';
COMMENT ON COLUMN "tushare_norm_daily_info"."pe" IS '平均市盈率';
COMMENT ON COLUMN "tushare_norm_daily_info"."tr" IS '换手率（％），注：深交所暂无此列';
COMMENT ON COLUMN "tushare_norm_daily_info"."exchange" IS '交易所（SH上交所 SZ深交所）';

CREATE TABLE IF NOT EXISTS "tushare_norm_eco_cal" (
    _record_hash CHAR(64) PRIMARY KEY,
    _request_hash CHAR(64) NOT NULL,
    _source_doc_id INTEGER,
    _source_collected_at TIMESTAMPTZ NOT NULL,
    _first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _schema_version INTEGER NOT NULL DEFAULT 1,
    _extra_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    "date" DATE,
    "time" TIME WITHOUT TIME ZONE,
    "currency" TEXT,
    "country" TEXT,
    "event" TEXT,
    "value" TEXT,
    "pre_value" TEXT,
    "fore_value" TEXT
);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_eco_cal_source" ON "tushare_norm_eco_cal" (_source_collected_at DESC);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_eco_cal_date" ON "tushare_norm_eco_cal" ("date" DESC);
COMMENT ON TABLE "tushare_norm_eco_cal" IS '财经日历；契约驱动标准化表' ;
COMMENT ON COLUMN "tushare_norm_eco_cal"."date" IS '日期';
COMMENT ON COLUMN "tushare_norm_eco_cal"."time" IS '时间';
COMMENT ON COLUMN "tushare_norm_eco_cal"."currency" IS '货币代码';
COMMENT ON COLUMN "tushare_norm_eco_cal"."country" IS '国家';
COMMENT ON COLUMN "tushare_norm_eco_cal"."event" IS '经济事件';
COMMENT ON COLUMN "tushare_norm_eco_cal"."value" IS '今值';
COMMENT ON COLUMN "tushare_norm_eco_cal"."pre_value" IS '前值';
COMMENT ON COLUMN "tushare_norm_eco_cal"."fore_value" IS '预测值';

CREATE TABLE IF NOT EXISTS "tushare_norm_etf_basic" (
    _record_hash CHAR(64) PRIMARY KEY,
    _request_hash CHAR(64) NOT NULL,
    _source_doc_id INTEGER,
    _source_collected_at TIMESTAMPTZ NOT NULL,
    _first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _schema_version INTEGER NOT NULL DEFAULT 1,
    _extra_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    "ts_code" TEXT,
    "csname" TEXT,
    "extname" TEXT,
    "cname" TEXT,
    "index_code" TEXT,
    "index_name" TEXT,
    "setup_date" DATE,
    "list_date" DATE,
    "list_status" TEXT,
    "exchange" TEXT,
    "mgr_name" TEXT,
    "custod_name" TEXT,
    "mgt_fee" NUMERIC,
    "etf_type" TEXT
);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_etf_basic_source" ON "tushare_norm_etf_basic" (_source_collected_at DESC);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_etf_basic_date" ON "tushare_norm_etf_basic" ("list_date" DESC);
COMMENT ON TABLE "tushare_norm_etf_basic" IS 'ETF基础信息；契约驱动标准化表' ;
COMMENT ON COLUMN "tushare_norm_etf_basic"."ts_code" IS '基金交易代码';
COMMENT ON COLUMN "tushare_norm_etf_basic"."csname" IS 'ETF中文简称';
COMMENT ON COLUMN "tushare_norm_etf_basic"."extname" IS 'ETF扩位简称(对应交易所简称)';
COMMENT ON COLUMN "tushare_norm_etf_basic"."cname" IS '基金中文全称';
COMMENT ON COLUMN "tushare_norm_etf_basic"."index_code" IS 'ETF基准指数代码';
COMMENT ON COLUMN "tushare_norm_etf_basic"."index_name" IS 'ETF基准指数中文全称';
COMMENT ON COLUMN "tushare_norm_etf_basic"."setup_date" IS '设立日期（格式：YYYYMMDD）';
COMMENT ON COLUMN "tushare_norm_etf_basic"."list_date" IS '上市日期（格式：YYYYMMDD）';
COMMENT ON COLUMN "tushare_norm_etf_basic"."list_status" IS '存续状态（L上市 D退市 P待上市）';
COMMENT ON COLUMN "tushare_norm_etf_basic"."exchange" IS '交易所（上交所SH 深交所SZ）';
COMMENT ON COLUMN "tushare_norm_etf_basic"."mgr_name" IS '基金管理人简称';
COMMENT ON COLUMN "tushare_norm_etf_basic"."custod_name" IS '基金托管人名称';
COMMENT ON COLUMN "tushare_norm_etf_basic"."mgt_fee" IS '基金管理人收取的费用';
COMMENT ON COLUMN "tushare_norm_etf_basic"."etf_type" IS '基金投资通道类型（境内、QDII）';

CREATE TABLE IF NOT EXISTS "tushare_norm_etf_index" (
    _record_hash CHAR(64) PRIMARY KEY,
    _request_hash CHAR(64) NOT NULL,
    _source_doc_id INTEGER,
    _source_collected_at TIMESTAMPTZ NOT NULL,
    _first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _schema_version INTEGER NOT NULL DEFAULT 1,
    _extra_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    "ts_code" TEXT,
    "indx_name" TEXT,
    "indx_csname" TEXT,
    "pub_party_name" TEXT,
    "pub_date" DATE,
    "base_date" DATE,
    "bp" NUMERIC,
    "adj_circle" TEXT
);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_etf_index_source" ON "tushare_norm_etf_index" (_source_collected_at DESC);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_etf_index_date" ON "tushare_norm_etf_index" ("base_date" DESC);
COMMENT ON TABLE "tushare_norm_etf_index" IS 'ETF基准指数列表；契约驱动标准化表' ;
COMMENT ON COLUMN "tushare_norm_etf_index"."ts_code" IS '指数代码';
COMMENT ON COLUMN "tushare_norm_etf_index"."indx_name" IS '指数全称';
COMMENT ON COLUMN "tushare_norm_etf_index"."indx_csname" IS '指数简称';
COMMENT ON COLUMN "tushare_norm_etf_index"."pub_party_name" IS '指数发布机构';
COMMENT ON COLUMN "tushare_norm_etf_index"."pub_date" IS '指数发布日期';
COMMENT ON COLUMN "tushare_norm_etf_index"."base_date" IS '指数基日';
COMMENT ON COLUMN "tushare_norm_etf_index"."bp" IS '指数基点(点)';
COMMENT ON COLUMN "tushare_norm_etf_index"."adj_circle" IS '指数成份证券调整周期';

CREATE TABLE IF NOT EXISTS "tushare_norm_etf_sh_cons" (
    _record_hash CHAR(64) PRIMARY KEY,
    _request_hash CHAR(64) NOT NULL,
    _source_doc_id INTEGER,
    _source_collected_at TIMESTAMPTZ NOT NULL,
    _first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _schema_version INTEGER NOT NULL DEFAULT 1,
    _extra_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    "trade_date" DATE,
    "ts_code" TEXT,
    "con_code" TEXT,
    "con_name" TEXT,
    "qty" BIGINT,
    "sub_flag" TEXT,
    "cpr" NUMERIC,
    "rdr" NUMERIC,
    "sca" NUMERIC,
    "exchange" TEXT
);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_etf_sh_cons_source" ON "tushare_norm_etf_sh_cons" (_source_collected_at DESC);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_etf_sh_cons_date" ON "tushare_norm_etf_sh_cons" ("trade_date" DESC);
COMMENT ON TABLE "tushare_norm_etf_sh_cons" IS 'ETF每日持仓组合(沪市）；契约驱动标准化表' ;
COMMENT ON COLUMN "tushare_norm_etf_sh_cons"."trade_date" IS '交易日期';
COMMENT ON COLUMN "tushare_norm_etf_sh_cons"."ts_code" IS 'ETF代码';
COMMENT ON COLUMN "tushare_norm_etf_sh_cons"."con_code" IS '成分代码';
COMMENT ON COLUMN "tushare_norm_etf_sh_cons"."con_name" IS '成分名称';
COMMENT ON COLUMN "tushare_norm_etf_sh_cons"."qty" IS '股票数量(股)';
COMMENT ON COLUMN "tushare_norm_etf_sh_cons"."sub_flag" IS '现金替代标志：允许/必须';
COMMENT ON COLUMN "tushare_norm_etf_sh_cons"."cpr" IS '申购现金替代溢价比率（%）';
COMMENT ON COLUMN "tushare_norm_etf_sh_cons"."rdr" IS '赎回现金替代折价比率（%）';
COMMENT ON COLUMN "tushare_norm_etf_sh_cons"."sca" IS '替代金额(单位：人民币元)';
COMMENT ON COLUMN "tushare_norm_etf_sh_cons"."exchange" IS '交易所代码HK港交所 SH上交所 SZ深交所 OTH其他';

CREATE TABLE IF NOT EXISTS "tushare_norm_etf_share_size" (
    _record_hash CHAR(64) PRIMARY KEY,
    _request_hash CHAR(64) NOT NULL,
    _source_doc_id INTEGER,
    _source_collected_at TIMESTAMPTZ NOT NULL,
    _first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _schema_version INTEGER NOT NULL DEFAULT 1,
    _extra_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    "trade_date" DATE,
    "ts_code" TEXT,
    "etf_name" TEXT,
    "total_share" NUMERIC,
    "total_size" NUMERIC,
    "nav" NUMERIC,
    "close" NUMERIC,
    "exchange" TEXT
);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_etf_share_size_source" ON "tushare_norm_etf_share_size" (_source_collected_at DESC);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_etf_share_size_date" ON "tushare_norm_etf_share_size" ("trade_date" DESC);
COMMENT ON TABLE "tushare_norm_etf_share_size" IS 'ETF份额规模；契约驱动标准化表' ;
COMMENT ON COLUMN "tushare_norm_etf_share_size"."trade_date" IS '交易日期';
COMMENT ON COLUMN "tushare_norm_etf_share_size"."ts_code" IS 'ETF代码';
COMMENT ON COLUMN "tushare_norm_etf_share_size"."etf_name" IS '基金名称';
COMMENT ON COLUMN "tushare_norm_etf_share_size"."total_share" IS '总份额（万份）';
COMMENT ON COLUMN "tushare_norm_etf_share_size"."total_size" IS '总规模（万元）';
COMMENT ON COLUMN "tushare_norm_etf_share_size"."nav" IS '基金份额净值(元)';
COMMENT ON COLUMN "tushare_norm_etf_share_size"."close" IS '收盘价（元）';
COMMENT ON COLUMN "tushare_norm_etf_share_size"."exchange" IS '交易所（SSE上交所 SZSE深交所 BSE北交所）';

CREATE TABLE IF NOT EXISTS "tushare_norm_etf_sz_cons" (
    _record_hash CHAR(64) PRIMARY KEY,
    _request_hash CHAR(64) NOT NULL,
    _source_doc_id INTEGER,
    _source_collected_at TIMESTAMPTZ NOT NULL,
    _first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _schema_version INTEGER NOT NULL DEFAULT 1,
    _extra_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    "trade_date" DATE,
    "ts_code" TEXT,
    "con_code" TEXT,
    "con_name" TEXT,
    "qty" BIGINT,
    "sub_flag" TEXT,
    "cpr" NUMERIC,
    "rdr" NUMERIC,
    "sub_cc" NUMERIC,
    "red_cc" NUMERIC,
    "exchange" TEXT
);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_etf_sz_cons_source" ON "tushare_norm_etf_sz_cons" (_source_collected_at DESC);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_etf_sz_cons_date" ON "tushare_norm_etf_sz_cons" ("trade_date" DESC);
COMMENT ON TABLE "tushare_norm_etf_sz_cons" IS 'ETF每日持仓组合(深市）；契约驱动标准化表' ;
COMMENT ON COLUMN "tushare_norm_etf_sz_cons"."trade_date" IS '交易日期';
COMMENT ON COLUMN "tushare_norm_etf_sz_cons"."ts_code" IS 'ETF代码';
COMMENT ON COLUMN "tushare_norm_etf_sz_cons"."con_code" IS '成分代码';
COMMENT ON COLUMN "tushare_norm_etf_sz_cons"."con_name" IS '成分名称';
COMMENT ON COLUMN "tushare_norm_etf_sz_cons"."qty" IS '股票数量(股)';
COMMENT ON COLUMN "tushare_norm_etf_sz_cons"."sub_flag" IS '现金替代标志';
COMMENT ON COLUMN "tushare_norm_etf_sz_cons"."cpr" IS '申购现金替代保证金率（%）';
COMMENT ON COLUMN "tushare_norm_etf_sz_cons"."rdr" IS '赎回现金替代保证金率（%）';
COMMENT ON COLUMN "tushare_norm_etf_sz_cons"."sub_cc" IS '申购替代金额(单位：人民币元)';
COMMENT ON COLUMN "tushare_norm_etf_sz_cons"."red_cc" IS '赎回替代金额(单位：人民币元)';
COMMENT ON COLUMN "tushare_norm_etf_sz_cons"."exchange" IS '交易所代码HK港交所 SH上交所 SZ深交所 OTH其他';

CREATE TABLE IF NOT EXISTS "tushare_norm_factor_value" (
    _record_hash CHAR(64) PRIMARY KEY,
    _request_hash CHAR(64) NOT NULL,
    _source_doc_id INTEGER,
    _source_collected_at TIMESTAMPTZ NOT NULL,
    _first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _schema_version INTEGER NOT NULL DEFAULT 1,
    _extra_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    "factor_name" TEXT,
    "ts_code" TEXT,
    "trade_date" DATE,
    "factor_value" NUMERIC
);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_factor_value_source" ON "tushare_norm_factor_value" (_source_collected_at DESC);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_factor_value_date" ON "tushare_norm_factor_value" ("trade_date" DESC);
COMMENT ON TABLE "tushare_norm_factor_value" IS '因子值；契约驱动标准化表' ;
COMMENT ON COLUMN "tushare_norm_factor_value"."factor_name" IS '因子名称';
COMMENT ON COLUMN "tushare_norm_factor_value"."ts_code" IS '证券代码';
COMMENT ON COLUMN "tushare_norm_factor_value"."trade_date" IS '交易日期，格式YYYYMMDD';
COMMENT ON COLUMN "tushare_norm_factor_value"."factor_value" IS '因子值';

CREATE TABLE IF NOT EXISTS "tushare_norm_fina_audit" (
    _record_hash CHAR(64) PRIMARY KEY,
    _request_hash CHAR(64) NOT NULL,
    _source_doc_id INTEGER,
    _source_collected_at TIMESTAMPTZ NOT NULL,
    _first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _schema_version INTEGER NOT NULL DEFAULT 1,
    _extra_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    "ts_code" TEXT,
    "ann_date" DATE,
    "end_date" DATE,
    "audit_result" TEXT,
    "audit_fees" NUMERIC,
    "audit_agency" TEXT,
    "audit_sign" TEXT
);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_fina_audit_source" ON "tushare_norm_fina_audit" (_source_collected_at DESC);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_fina_audit_date" ON "tushare_norm_fina_audit" ("ann_date" DESC);
COMMENT ON TABLE "tushare_norm_fina_audit" IS '财务审计意见；契约驱动标准化表' ;

CREATE TABLE IF NOT EXISTS "tushare_norm_ft_limit" (
    _record_hash CHAR(64) PRIMARY KEY,
    _request_hash CHAR(64) NOT NULL,
    _source_doc_id INTEGER,
    _source_collected_at TIMESTAMPTZ NOT NULL,
    _first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _schema_version INTEGER NOT NULL DEFAULT 1,
    _extra_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    "trade_date" DATE,
    "ts_code" TEXT,
    "name" TEXT,
    "up_limit" NUMERIC,
    "down_limit" NUMERIC,
    "m_ratio" NUMERIC,
    "cont" TEXT,
    "exchange" TEXT
);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_ft_limit_source" ON "tushare_norm_ft_limit" (_source_collected_at DESC);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_ft_limit_date" ON "tushare_norm_ft_limit" ("trade_date" DESC);
COMMENT ON TABLE "tushare_norm_ft_limit" IS '期货合约涨跌停价格（盘前）；契约驱动标准化表' ;
COMMENT ON COLUMN "tushare_norm_ft_limit"."trade_date" IS '交易日期';
COMMENT ON COLUMN "tushare_norm_ft_limit"."ts_code" IS 'TS股票代码';
COMMENT ON COLUMN "tushare_norm_ft_limit"."name" IS '合约名称';
COMMENT ON COLUMN "tushare_norm_ft_limit"."up_limit" IS '涨停价';
COMMENT ON COLUMN "tushare_norm_ft_limit"."down_limit" IS '跌停价';
COMMENT ON COLUMN "tushare_norm_ft_limit"."m_ratio" IS '最低交易保证金率（%）';
COMMENT ON COLUMN "tushare_norm_ft_limit"."cont" IS '合约代码';
COMMENT ON COLUMN "tushare_norm_ft_limit"."exchange" IS '交易所代码';

CREATE TABLE IF NOT EXISTS "tushare_norm_fund_adj" (
    _record_hash CHAR(64) PRIMARY KEY,
    _request_hash CHAR(64) NOT NULL,
    _source_doc_id INTEGER,
    _source_collected_at TIMESTAMPTZ NOT NULL,
    _first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _schema_version INTEGER NOT NULL DEFAULT 1,
    _extra_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    "ts_code" TEXT,
    "trade_date" DATE,
    "adj_factor" NUMERIC
);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_fund_adj_source" ON "tushare_norm_fund_adj" (_source_collected_at DESC);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_fund_adj_date" ON "tushare_norm_fund_adj" ("trade_date" DESC);
COMMENT ON TABLE "tushare_norm_fund_adj" IS '基金复权因子；契约驱动标准化表' ;
COMMENT ON COLUMN "tushare_norm_fund_adj"."ts_code" IS 'ts基金代码';
COMMENT ON COLUMN "tushare_norm_fund_adj"."trade_date" IS '交易日期';
COMMENT ON COLUMN "tushare_norm_fund_adj"."adj_factor" IS '复权因子';

CREATE TABLE IF NOT EXISTS "tushare_norm_fund_basic" (
    _record_hash CHAR(64) PRIMARY KEY,
    _request_hash CHAR(64) NOT NULL,
    _source_doc_id INTEGER,
    _source_collected_at TIMESTAMPTZ NOT NULL,
    _first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _schema_version INTEGER NOT NULL DEFAULT 1,
    _extra_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    "ts_code" TEXT,
    "name" TEXT,
    "management" TEXT,
    "custodian" TEXT,
    "fund_type" TEXT,
    "found_date" DATE,
    "due_date" DATE,
    "list_date" DATE,
    "issue_date" DATE,
    "delist_date" DATE,
    "issue_amount" NUMERIC,
    "m_fee" NUMERIC,
    "c_fee" NUMERIC,
    "duration_year" NUMERIC,
    "p_value" NUMERIC,
    "min_amount" NUMERIC,
    "exp_return" NUMERIC,
    "benchmark" TEXT,
    "status" TEXT,
    "invest_type" TEXT,
    "type" TEXT,
    "trustee" TEXT,
    "purc_startdate" TEXT,
    "redm_startdate" TEXT,
    "market" TEXT
);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_fund_basic_source" ON "tushare_norm_fund_basic" (_source_collected_at DESC);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_fund_basic_date" ON "tushare_norm_fund_basic" ("delist_date" DESC);
COMMENT ON TABLE "tushare_norm_fund_basic" IS '公募基金列表；契约驱动标准化表' ;
COMMENT ON COLUMN "tushare_norm_fund_basic"."ts_code" IS '基金代码';
COMMENT ON COLUMN "tushare_norm_fund_basic"."name" IS '简称';
COMMENT ON COLUMN "tushare_norm_fund_basic"."management" IS '管理人';
COMMENT ON COLUMN "tushare_norm_fund_basic"."custodian" IS '托管人';
COMMENT ON COLUMN "tushare_norm_fund_basic"."fund_type" IS '投资类型';
COMMENT ON COLUMN "tushare_norm_fund_basic"."found_date" IS '成立日期';
COMMENT ON COLUMN "tushare_norm_fund_basic"."due_date" IS '到期日期';
COMMENT ON COLUMN "tushare_norm_fund_basic"."list_date" IS '上市时间';
COMMENT ON COLUMN "tushare_norm_fund_basic"."issue_date" IS '发行日期';
COMMENT ON COLUMN "tushare_norm_fund_basic"."delist_date" IS '退市日期';
COMMENT ON COLUMN "tushare_norm_fund_basic"."issue_amount" IS '发行份额(亿)';
COMMENT ON COLUMN "tushare_norm_fund_basic"."m_fee" IS '管理费';
COMMENT ON COLUMN "tushare_norm_fund_basic"."c_fee" IS '托管费';
COMMENT ON COLUMN "tushare_norm_fund_basic"."duration_year" IS '存续期';
COMMENT ON COLUMN "tushare_norm_fund_basic"."p_value" IS '面值';
COMMENT ON COLUMN "tushare_norm_fund_basic"."min_amount" IS '起点金额(万元)';
COMMENT ON COLUMN "tushare_norm_fund_basic"."exp_return" IS '预期收益率';
COMMENT ON COLUMN "tushare_norm_fund_basic"."benchmark" IS '业绩比较基准';
COMMENT ON COLUMN "tushare_norm_fund_basic"."status" IS '存续状态D摘牌/已到期 I发行 L已上市/存续中';
COMMENT ON COLUMN "tushare_norm_fund_basic"."invest_type" IS '投资风格';
COMMENT ON COLUMN "tushare_norm_fund_basic"."type" IS '基金类型';
COMMENT ON COLUMN "tushare_norm_fund_basic"."trustee" IS '受托人';
COMMENT ON COLUMN "tushare_norm_fund_basic"."purc_startdate" IS '日常申购起始日';
COMMENT ON COLUMN "tushare_norm_fund_basic"."redm_startdate" IS '日常赎回起始日';
COMMENT ON COLUMN "tushare_norm_fund_basic"."market" IS 'E场内O场外';

CREATE TABLE IF NOT EXISTS "tushare_norm_fund_company" (
    _record_hash CHAR(64) PRIMARY KEY,
    _request_hash CHAR(64) NOT NULL,
    _source_doc_id INTEGER,
    _source_collected_at TIMESTAMPTZ NOT NULL,
    _first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _schema_version INTEGER NOT NULL DEFAULT 1,
    _extra_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    "name" TEXT,
    "shortname" TEXT,
    "short_enname" TEXT,
    "province" TEXT,
    "city" TEXT,
    "address" TEXT,
    "phone" TEXT,
    "office" TEXT,
    "website" TEXT,
    "chairman" TEXT,
    "manager" TEXT,
    "reg_capital" NUMERIC,
    "setup_date" DATE,
    "end_date" DATE,
    "employees" NUMERIC,
    "main_business" TEXT,
    "org_code" TEXT,
    "credit_code" TEXT
);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_fund_company_source" ON "tushare_norm_fund_company" (_source_collected_at DESC);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_fund_company_date" ON "tushare_norm_fund_company" ("end_date" DESC);
COMMENT ON TABLE "tushare_norm_fund_company" IS '公募基金公司；契约驱动标准化表' ;
COMMENT ON COLUMN "tushare_norm_fund_company"."name" IS '基金公司名称';
COMMENT ON COLUMN "tushare_norm_fund_company"."shortname" IS '简称';
COMMENT ON COLUMN "tushare_norm_fund_company"."short_enname" IS '英文缩写';
COMMENT ON COLUMN "tushare_norm_fund_company"."province" IS '省份';
COMMENT ON COLUMN "tushare_norm_fund_company"."city" IS '城市';
COMMENT ON COLUMN "tushare_norm_fund_company"."address" IS '注册地址';
COMMENT ON COLUMN "tushare_norm_fund_company"."phone" IS '电话';
COMMENT ON COLUMN "tushare_norm_fund_company"."office" IS '办公地址';
COMMENT ON COLUMN "tushare_norm_fund_company"."website" IS '公司网址';
COMMENT ON COLUMN "tushare_norm_fund_company"."chairman" IS '法人代表';
COMMENT ON COLUMN "tushare_norm_fund_company"."manager" IS '总经理';
COMMENT ON COLUMN "tushare_norm_fund_company"."reg_capital" IS '注册资本';
COMMENT ON COLUMN "tushare_norm_fund_company"."setup_date" IS '成立日期';
COMMENT ON COLUMN "tushare_norm_fund_company"."end_date" IS '公司终止日期';
COMMENT ON COLUMN "tushare_norm_fund_company"."employees" IS '员工总数';
COMMENT ON COLUMN "tushare_norm_fund_company"."main_business" IS '主要产品及业务';
COMMENT ON COLUMN "tushare_norm_fund_company"."org_code" IS '组织机构代码';
COMMENT ON COLUMN "tushare_norm_fund_company"."credit_code" IS '统一社会信用代码';

CREATE TABLE IF NOT EXISTS "tushare_norm_fund_daily" (
    _record_hash CHAR(64) PRIMARY KEY,
    _request_hash CHAR(64) NOT NULL,
    _source_doc_id INTEGER,
    _source_collected_at TIMESTAMPTZ NOT NULL,
    _first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _schema_version INTEGER NOT NULL DEFAULT 1,
    _extra_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    "ts_code" TEXT,
    "trade_date" DATE,
    "open" NUMERIC,
    "high" NUMERIC,
    "low" NUMERIC,
    "close" NUMERIC,
    "pre_close" NUMERIC,
    "change" NUMERIC,
    "pct_chg" NUMERIC,
    "vol" NUMERIC,
    "amount" NUMERIC
);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_fund_daily_source" ON "tushare_norm_fund_daily" (_source_collected_at DESC);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_fund_daily_date" ON "tushare_norm_fund_daily" ("trade_date" DESC);
COMMENT ON TABLE "tushare_norm_fund_daily" IS 'ETF日线行情；契约驱动标准化表' ;
COMMENT ON COLUMN "tushare_norm_fund_daily"."ts_code" IS 'TS代码';
COMMENT ON COLUMN "tushare_norm_fund_daily"."trade_date" IS '交易日期';
COMMENT ON COLUMN "tushare_norm_fund_daily"."open" IS '开盘价(元)';
COMMENT ON COLUMN "tushare_norm_fund_daily"."high" IS '最高价(元)';
COMMENT ON COLUMN "tushare_norm_fund_daily"."low" IS '最低价(元)';
COMMENT ON COLUMN "tushare_norm_fund_daily"."close" IS '收盘价(元)';
COMMENT ON COLUMN "tushare_norm_fund_daily"."pre_close" IS '昨收盘价(元)';
COMMENT ON COLUMN "tushare_norm_fund_daily"."change" IS '涨跌额(元)';
COMMENT ON COLUMN "tushare_norm_fund_daily"."pct_chg" IS '涨跌幅(%)';
COMMENT ON COLUMN "tushare_norm_fund_daily"."vol" IS '成交量(手)';
COMMENT ON COLUMN "tushare_norm_fund_daily"."amount" IS '成交额(千元)';

CREATE TABLE IF NOT EXISTS "tushare_norm_fund_div" (
    _record_hash CHAR(64) PRIMARY KEY,
    _request_hash CHAR(64) NOT NULL,
    _source_doc_id INTEGER,
    _source_collected_at TIMESTAMPTZ NOT NULL,
    _first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _schema_version INTEGER NOT NULL DEFAULT 1,
    _extra_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    "ts_code" TEXT,
    "ann_date" DATE,
    "imp_anndate" DATE,
    "base_date" DATE,
    "div_proc" TEXT,
    "record_date" DATE,
    "ex_date" DATE,
    "pay_date" DATE,
    "earpay_date" DATE,
    "net_ex_date" DATE,
    "div_cash" NUMERIC,
    "base_unit" NUMERIC,
    "ear_distr" NUMERIC,
    "ear_amount" NUMERIC,
    "account_date" DATE,
    "base_year" TEXT
);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_fund_div_source" ON "tushare_norm_fund_div" (_source_collected_at DESC);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_fund_div_date" ON "tushare_norm_fund_div" ("ann_date" DESC);
COMMENT ON TABLE "tushare_norm_fund_div" IS '公募基金分红；契约驱动标准化表' ;
COMMENT ON COLUMN "tushare_norm_fund_div"."ts_code" IS 'TS代码';
COMMENT ON COLUMN "tushare_norm_fund_div"."ann_date" IS '公告日期';
COMMENT ON COLUMN "tushare_norm_fund_div"."imp_anndate" IS '分红实施公告日';
COMMENT ON COLUMN "tushare_norm_fund_div"."base_date" IS '分配收益基准日';
COMMENT ON COLUMN "tushare_norm_fund_div"."div_proc" IS '方案进度';
COMMENT ON COLUMN "tushare_norm_fund_div"."record_date" IS '权益登记日';
COMMENT ON COLUMN "tushare_norm_fund_div"."ex_date" IS '除息日';
COMMENT ON COLUMN "tushare_norm_fund_div"."pay_date" IS '派息日';
COMMENT ON COLUMN "tushare_norm_fund_div"."earpay_date" IS '收益支付日';
COMMENT ON COLUMN "tushare_norm_fund_div"."net_ex_date" IS '净值除权日';
COMMENT ON COLUMN "tushare_norm_fund_div"."div_cash" IS '每股派息(元)';
COMMENT ON COLUMN "tushare_norm_fund_div"."base_unit" IS '基准基金份额(万份)';
COMMENT ON COLUMN "tushare_norm_fund_div"."ear_distr" IS '可分配收益(元)';
COMMENT ON COLUMN "tushare_norm_fund_div"."ear_amount" IS '收益分配金额(元)';
COMMENT ON COLUMN "tushare_norm_fund_div"."account_date" IS '红利再投资到账日';
COMMENT ON COLUMN "tushare_norm_fund_div"."base_year" IS '份额基准年度';

CREATE TABLE IF NOT EXISTS "tushare_norm_fund_factor_pro" (
    _record_hash CHAR(64) PRIMARY KEY,
    _request_hash CHAR(64) NOT NULL,
    _source_doc_id INTEGER,
    _source_collected_at TIMESTAMPTZ NOT NULL,
    _first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _schema_version INTEGER NOT NULL DEFAULT 1,
    _extra_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    "ts_code" TEXT,
    "trade_date" DATE,
    "trade_date_doris" TEXT,
    "open" NUMERIC,
    "high" NUMERIC,
    "low" NUMERIC,
    "close" NUMERIC,
    "pre_close" NUMERIC,
    "change" NUMERIC,
    "pct_change" NUMERIC,
    "vol" NUMERIC,
    "amount" NUMERIC,
    "asi_bfq" NUMERIC,
    "asit_bfq" NUMERIC,
    "atr_bfq" NUMERIC,
    "bbi_bfq" NUMERIC,
    "bias1_bfq" NUMERIC,
    "bias2_bfq" NUMERIC,
    "bias3_bfq" NUMERIC,
    "boll_lower_bfq" NUMERIC,
    "boll_mid_bfq" NUMERIC,
    "boll_upper_bfq" NUMERIC,
    "brar_ar_bfq" NUMERIC,
    "brar_br_bfq" NUMERIC,
    "cci_bfq" NUMERIC,
    "cr_bfq" NUMERIC,
    "dfma_dif_bfq" NUMERIC,
    "dfma_difma_bfq" NUMERIC,
    "dmi_adx_bfq" NUMERIC,
    "dmi_adxr_bfq" NUMERIC,
    "dmi_mdi_bfq" NUMERIC,
    "dmi_pdi_bfq" NUMERIC,
    "downdays" NUMERIC,
    "updays" NUMERIC,
    "dpo_bfq" NUMERIC,
    "madpo_bfq" NUMERIC,
    "ema_bfq_10" NUMERIC,
    "ema_bfq_20" NUMERIC,
    "ema_bfq_250" NUMERIC,
    "ema_bfq_30" NUMERIC,
    "ema_bfq_5" NUMERIC,
    "ema_bfq_60" NUMERIC,
    "ema_bfq_90" NUMERIC,
    "emv_bfq" NUMERIC,
    "maemv_bfq" NUMERIC,
    "expma_12_bfq" NUMERIC,
    "expma_50_bfq" NUMERIC,
    "kdj_bfq" NUMERIC,
    "kdj_d_bfq" NUMERIC,
    "kdj_k_bfq" NUMERIC,
    "ktn_down_bfq" NUMERIC,
    "ktn_mid_bfq" NUMERIC,
    "ktn_upper_bfq" NUMERIC,
    "lowdays" NUMERIC,
    "topdays" NUMERIC,
    "ma_bfq_10" NUMERIC,
    "ma_bfq_20" NUMERIC,
    "ma_bfq_250" NUMERIC,
    "ma_bfq_30" NUMERIC,
    "ma_bfq_5" NUMERIC,
    "ma_bfq_60" NUMERIC,
    "ma_bfq_90" NUMERIC,
    "macd_bfq" NUMERIC,
    "macd_dea_bfq" NUMERIC,
    "macd_dif_bfq" NUMERIC,
    "mass_bfq" NUMERIC,
    "ma_mass_bfq" NUMERIC,
    "mfi_bfq" NUMERIC,
    "mtm_bfq" NUMERIC,
    "mtmma_bfq" NUMERIC,
    "obv_bfq" NUMERIC,
    "psy_bfq" NUMERIC,
    "psyma_bfq" NUMERIC,
    "roc_bfq" NUMERIC,
    "maroc_bfq" NUMERIC,
    "rsi_bfq_12" NUMERIC,
    "rsi_bfq_24" NUMERIC,
    "rsi_bfq_6" NUMERIC,
    "taq_down_bfq" NUMERIC,
    "taq_mid_bfq" NUMERIC,
    "taq_up_bfq" NUMERIC,
    "trix_bfq" NUMERIC,
    "trma_bfq" NUMERIC,
    "vr_bfq" NUMERIC,
    "wr_bfq" NUMERIC,
    "wr1_bfq" NUMERIC,
    "xsii_td1_bfq" NUMERIC,
    "xsii_td2_bfq" NUMERIC,
    "xsii_td3_bfq" NUMERIC,
    "xsii_td4_bfq" NUMERIC
);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_fund_factor_pro_source" ON "tushare_norm_fund_factor_pro" (_source_collected_at DESC);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_fund_factor_pro_date" ON "tushare_norm_fund_factor_pro" ("trade_date" DESC);
COMMENT ON TABLE "tushare_norm_fund_factor_pro" IS '场内基金技术因子(专业版)；契约驱动标准化表' ;
COMMENT ON COLUMN "tushare_norm_fund_factor_pro"."ts_code" IS '基金代码';
COMMENT ON COLUMN "tushare_norm_fund_factor_pro"."trade_date" IS '交易日期';
COMMENT ON COLUMN "tushare_norm_fund_factor_pro"."trade_date_doris" IS '日期';
COMMENT ON COLUMN "tushare_norm_fund_factor_pro"."open" IS '开盘价';
COMMENT ON COLUMN "tushare_norm_fund_factor_pro"."high" IS '最高价';
COMMENT ON COLUMN "tushare_norm_fund_factor_pro"."low" IS '最低价';
COMMENT ON COLUMN "tushare_norm_fund_factor_pro"."close" IS '收盘价';
COMMENT ON COLUMN "tushare_norm_fund_factor_pro"."pre_close" IS '昨收价';
COMMENT ON COLUMN "tushare_norm_fund_factor_pro"."change" IS '涨跌额';
COMMENT ON COLUMN "tushare_norm_fund_factor_pro"."pct_change" IS '涨跌幅 （未复权，如果是复权请用 通用行情接口 ）';
COMMENT ON COLUMN "tushare_norm_fund_factor_pro"."vol" IS '成交量 （手）';
COMMENT ON COLUMN "tushare_norm_fund_factor_pro"."amount" IS '成交额 （千元）';
COMMENT ON COLUMN "tushare_norm_fund_factor_pro"."asi_bfq" IS '振动升降指标-OPEN, CLOSE, HIGH, LOW, M1=26, M2=10';
COMMENT ON COLUMN "tushare_norm_fund_factor_pro"."asit_bfq" IS '振动升降指标-OPEN, CLOSE, HIGH, LOW, M1=26, M2=10';
COMMENT ON COLUMN "tushare_norm_fund_factor_pro"."atr_bfq" IS '真实波动N日平均值-CLOSE, HIGH, LOW, N=20';
COMMENT ON COLUMN "tushare_norm_fund_factor_pro"."bbi_bfq" IS 'BBI多空指标-CLOSE, M1=3, M2=6, M3=12, M4=20';
COMMENT ON COLUMN "tushare_norm_fund_factor_pro"."bias1_bfq" IS 'BIAS乖离率-CLOSE, L1=6, L2=12, L3=24';
COMMENT ON COLUMN "tushare_norm_fund_factor_pro"."bias2_bfq" IS 'BIAS乖离率-CLOSE, L1=6, L2=12, L3=24';
COMMENT ON COLUMN "tushare_norm_fund_factor_pro"."bias3_bfq" IS 'BIAS乖离率-CLOSE, L1=6, L2=12, L3=24';
COMMENT ON COLUMN "tushare_norm_fund_factor_pro"."boll_lower_bfq" IS 'BOLL指标，布林带-CLOSE, N=20, P=2';
COMMENT ON COLUMN "tushare_norm_fund_factor_pro"."boll_mid_bfq" IS 'BOLL指标，布林带-CLOSE, N=20, P=2';
COMMENT ON COLUMN "tushare_norm_fund_factor_pro"."boll_upper_bfq" IS 'BOLL指标，布林带-CLOSE, N=20, P=2';
COMMENT ON COLUMN "tushare_norm_fund_factor_pro"."brar_ar_bfq" IS 'BRAR情绪指标-OPEN, CLOSE, HIGH, LOW, M1=26';
COMMENT ON COLUMN "tushare_norm_fund_factor_pro"."brar_br_bfq" IS 'BRAR情绪指标-OPEN, CLOSE, HIGH, LOW, M1=26';
COMMENT ON COLUMN "tushare_norm_fund_factor_pro"."cci_bfq" IS '顺势指标又叫CCI指标-CLOSE, HIGH, LOW, N=14';
COMMENT ON COLUMN "tushare_norm_fund_factor_pro"."cr_bfq" IS 'CR价格动量指标-CLOSE, HIGH, LOW, N=20';
COMMENT ON COLUMN "tushare_norm_fund_factor_pro"."dfma_dif_bfq" IS '平行线差指标-CLOSE, N1=10, N2=50, M=10';
COMMENT ON COLUMN "tushare_norm_fund_factor_pro"."dfma_difma_bfq" IS '平行线差指标-CLOSE, N1=10, N2=50, M=10';
COMMENT ON COLUMN "tushare_norm_fund_factor_pro"."dmi_adx_bfq" IS '动向指标-CLOSE, HIGH, LOW, M1=14, M2=6';
COMMENT ON COLUMN "tushare_norm_fund_factor_pro"."dmi_adxr_bfq" IS '动向指标-CLOSE, HIGH, LOW, M1=14, M2=6';
COMMENT ON COLUMN "tushare_norm_fund_factor_pro"."dmi_mdi_bfq" IS '动向指标-CLOSE, HIGH, LOW, M1=14, M2=6';
COMMENT ON COLUMN "tushare_norm_fund_factor_pro"."dmi_pdi_bfq" IS '动向指标-CLOSE, HIGH, LOW, M1=14, M2=6';
COMMENT ON COLUMN "tushare_norm_fund_factor_pro"."downdays" IS '连跌天数';
COMMENT ON COLUMN "tushare_norm_fund_factor_pro"."updays" IS '连涨天数';
COMMENT ON COLUMN "tushare_norm_fund_factor_pro"."dpo_bfq" IS '区间震荡线-CLOSE, M1=20, M2=10, M3=6';
COMMENT ON COLUMN "tushare_norm_fund_factor_pro"."madpo_bfq" IS '区间震荡线-CLOSE, M1=20, M2=10, M3=6';
COMMENT ON COLUMN "tushare_norm_fund_factor_pro"."ema_bfq_10" IS '指数移动平均-N=10';
COMMENT ON COLUMN "tushare_norm_fund_factor_pro"."ema_bfq_20" IS '指数移动平均-N=20';
COMMENT ON COLUMN "tushare_norm_fund_factor_pro"."ema_bfq_250" IS '指数移动平均-N=250';
COMMENT ON COLUMN "tushare_norm_fund_factor_pro"."ema_bfq_30" IS '指数移动平均-N=30';
COMMENT ON COLUMN "tushare_norm_fund_factor_pro"."ema_bfq_5" IS '指数移动平均-N=5';
COMMENT ON COLUMN "tushare_norm_fund_factor_pro"."ema_bfq_60" IS '指数移动平均-N=60';
COMMENT ON COLUMN "tushare_norm_fund_factor_pro"."ema_bfq_90" IS '指数移动平均-N=90';
COMMENT ON COLUMN "tushare_norm_fund_factor_pro"."emv_bfq" IS '简易波动指标-HIGH, LOW, VOL, N=14, M=9';
COMMENT ON COLUMN "tushare_norm_fund_factor_pro"."maemv_bfq" IS '简易波动指标-HIGH, LOW, VOL, N=14, M=9';
COMMENT ON COLUMN "tushare_norm_fund_factor_pro"."expma_12_bfq" IS 'EMA指数平均数指标-CLOSE, N1=12, N2=50';
COMMENT ON COLUMN "tushare_norm_fund_factor_pro"."expma_50_bfq" IS 'EMA指数平均数指标-CLOSE, N1=12, N2=50';
COMMENT ON COLUMN "tushare_norm_fund_factor_pro"."kdj_bfq" IS 'KDJ指标-CLOSE, HIGH, LOW, N=9, M1=3, M2=3';
COMMENT ON COLUMN "tushare_norm_fund_factor_pro"."kdj_d_bfq" IS 'KDJ指标-CLOSE, HIGH, LOW, N=9, M1=3, M2=3';
COMMENT ON COLUMN "tushare_norm_fund_factor_pro"."kdj_k_bfq" IS 'KDJ指标-CLOSE, HIGH, LOW, N=9, M1=3, M2=3';
COMMENT ON COLUMN "tushare_norm_fund_factor_pro"."ktn_down_bfq" IS '肯特纳交易通道, N选20日，ATR选10日-CLOSE, HIGH, LOW, N=20, M=10';
COMMENT ON COLUMN "tushare_norm_fund_factor_pro"."ktn_mid_bfq" IS '肯特纳交易通道, N选20日，ATR选10日-CLOSE, HIGH, LOW, N=20, M=10';
COMMENT ON COLUMN "tushare_norm_fund_factor_pro"."ktn_upper_bfq" IS '肯特纳交易通道, N选20日，ATR选10日-CLOSE, HIGH, LOW, N=20, M=10';
COMMENT ON COLUMN "tushare_norm_fund_factor_pro"."lowdays" IS 'LOWRANGE(LOW)表示当前最低价是近多少周期内最低价的最小值';
COMMENT ON COLUMN "tushare_norm_fund_factor_pro"."topdays" IS 'TOPRANGE(HIGH)表示当前最高价是近多少周期内最高价的最大值';
COMMENT ON COLUMN "tushare_norm_fund_factor_pro"."ma_bfq_10" IS '简单移动平均-N=10';
COMMENT ON COLUMN "tushare_norm_fund_factor_pro"."ma_bfq_20" IS '简单移动平均-N=20';
COMMENT ON COLUMN "tushare_norm_fund_factor_pro"."ma_bfq_250" IS '简单移动平均-N=250';
COMMENT ON COLUMN "tushare_norm_fund_factor_pro"."ma_bfq_30" IS '简单移动平均-N=30';
COMMENT ON COLUMN "tushare_norm_fund_factor_pro"."ma_bfq_5" IS '简单移动平均-N=5';
COMMENT ON COLUMN "tushare_norm_fund_factor_pro"."ma_bfq_60" IS '简单移动平均-N=60';
COMMENT ON COLUMN "tushare_norm_fund_factor_pro"."ma_bfq_90" IS '简单移动平均-N=90';
COMMENT ON COLUMN "tushare_norm_fund_factor_pro"."macd_bfq" IS 'MACD指标-CLOSE, SHORT=12, LONG=26, M=9';
COMMENT ON COLUMN "tushare_norm_fund_factor_pro"."macd_dea_bfq" IS 'MACD指标-CLOSE, SHORT=12, LONG=26, M=9';
COMMENT ON COLUMN "tushare_norm_fund_factor_pro"."macd_dif_bfq" IS 'MACD指标-CLOSE, SHORT=12, LONG=26, M=9';
COMMENT ON COLUMN "tushare_norm_fund_factor_pro"."mass_bfq" IS '梅斯线-HIGH, LOW, N1=9, N2=25, M=6';
COMMENT ON COLUMN "tushare_norm_fund_factor_pro"."ma_mass_bfq" IS '梅斯线-HIGH, LOW, N1=9, N2=25, M=6';
COMMENT ON COLUMN "tushare_norm_fund_factor_pro"."mfi_bfq" IS 'MFI指标是成交量的RSI指标-CLOSE, HIGH, LOW, VOL, N=14';
COMMENT ON COLUMN "tushare_norm_fund_factor_pro"."mtm_bfq" IS '动量指标-CLOSE, N=12, M=6';
COMMENT ON COLUMN "tushare_norm_fund_factor_pro"."mtmma_bfq" IS '动量指标-CLOSE, N=12, M=6';
COMMENT ON COLUMN "tushare_norm_fund_factor_pro"."obv_bfq" IS '能量潮指标-CLOSE, VOL';
COMMENT ON COLUMN "tushare_norm_fund_factor_pro"."psy_bfq" IS '投资者对股市涨跌产生心理波动的情绪指标-CLOSE, N=12, M=6';
COMMENT ON COLUMN "tushare_norm_fund_factor_pro"."psyma_bfq" IS '投资者对股市涨跌产生心理波动的情绪指标-CLOSE, N=12, M=6';
COMMENT ON COLUMN "tushare_norm_fund_factor_pro"."roc_bfq" IS '变动率指标-CLOSE, N=12, M=6';
COMMENT ON COLUMN "tushare_norm_fund_factor_pro"."maroc_bfq" IS '变动率指标-CLOSE, N=12, M=6';
COMMENT ON COLUMN "tushare_norm_fund_factor_pro"."rsi_bfq_12" IS 'RSI指标-CLOSE, N=12';
COMMENT ON COLUMN "tushare_norm_fund_factor_pro"."rsi_bfq_24" IS 'RSI指标-CLOSE, N=24';
COMMENT ON COLUMN "tushare_norm_fund_factor_pro"."rsi_bfq_6" IS 'RSI指标-CLOSE, N=6';
COMMENT ON COLUMN "tushare_norm_fund_factor_pro"."taq_down_bfq" IS '唐安奇通道(海龟)交易指标-HIGH, LOW, 20';
COMMENT ON COLUMN "tushare_norm_fund_factor_pro"."taq_mid_bfq" IS '唐安奇通道(海龟)交易指标-HIGH, LOW, 20';
COMMENT ON COLUMN "tushare_norm_fund_factor_pro"."taq_up_bfq" IS '唐安奇通道(海龟)交易指标-HIGH, LOW, 20';
COMMENT ON COLUMN "tushare_norm_fund_factor_pro"."trix_bfq" IS '三重指数平滑平均线-CLOSE, M1=12, M2=20';
COMMENT ON COLUMN "tushare_norm_fund_factor_pro"."trma_bfq" IS '三重指数平滑平均线-CLOSE, M1=12, M2=20';
COMMENT ON COLUMN "tushare_norm_fund_factor_pro"."vr_bfq" IS 'VR容量比率-CLOSE, VOL, M1=26';
COMMENT ON COLUMN "tushare_norm_fund_factor_pro"."wr_bfq" IS 'W&R 威廉指标-CLOSE, HIGH, LOW, N=10, N1=6';
COMMENT ON COLUMN "tushare_norm_fund_factor_pro"."wr1_bfq" IS 'W&R 威廉指标-CLOSE, HIGH, LOW, N=10, N1=6';
COMMENT ON COLUMN "tushare_norm_fund_factor_pro"."xsii_td1_bfq" IS '薛斯通道II-CLOSE, HIGH, LOW, N=102, M=7';
COMMENT ON COLUMN "tushare_norm_fund_factor_pro"."xsii_td2_bfq" IS '薛斯通道II-CLOSE, HIGH, LOW, N=102, M=7';
COMMENT ON COLUMN "tushare_norm_fund_factor_pro"."xsii_td3_bfq" IS '薛斯通道II-CLOSE, HIGH, LOW, N=102, M=7';
COMMENT ON COLUMN "tushare_norm_fund_factor_pro"."xsii_td4_bfq" IS '薛斯通道II-CLOSE, HIGH, LOW, N=102, M=7';

CREATE TABLE IF NOT EXISTS "tushare_norm_fund_manager" (
    _record_hash CHAR(64) PRIMARY KEY,
    _request_hash CHAR(64) NOT NULL,
    _source_doc_id INTEGER,
    _source_collected_at TIMESTAMPTZ NOT NULL,
    _first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _schema_version INTEGER NOT NULL DEFAULT 1,
    _extra_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    "ts_code" TEXT,
    "ann_date" DATE,
    "name" TEXT,
    "gender" TEXT,
    "birth_year" TEXT,
    "edu" TEXT,
    "nationality" TEXT,
    "begin_date" DATE,
    "end_date" DATE,
    "resume" TEXT
);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_fund_manager_source" ON "tushare_norm_fund_manager" (_source_collected_at DESC);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_fund_manager_date" ON "tushare_norm_fund_manager" ("ann_date" DESC);
COMMENT ON TABLE "tushare_norm_fund_manager" IS '基金经理；契约驱动标准化表' ;
COMMENT ON COLUMN "tushare_norm_fund_manager"."ts_code" IS '基金代码';
COMMENT ON COLUMN "tushare_norm_fund_manager"."ann_date" IS '公告日期';
COMMENT ON COLUMN "tushare_norm_fund_manager"."name" IS '基金经理姓名';
COMMENT ON COLUMN "tushare_norm_fund_manager"."gender" IS '性别 F:女 M:男';
COMMENT ON COLUMN "tushare_norm_fund_manager"."birth_year" IS '出生年份';
COMMENT ON COLUMN "tushare_norm_fund_manager"."edu" IS '学历';
COMMENT ON COLUMN "tushare_norm_fund_manager"."nationality" IS '国籍';
COMMENT ON COLUMN "tushare_norm_fund_manager"."begin_date" IS '任职日期';
COMMENT ON COLUMN "tushare_norm_fund_manager"."end_date" IS '离任日期';
COMMENT ON COLUMN "tushare_norm_fund_manager"."resume" IS '简历';

CREATE TABLE IF NOT EXISTS "tushare_norm_fund_nav" (
    _record_hash CHAR(64) PRIMARY KEY,
    _request_hash CHAR(64) NOT NULL,
    _source_doc_id INTEGER,
    _source_collected_at TIMESTAMPTZ NOT NULL,
    _first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _schema_version INTEGER NOT NULL DEFAULT 1,
    _extra_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    "ts_code" TEXT,
    "ann_date" DATE,
    "nav_date" DATE,
    "unit_nav" NUMERIC,
    "accum_nav" NUMERIC,
    "accum_div" NUMERIC,
    "net_asset" NUMERIC,
    "total_netasset" NUMERIC,
    "adj_nav" NUMERIC
);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_fund_nav_source" ON "tushare_norm_fund_nav" (_source_collected_at DESC);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_fund_nav_date" ON "tushare_norm_fund_nav" ("ann_date" DESC);
COMMENT ON TABLE "tushare_norm_fund_nav" IS '公募基金净值；契约驱动标准化表' ;
COMMENT ON COLUMN "tushare_norm_fund_nav"."ts_code" IS 'TS代码';
COMMENT ON COLUMN "tushare_norm_fund_nav"."ann_date" IS '公告日期';
COMMENT ON COLUMN "tushare_norm_fund_nav"."nav_date" IS '净值日期';
COMMENT ON COLUMN "tushare_norm_fund_nav"."unit_nav" IS '单位净值';
COMMENT ON COLUMN "tushare_norm_fund_nav"."accum_nav" IS '累计净值';
COMMENT ON COLUMN "tushare_norm_fund_nav"."accum_div" IS '累计分红';
COMMENT ON COLUMN "tushare_norm_fund_nav"."net_asset" IS '资产净值';
COMMENT ON COLUMN "tushare_norm_fund_nav"."total_netasset" IS '合计资产净值';
COMMENT ON COLUMN "tushare_norm_fund_nav"."adj_nav" IS '复权单位净值';

CREATE TABLE IF NOT EXISTS "tushare_norm_fund_portfolio" (
    _record_hash CHAR(64) PRIMARY KEY,
    _request_hash CHAR(64) NOT NULL,
    _source_doc_id INTEGER,
    _source_collected_at TIMESTAMPTZ NOT NULL,
    _first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _schema_version INTEGER NOT NULL DEFAULT 1,
    _extra_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    "ts_code" TEXT,
    "ann_date" DATE,
    "end_date" DATE,
    "symbol" TEXT,
    "mkv" NUMERIC,
    "amount" NUMERIC,
    "stk_mkv_ratio" NUMERIC,
    "stk_float_ratio" NUMERIC
);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_fund_portfolio_source" ON "tushare_norm_fund_portfolio" (_source_collected_at DESC);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_fund_portfolio_date" ON "tushare_norm_fund_portfolio" ("ann_date" DESC);
COMMENT ON TABLE "tushare_norm_fund_portfolio" IS '公募基金持仓数据；契约驱动标准化表' ;
COMMENT ON COLUMN "tushare_norm_fund_portfolio"."ts_code" IS 'TS基金代码';
COMMENT ON COLUMN "tushare_norm_fund_portfolio"."ann_date" IS '公告日期';
COMMENT ON COLUMN "tushare_norm_fund_portfolio"."end_date" IS '截止日期';
COMMENT ON COLUMN "tushare_norm_fund_portfolio"."symbol" IS '股票代码';
COMMENT ON COLUMN "tushare_norm_fund_portfolio"."mkv" IS '持有股票市值(元)';
COMMENT ON COLUMN "tushare_norm_fund_portfolio"."amount" IS '持有股票数量（股）';
COMMENT ON COLUMN "tushare_norm_fund_portfolio"."stk_mkv_ratio" IS '占股票市值比';
COMMENT ON COLUMN "tushare_norm_fund_portfolio"."stk_float_ratio" IS '占流通股本比例';

CREATE TABLE IF NOT EXISTS "tushare_norm_fund_share" (
    _record_hash CHAR(64) PRIMARY KEY,
    _request_hash CHAR(64) NOT NULL,
    _source_doc_id INTEGER,
    _source_collected_at TIMESTAMPTZ NOT NULL,
    _first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _schema_version INTEGER NOT NULL DEFAULT 1,
    _extra_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    "ts_code" TEXT,
    "trade_date" DATE,
    "fd_share" NUMERIC
);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_fund_share_source" ON "tushare_norm_fund_share" (_source_collected_at DESC);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_fund_share_date" ON "tushare_norm_fund_share" ("trade_date" DESC);
COMMENT ON TABLE "tushare_norm_fund_share" IS '基金规模数据；契约驱动标准化表' ;
COMMENT ON COLUMN "tushare_norm_fund_share"."ts_code" IS '基金代码，支持多只基金同时提取，用逗号分隔';
COMMENT ON COLUMN "tushare_norm_fund_share"."trade_date" IS '交易（变动）日期，格式YYYYMMDD';
COMMENT ON COLUMN "tushare_norm_fund_share"."fd_share" IS '基金份额（万）';

CREATE TABLE IF NOT EXISTS "tushare_norm_fut_basic" (
    _record_hash CHAR(64) PRIMARY KEY,
    _request_hash CHAR(64) NOT NULL,
    _source_doc_id INTEGER,
    _source_collected_at TIMESTAMPTZ NOT NULL,
    _first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _schema_version INTEGER NOT NULL DEFAULT 1,
    _extra_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    "ts_code" TEXT,
    "symbol" TEXT,
    "exchange" TEXT,
    "name" TEXT,
    "fut_code" TEXT,
    "multiplier" NUMERIC,
    "trade_unit" TEXT,
    "per_unit" NUMERIC,
    "quote_unit" TEXT,
    "quote_unit_desc" TEXT,
    "d_mode_desc" TEXT,
    "list_date" DATE,
    "delist_date" DATE,
    "d_month" TEXT,
    "last_ddate" TEXT,
    "trade_time_desc" TEXT
);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_fut_basic_source" ON "tushare_norm_fut_basic" (_source_collected_at DESC);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_fut_basic_date" ON "tushare_norm_fut_basic" ("delist_date" DESC);
COMMENT ON TABLE "tushare_norm_fut_basic" IS '期货合约信息表；契约驱动标准化表' ;
COMMENT ON COLUMN "tushare_norm_fut_basic"."ts_code" IS '合约代码';
COMMENT ON COLUMN "tushare_norm_fut_basic"."symbol" IS '交易标识';
COMMENT ON COLUMN "tushare_norm_fut_basic"."exchange" IS '交易市场';
COMMENT ON COLUMN "tushare_norm_fut_basic"."name" IS '中文简称';
COMMENT ON COLUMN "tushare_norm_fut_basic"."fut_code" IS '合约产品代码';
COMMENT ON COLUMN "tushare_norm_fut_basic"."multiplier" IS '合约乘数(只适用于国债期货、指数期货)';
COMMENT ON COLUMN "tushare_norm_fut_basic"."trade_unit" IS '交易计量单位';
COMMENT ON COLUMN "tushare_norm_fut_basic"."per_unit" IS '交易单位(每手)';
COMMENT ON COLUMN "tushare_norm_fut_basic"."quote_unit" IS '报价单位';
COMMENT ON COLUMN "tushare_norm_fut_basic"."quote_unit_desc" IS '最小报价单位说明';
COMMENT ON COLUMN "tushare_norm_fut_basic"."d_mode_desc" IS '交割方式说明';
COMMENT ON COLUMN "tushare_norm_fut_basic"."list_date" IS '上市日期';
COMMENT ON COLUMN "tushare_norm_fut_basic"."delist_date" IS '最后交易日期';
COMMENT ON COLUMN "tushare_norm_fut_basic"."d_month" IS '交割月份';
COMMENT ON COLUMN "tushare_norm_fut_basic"."last_ddate" IS '最后交割日';
COMMENT ON COLUMN "tushare_norm_fut_basic"."trade_time_desc" IS '交易时间说明';

CREATE TABLE IF NOT EXISTS "tushare_norm_fut_daily" (
    _record_hash CHAR(64) PRIMARY KEY,
    _request_hash CHAR(64) NOT NULL,
    _source_doc_id INTEGER,
    _source_collected_at TIMESTAMPTZ NOT NULL,
    _first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _schema_version INTEGER NOT NULL DEFAULT 1,
    _extra_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    "ts_code" TEXT,
    "trade_date" DATE,
    "pre_close" NUMERIC,
    "pre_settle" NUMERIC,
    "open" NUMERIC,
    "high" NUMERIC,
    "low" NUMERIC,
    "close" NUMERIC,
    "settle" NUMERIC,
    "change1" NUMERIC,
    "change2" NUMERIC,
    "vol" NUMERIC,
    "amount" NUMERIC,
    "oi" NUMERIC,
    "oi_chg" NUMERIC,
    "delv_settle" NUMERIC
);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_fut_daily_source" ON "tushare_norm_fut_daily" (_source_collected_at DESC);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_fut_daily_date" ON "tushare_norm_fut_daily" ("trade_date" DESC);
COMMENT ON TABLE "tushare_norm_fut_daily" IS '期货日线行情；契约驱动标准化表' ;
COMMENT ON COLUMN "tushare_norm_fut_daily"."ts_code" IS 'TS合约代码';
COMMENT ON COLUMN "tushare_norm_fut_daily"."trade_date" IS '交易日期';
COMMENT ON COLUMN "tushare_norm_fut_daily"."pre_close" IS '昨收盘价';
COMMENT ON COLUMN "tushare_norm_fut_daily"."pre_settle" IS '昨结算价';
COMMENT ON COLUMN "tushare_norm_fut_daily"."open" IS '开盘价';
COMMENT ON COLUMN "tushare_norm_fut_daily"."high" IS '最高价';
COMMENT ON COLUMN "tushare_norm_fut_daily"."low" IS '最低价';
COMMENT ON COLUMN "tushare_norm_fut_daily"."close" IS '收盘价';
COMMENT ON COLUMN "tushare_norm_fut_daily"."settle" IS '结算价';
COMMENT ON COLUMN "tushare_norm_fut_daily"."change1" IS '涨跌1 收盘价-昨结算价';
COMMENT ON COLUMN "tushare_norm_fut_daily"."change2" IS '涨跌2 结算价-昨结算价';
COMMENT ON COLUMN "tushare_norm_fut_daily"."vol" IS '成交量(手)';
COMMENT ON COLUMN "tushare_norm_fut_daily"."amount" IS '成交金额(万元)';
COMMENT ON COLUMN "tushare_norm_fut_daily"."oi" IS '持仓量(手)';
COMMENT ON COLUMN "tushare_norm_fut_daily"."oi_chg" IS '持仓量变化';
COMMENT ON COLUMN "tushare_norm_fut_daily"."delv_settle" IS '交割结算价';

CREATE TABLE IF NOT EXISTS "tushare_norm_fut_holding" (
    _record_hash CHAR(64) PRIMARY KEY,
    _request_hash CHAR(64) NOT NULL,
    _source_doc_id INTEGER,
    _source_collected_at TIMESTAMPTZ NOT NULL,
    _first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _schema_version INTEGER NOT NULL DEFAULT 1,
    _extra_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    "trade_date" DATE,
    "symbol" TEXT,
    "broker" TEXT,
    "vol" BIGINT,
    "vol_chg" BIGINT,
    "long_hld" BIGINT,
    "long_chg" BIGINT,
    "short_hld" BIGINT,
    "short_chg" BIGINT,
    "exchange" TEXT
);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_fut_holding_source" ON "tushare_norm_fut_holding" (_source_collected_at DESC);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_fut_holding_date" ON "tushare_norm_fut_holding" ("trade_date" DESC);
COMMENT ON TABLE "tushare_norm_fut_holding" IS '每日成交持仓排名；契约驱动标准化表' ;
COMMENT ON COLUMN "tushare_norm_fut_holding"."trade_date" IS '交易日期';
COMMENT ON COLUMN "tushare_norm_fut_holding"."symbol" IS '合约代码或类型';
COMMENT ON COLUMN "tushare_norm_fut_holding"."broker" IS '期货公司会员简称';
COMMENT ON COLUMN "tushare_norm_fut_holding"."vol" IS '成交量';
COMMENT ON COLUMN "tushare_norm_fut_holding"."vol_chg" IS '成交量变化';
COMMENT ON COLUMN "tushare_norm_fut_holding"."long_hld" IS '持买仓量';
COMMENT ON COLUMN "tushare_norm_fut_holding"."long_chg" IS '持买仓量变化';
COMMENT ON COLUMN "tushare_norm_fut_holding"."short_hld" IS '持卖仓量';
COMMENT ON COLUMN "tushare_norm_fut_holding"."short_chg" IS '持卖仓量变化';
COMMENT ON COLUMN "tushare_norm_fut_holding"."exchange" IS '交易所';

CREATE TABLE IF NOT EXISTS "tushare_norm_fut_index_daily" (
    _record_hash CHAR(64) PRIMARY KEY,
    _request_hash CHAR(64) NOT NULL,
    _source_doc_id INTEGER,
    _source_collected_at TIMESTAMPTZ NOT NULL,
    _first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _schema_version INTEGER NOT NULL DEFAULT 1,
    _extra_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    "ts_code" TEXT,
    "trade_date" DATE,
    "close" NUMERIC,
    "open" NUMERIC,
    "high" NUMERIC,
    "low" NUMERIC,
    "pre_close" NUMERIC,
    "change" NUMERIC,
    "pct_chg" NUMERIC,
    "vol" NUMERIC,
    "amount" NUMERIC
);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_fut_index_daily_source" ON "tushare_norm_fut_index_daily" (_source_collected_at DESC);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_fut_index_daily_date" ON "tushare_norm_fut_index_daily" ("trade_date" DESC);
COMMENT ON TABLE "tushare_norm_fut_index_daily" IS '南华期货指数日线行情；契约驱动标准化表' ;
COMMENT ON COLUMN "tushare_norm_fut_index_daily"."ts_code" IS 'TS指数代码';
COMMENT ON COLUMN "tushare_norm_fut_index_daily"."trade_date" IS '交易日';
COMMENT ON COLUMN "tushare_norm_fut_index_daily"."close" IS '收盘点位';
COMMENT ON COLUMN "tushare_norm_fut_index_daily"."open" IS '开盘点位';
COMMENT ON COLUMN "tushare_norm_fut_index_daily"."high" IS '最高点位';
COMMENT ON COLUMN "tushare_norm_fut_index_daily"."low" IS '最低点位';
COMMENT ON COLUMN "tushare_norm_fut_index_daily"."pre_close" IS '昨日收盘点';
COMMENT ON COLUMN "tushare_norm_fut_index_daily"."change" IS '涨跌点';
COMMENT ON COLUMN "tushare_norm_fut_index_daily"."pct_chg" IS '涨跌幅';
COMMENT ON COLUMN "tushare_norm_fut_index_daily"."vol" IS '成交量（手）';
COMMENT ON COLUMN "tushare_norm_fut_index_daily"."amount" IS '成交额（千元）';

CREATE TABLE IF NOT EXISTS "tushare_norm_fut_mapping" (
    _record_hash CHAR(64) PRIMARY KEY,
    _request_hash CHAR(64) NOT NULL,
    _source_doc_id INTEGER,
    _source_collected_at TIMESTAMPTZ NOT NULL,
    _first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _schema_version INTEGER NOT NULL DEFAULT 1,
    _extra_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    "ts_code" TEXT,
    "trade_date" DATE,
    "mapping_ts_code" TEXT
);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_fut_mapping_source" ON "tushare_norm_fut_mapping" (_source_collected_at DESC);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_fut_mapping_date" ON "tushare_norm_fut_mapping" ("trade_date" DESC);
COMMENT ON TABLE "tushare_norm_fut_mapping" IS '期货主力与连续合约；契约驱动标准化表' ;
COMMENT ON COLUMN "tushare_norm_fut_mapping"."ts_code" IS '连续合约代码';
COMMENT ON COLUMN "tushare_norm_fut_mapping"."trade_date" IS '起始日期';
COMMENT ON COLUMN "tushare_norm_fut_mapping"."mapping_ts_code" IS '期货合约代码';

CREATE TABLE IF NOT EXISTS "tushare_norm_fut_settle" (
    _record_hash CHAR(64) PRIMARY KEY,
    _request_hash CHAR(64) NOT NULL,
    _source_doc_id INTEGER,
    _source_collected_at TIMESTAMPTZ NOT NULL,
    _first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _schema_version INTEGER NOT NULL DEFAULT 1,
    _extra_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    "ts_code" TEXT,
    "trade_date" DATE,
    "settle" NUMERIC,
    "trading_fee_rate" NUMERIC,
    "trading_fee" NUMERIC,
    "delivery_fee" NUMERIC,
    "b_hedging_margin_rate" NUMERIC,
    "s_hedging_margin_rate" NUMERIC,
    "long_margin_rate" NUMERIC,
    "short_margin_rate" NUMERIC,
    "offset_today_fee" NUMERIC,
    "exchange" TEXT
);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_fut_settle_source" ON "tushare_norm_fut_settle" (_source_collected_at DESC);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_fut_settle_date" ON "tushare_norm_fut_settle" ("trade_date" DESC);
COMMENT ON TABLE "tushare_norm_fut_settle" IS '结算参数；契约驱动标准化表' ;
COMMENT ON COLUMN "tushare_norm_fut_settle"."ts_code" IS '合约代码';
COMMENT ON COLUMN "tushare_norm_fut_settle"."trade_date" IS '交易日期';
COMMENT ON COLUMN "tushare_norm_fut_settle"."settle" IS '结算价';
COMMENT ON COLUMN "tushare_norm_fut_settle"."trading_fee_rate" IS '交易手续费率';
COMMENT ON COLUMN "tushare_norm_fut_settle"."trading_fee" IS '交易手续费';
COMMENT ON COLUMN "tushare_norm_fut_settle"."delivery_fee" IS '交割手续费';
COMMENT ON COLUMN "tushare_norm_fut_settle"."b_hedging_margin_rate" IS '买套保交易保证金率';
COMMENT ON COLUMN "tushare_norm_fut_settle"."s_hedging_margin_rate" IS '卖套保交易保证金率';
COMMENT ON COLUMN "tushare_norm_fut_settle"."long_margin_rate" IS '买投机交易保证金率';
COMMENT ON COLUMN "tushare_norm_fut_settle"."short_margin_rate" IS '卖投机交易保证金率';
COMMENT ON COLUMN "tushare_norm_fut_settle"."offset_today_fee" IS '平今仓手续率';
COMMENT ON COLUMN "tushare_norm_fut_settle"."exchange" IS '交易所';

CREATE TABLE IF NOT EXISTS "tushare_norm_fut_trade_cal" (
    _record_hash CHAR(64) PRIMARY KEY,
    _request_hash CHAR(64) NOT NULL,
    _source_doc_id INTEGER,
    _source_collected_at TIMESTAMPTZ NOT NULL,
    _first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _schema_version INTEGER NOT NULL DEFAULT 1,
    _extra_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    "exchange" TEXT,
    "cal_date" DATE,
    "is_open" BIGINT,
    "pretrade_date" DATE
);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_fut_trade_cal_source" ON "tushare_norm_fut_trade_cal" (_source_collected_at DESC);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_fut_trade_cal_date" ON "tushare_norm_fut_trade_cal" ("cal_date" DESC);
COMMENT ON TABLE "tushare_norm_fut_trade_cal" IS '交易日历；契约驱动标准化表' ;
COMMENT ON COLUMN "tushare_norm_fut_trade_cal"."exchange" IS '交易所 同参数部分描述';
COMMENT ON COLUMN "tushare_norm_fut_trade_cal"."cal_date" IS '日历日期';
COMMENT ON COLUMN "tushare_norm_fut_trade_cal"."is_open" IS '是否交易 0休市 1交易';
COMMENT ON COLUMN "tushare_norm_fut_trade_cal"."pretrade_date" IS '上一个交易日';

CREATE TABLE IF NOT EXISTS "tushare_norm_fut_weekly_detail" (
    _record_hash CHAR(64) PRIMARY KEY,
    _request_hash CHAR(64) NOT NULL,
    _source_doc_id INTEGER,
    _source_collected_at TIMESTAMPTZ NOT NULL,
    _first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _schema_version INTEGER NOT NULL DEFAULT 1,
    _extra_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    "exchange" TEXT,
    "prd" TEXT,
    "name" TEXT,
    "vol" BIGINT,
    "vol_yoy" NUMERIC,
    "amount" NUMERIC,
    "amout_yoy" NUMERIC,
    "cumvol" BIGINT,
    "cumvol_yoy" NUMERIC,
    "cumamt" NUMERIC,
    "cumamt_yoy" NUMERIC,
    "open_interest" BIGINT,
    "interest_wow" NUMERIC,
    "mc_close" NUMERIC,
    "close_wow" NUMERIC,
    "week" TEXT,
    "week_date" DATE
);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_fut_weekly_detail_source" ON "tushare_norm_fut_weekly_detail" (_source_collected_at DESC);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_fut_weekly_detail_date" ON "tushare_norm_fut_weekly_detail" ("week_date" DESC);
COMMENT ON TABLE "tushare_norm_fut_weekly_detail" IS '期货主要品种交易周报；契约驱动标准化表' ;
COMMENT ON COLUMN "tushare_norm_fut_weekly_detail"."exchange" IS '交易所代码';
COMMENT ON COLUMN "tushare_norm_fut_weekly_detail"."prd" IS '期货品种代码';
COMMENT ON COLUMN "tushare_norm_fut_weekly_detail"."name" IS '品种名称';
COMMENT ON COLUMN "tushare_norm_fut_weekly_detail"."vol" IS '成交量（手）';
COMMENT ON COLUMN "tushare_norm_fut_weekly_detail"."vol_yoy" IS '同比增减（%）';
COMMENT ON COLUMN "tushare_norm_fut_weekly_detail"."amount" IS '成交金额（亿元）';
COMMENT ON COLUMN "tushare_norm_fut_weekly_detail"."amout_yoy" IS '同比增减（%）';
COMMENT ON COLUMN "tushare_norm_fut_weekly_detail"."cumvol" IS '年累计成交总量（手）';
COMMENT ON COLUMN "tushare_norm_fut_weekly_detail"."cumvol_yoy" IS '同比增减（%）';
COMMENT ON COLUMN "tushare_norm_fut_weekly_detail"."cumamt" IS '年累计成交金额（亿元）';
COMMENT ON COLUMN "tushare_norm_fut_weekly_detail"."cumamt_yoy" IS '同比增减（%）';
COMMENT ON COLUMN "tushare_norm_fut_weekly_detail"."open_interest" IS '持仓量（手）';
COMMENT ON COLUMN "tushare_norm_fut_weekly_detail"."interest_wow" IS '环比增减（%）';
COMMENT ON COLUMN "tushare_norm_fut_weekly_detail"."mc_close" IS '本周主力合约收盘价';
COMMENT ON COLUMN "tushare_norm_fut_weekly_detail"."close_wow" IS '环比涨跌（%）';
COMMENT ON COLUMN "tushare_norm_fut_weekly_detail"."week" IS '周期';
COMMENT ON COLUMN "tushare_norm_fut_weekly_detail"."week_date" IS '周日期';

CREATE TABLE IF NOT EXISTS "tushare_norm_fut_weekly_monthly" (
    _record_hash CHAR(64) PRIMARY KEY,
    _request_hash CHAR(64) NOT NULL,
    _source_doc_id INTEGER,
    _source_collected_at TIMESTAMPTZ NOT NULL,
    _first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _schema_version INTEGER NOT NULL DEFAULT 1,
    _extra_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    "ts_code" TEXT,
    "trade_date" DATE,
    "end_date" DATE,
    "freq" TEXT,
    "open" NUMERIC,
    "high" NUMERIC,
    "low" NUMERIC,
    "close" NUMERIC,
    "pre_close" NUMERIC,
    "settle" NUMERIC,
    "pre_settle" NUMERIC,
    "vol" NUMERIC,
    "amount" NUMERIC,
    "oi" NUMERIC,
    "oi_chg" NUMERIC,
    "exchange" TEXT,
    "change1" NUMERIC,
    "change2" NUMERIC
);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_fut_weekly_monthly_source" ON "tushare_norm_fut_weekly_monthly" (_source_collected_at DESC);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_fut_weekly_monthly_date" ON "tushare_norm_fut_weekly_monthly" ("trade_date" DESC);
COMMENT ON TABLE "tushare_norm_fut_weekly_monthly" IS '期货周/月线行情(每日更新)；契约驱动标准化表' ;
COMMENT ON COLUMN "tushare_norm_fut_weekly_monthly"."ts_code" IS '期货代码';
COMMENT ON COLUMN "tushare_norm_fut_weekly_monthly"."trade_date" IS '交易日期（每周五或者月末日期）';
COMMENT ON COLUMN "tushare_norm_fut_weekly_monthly"."end_date" IS '计算截至日期';
COMMENT ON COLUMN "tushare_norm_fut_weekly_monthly"."freq" IS '频率(周week,月month)';
COMMENT ON COLUMN "tushare_norm_fut_weekly_monthly"."open" IS '(周/月)开盘价';
COMMENT ON COLUMN "tushare_norm_fut_weekly_monthly"."high" IS '(周/月)最高价';
COMMENT ON COLUMN "tushare_norm_fut_weekly_monthly"."low" IS '(周/月)最低价';
COMMENT ON COLUMN "tushare_norm_fut_weekly_monthly"."close" IS '(周/月)收盘价';
COMMENT ON COLUMN "tushare_norm_fut_weekly_monthly"."pre_close" IS '前一(周/月)收盘价';
COMMENT ON COLUMN "tushare_norm_fut_weekly_monthly"."settle" IS '(周/月)结算价';
COMMENT ON COLUMN "tushare_norm_fut_weekly_monthly"."pre_settle" IS '前一(周/月)结算价';
COMMENT ON COLUMN "tushare_norm_fut_weekly_monthly"."vol" IS '(周/月)成交量(手)';
COMMENT ON COLUMN "tushare_norm_fut_weekly_monthly"."amount" IS '(周/月)成交金额(万元)';
COMMENT ON COLUMN "tushare_norm_fut_weekly_monthly"."oi" IS '(周/月)持仓量(手)';
COMMENT ON COLUMN "tushare_norm_fut_weekly_monthly"."oi_chg" IS '(周/月)持仓量变化';
COMMENT ON COLUMN "tushare_norm_fut_weekly_monthly"."exchange" IS '交易所';
COMMENT ON COLUMN "tushare_norm_fut_weekly_monthly"."change1" IS '(周/月)涨跌1 收盘价-昨结算价';
COMMENT ON COLUMN "tushare_norm_fut_weekly_monthly"."change2" IS '(周/月)涨跌2 结算价-昨结算价';

CREATE TABLE IF NOT EXISTS "tushare_norm_fut_wsr" (
    _record_hash CHAR(64) PRIMARY KEY,
    _request_hash CHAR(64) NOT NULL,
    _source_doc_id INTEGER,
    _source_collected_at TIMESTAMPTZ NOT NULL,
    _first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _schema_version INTEGER NOT NULL DEFAULT 1,
    _extra_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    "trade_date" DATE,
    "symbol" TEXT,
    "fut_name" TEXT,
    "warehouse" TEXT,
    "wh_id" TEXT,
    "pre_vol" BIGINT,
    "vol" BIGINT,
    "vol_chg" BIGINT,
    "area" TEXT,
    "year" TEXT,
    "grade" TEXT,
    "brand" TEXT,
    "place" TEXT,
    "pd" BIGINT,
    "is_ct" TEXT,
    "unit" TEXT,
    "exchange" TEXT
);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_fut_wsr_source" ON "tushare_norm_fut_wsr" (_source_collected_at DESC);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_fut_wsr_date" ON "tushare_norm_fut_wsr" ("trade_date" DESC);
COMMENT ON TABLE "tushare_norm_fut_wsr" IS '仓单日报；契约驱动标准化表' ;
COMMENT ON COLUMN "tushare_norm_fut_wsr"."trade_date" IS '交易日期';
COMMENT ON COLUMN "tushare_norm_fut_wsr"."symbol" IS '产品代码';
COMMENT ON COLUMN "tushare_norm_fut_wsr"."fut_name" IS '产品名称';
COMMENT ON COLUMN "tushare_norm_fut_wsr"."warehouse" IS '仓库名称';
COMMENT ON COLUMN "tushare_norm_fut_wsr"."wh_id" IS '仓库编号';
COMMENT ON COLUMN "tushare_norm_fut_wsr"."pre_vol" IS '昨日仓单量';
COMMENT ON COLUMN "tushare_norm_fut_wsr"."vol" IS '今日仓单量';
COMMENT ON COLUMN "tushare_norm_fut_wsr"."vol_chg" IS '增减量';
COMMENT ON COLUMN "tushare_norm_fut_wsr"."area" IS '地区';
COMMENT ON COLUMN "tushare_norm_fut_wsr"."year" IS '年度';
COMMENT ON COLUMN "tushare_norm_fut_wsr"."grade" IS '等级';
COMMENT ON COLUMN "tushare_norm_fut_wsr"."brand" IS '品牌';
COMMENT ON COLUMN "tushare_norm_fut_wsr"."place" IS '产地';
COMMENT ON COLUMN "tushare_norm_fut_wsr"."pd" IS '升贴水';
COMMENT ON COLUMN "tushare_norm_fut_wsr"."is_ct" IS '是否折算仓单';
COMMENT ON COLUMN "tushare_norm_fut_wsr"."unit" IS '单位';
COMMENT ON COLUMN "tushare_norm_fut_wsr"."exchange" IS '交易所';

CREATE TABLE IF NOT EXISTS "tushare_norm_gz_index" (
    _record_hash CHAR(64) PRIMARY KEY,
    _request_hash CHAR(64) NOT NULL,
    _source_doc_id INTEGER,
    _source_collected_at TIMESTAMPTZ NOT NULL,
    _first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _schema_version INTEGER NOT NULL DEFAULT 1,
    _extra_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    "date" DATE,
    "d10_rate" NUMERIC,
    "m1_rate" NUMERIC,
    "m3_rate" NUMERIC,
    "m6_rate" NUMERIC,
    "m12_rate" NUMERIC,
    "long_rate" NUMERIC
);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_gz_index_source" ON "tushare_norm_gz_index" (_source_collected_at DESC);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_gz_index_date" ON "tushare_norm_gz_index" ("date" DESC);
COMMENT ON TABLE "tushare_norm_gz_index" IS '广州民间借贷利率；契约驱动标准化表' ;
COMMENT ON COLUMN "tushare_norm_gz_index"."date" IS '日期';
COMMENT ON COLUMN "tushare_norm_gz_index"."d10_rate" IS '小额贷市场平均利率（十天） （单位：%，下同）';
COMMENT ON COLUMN "tushare_norm_gz_index"."m1_rate" IS '小额贷市场平均利率（一月期）';
COMMENT ON COLUMN "tushare_norm_gz_index"."m3_rate" IS '小额贷市场平均利率（三月期）';
COMMENT ON COLUMN "tushare_norm_gz_index"."m6_rate" IS '小额贷市场平均利率（六月期）';
COMMENT ON COLUMN "tushare_norm_gz_index"."m12_rate" IS '小额贷市场平均利率（一年期）';
COMMENT ON COLUMN "tushare_norm_gz_index"."long_rate" IS '小额贷市场平均利率（长期）';

CREATE TABLE IF NOT EXISTS "tushare_norm_hibor" (
    _record_hash CHAR(64) PRIMARY KEY,
    _request_hash CHAR(64) NOT NULL,
    _source_doc_id INTEGER,
    _source_collected_at TIMESTAMPTZ NOT NULL,
    _first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _schema_version INTEGER NOT NULL DEFAULT 1,
    _extra_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    "date" DATE,
    "on" NUMERIC,
    "1w" NUMERIC,
    "2w" NUMERIC,
    "1m" NUMERIC,
    "2m" NUMERIC,
    "3m" NUMERIC,
    "6m" NUMERIC,
    "12m" NUMERIC
);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_hibor_source" ON "tushare_norm_hibor" (_source_collected_at DESC);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_hibor_date" ON "tushare_norm_hibor" ("date" DESC);
COMMENT ON TABLE "tushare_norm_hibor" IS 'Hibor利率；契约驱动标准化表' ;
COMMENT ON COLUMN "tushare_norm_hibor"."date" IS '日期';
COMMENT ON COLUMN "tushare_norm_hibor"."on" IS '隔夜';
COMMENT ON COLUMN "tushare_norm_hibor"."1w" IS '1周';
COMMENT ON COLUMN "tushare_norm_hibor"."2w" IS '2周';
COMMENT ON COLUMN "tushare_norm_hibor"."1m" IS '1个月';
COMMENT ON COLUMN "tushare_norm_hibor"."2m" IS '2个月';
COMMENT ON COLUMN "tushare_norm_hibor"."3m" IS '3个月';
COMMENT ON COLUMN "tushare_norm_hibor"."6m" IS '6个月';
COMMENT ON COLUMN "tushare_norm_hibor"."12m" IS '12个月';

CREATE TABLE IF NOT EXISTS "tushare_norm_hk_basic" (
    _record_hash CHAR(64) PRIMARY KEY,
    _request_hash CHAR(64) NOT NULL,
    _source_doc_id INTEGER,
    _source_collected_at TIMESTAMPTZ NOT NULL,
    _first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _schema_version INTEGER NOT NULL DEFAULT 1,
    _extra_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    "ts_code" TEXT,
    "name" TEXT,
    "fullname" TEXT,
    "enname" TEXT,
    "cn_spell" TEXT,
    "market" TEXT,
    "list_status" TEXT,
    "list_date" DATE,
    "delist_date" DATE,
    "trade_unit" NUMERIC,
    "isin" TEXT,
    "curr_type" TEXT
);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_hk_basic_source" ON "tushare_norm_hk_basic" (_source_collected_at DESC);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_hk_basic_date" ON "tushare_norm_hk_basic" ("delist_date" DESC);
COMMENT ON TABLE "tushare_norm_hk_basic" IS '港股列表；契约驱动标准化表' ;
COMMENT ON COLUMN "tushare_norm_hk_basic"."ts_code" IS 'TS代码';
COMMENT ON COLUMN "tushare_norm_hk_basic"."name" IS '股票简称';
COMMENT ON COLUMN "tushare_norm_hk_basic"."fullname" IS '公司全称';
COMMENT ON COLUMN "tushare_norm_hk_basic"."enname" IS '英文名称';
COMMENT ON COLUMN "tushare_norm_hk_basic"."cn_spell" IS '拼音';
COMMENT ON COLUMN "tushare_norm_hk_basic"."market" IS '市场类别';
COMMENT ON COLUMN "tushare_norm_hk_basic"."list_status" IS '上市状态';
COMMENT ON COLUMN "tushare_norm_hk_basic"."list_date" IS '上市日期';
COMMENT ON COLUMN "tushare_norm_hk_basic"."delist_date" IS '退市日期';
COMMENT ON COLUMN "tushare_norm_hk_basic"."trade_unit" IS '交易单位';
COMMENT ON COLUMN "tushare_norm_hk_basic"."isin" IS 'ISIN代码';
COMMENT ON COLUMN "tushare_norm_hk_basic"."curr_type" IS '货币代码';

CREATE TABLE IF NOT EXISTS "tushare_norm_hk_daily" (
    _record_hash CHAR(64) PRIMARY KEY,
    _request_hash CHAR(64) NOT NULL,
    _source_doc_id INTEGER,
    _source_collected_at TIMESTAMPTZ NOT NULL,
    _first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _schema_version INTEGER NOT NULL DEFAULT 1,
    _extra_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    "ts_code" TEXT,
    "trade_date" DATE,
    "open" NUMERIC,
    "high" NUMERIC,
    "low" NUMERIC,
    "close" NUMERIC,
    "pre_close" NUMERIC,
    "change" NUMERIC,
    "pct_chg" NUMERIC,
    "vol" NUMERIC,
    "amount" NUMERIC
);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_hk_daily_source" ON "tushare_norm_hk_daily" (_source_collected_at DESC);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_hk_daily_date" ON "tushare_norm_hk_daily" ("trade_date" DESC);
COMMENT ON TABLE "tushare_norm_hk_daily" IS '港股行情；契约驱动标准化表' ;
COMMENT ON COLUMN "tushare_norm_hk_daily"."ts_code" IS '股票代码';
COMMENT ON COLUMN "tushare_norm_hk_daily"."trade_date" IS '交易日期';
COMMENT ON COLUMN "tushare_norm_hk_daily"."open" IS '开盘价';
COMMENT ON COLUMN "tushare_norm_hk_daily"."high" IS '最高价';
COMMENT ON COLUMN "tushare_norm_hk_daily"."low" IS '最低价';
COMMENT ON COLUMN "tushare_norm_hk_daily"."close" IS '收盘价';
COMMENT ON COLUMN "tushare_norm_hk_daily"."pre_close" IS '昨收价';
COMMENT ON COLUMN "tushare_norm_hk_daily"."change" IS '涨跌额';
COMMENT ON COLUMN "tushare_norm_hk_daily"."pct_chg" IS '涨跌幅(%)';
COMMENT ON COLUMN "tushare_norm_hk_daily"."vol" IS '成交量(股)';
COMMENT ON COLUMN "tushare_norm_hk_daily"."amount" IS '成交额(元)';

CREATE TABLE IF NOT EXISTS "tushare_norm_hk_tradecal" (
    _record_hash CHAR(64) PRIMARY KEY,
    _request_hash CHAR(64) NOT NULL,
    _source_doc_id INTEGER,
    _source_collected_at TIMESTAMPTZ NOT NULL,
    _first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _schema_version INTEGER NOT NULL DEFAULT 1,
    _extra_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    "cal_date" DATE,
    "is_open" BIGINT,
    "pretrade_date" DATE
);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_hk_tradecal_source" ON "tushare_norm_hk_tradecal" (_source_collected_at DESC);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_hk_tradecal_date" ON "tushare_norm_hk_tradecal" ("cal_date" DESC);
COMMENT ON TABLE "tushare_norm_hk_tradecal" IS '港股交易日历；契约驱动标准化表' ;
COMMENT ON COLUMN "tushare_norm_hk_tradecal"."cal_date" IS '日历日期';
COMMENT ON COLUMN "tushare_norm_hk_tradecal"."is_open" IS '是否交易 ''0''休市 ''1''交易';
COMMENT ON COLUMN "tushare_norm_hk_tradecal"."pretrade_date" IS '上一个交易日';

CREATE TABLE IF NOT EXISTS "tushare_norm_idx_anns" (
    _record_hash CHAR(64) PRIMARY KEY,
    _request_hash CHAR(64) NOT NULL,
    _source_doc_id INTEGER,
    _source_collected_at TIMESTAMPTZ NOT NULL,
    _first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _schema_version INTEGER NOT NULL DEFAULT 1,
    _extra_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    "ann_date" DATE,
    "title" TEXT,
    "url" TEXT,
    "source" TEXT,
    "type" TEXT
);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_idx_anns_source" ON "tushare_norm_idx_anns" (_source_collected_at DESC);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_idx_anns_date" ON "tushare_norm_idx_anns" ("ann_date" DESC);
COMMENT ON TABLE "tushare_norm_idx_anns" IS '指数公告；契约驱动标准化表' ;
COMMENT ON COLUMN "tushare_norm_idx_anns"."ann_date" IS '公告日期';
COMMENT ON COLUMN "tushare_norm_idx_anns"."title" IS '标题';
COMMENT ON COLUMN "tushare_norm_idx_anns"."url" IS '链接';
COMMENT ON COLUMN "tushare_norm_idx_anns"."source" IS '来源';
COMMENT ON COLUMN "tushare_norm_idx_anns"."type" IS '类型(指数发布、指数修订、指数更名、其他）';

CREATE TABLE IF NOT EXISTS "tushare_norm_idx_factor_pro" (
    _record_hash CHAR(64) PRIMARY KEY,
    _request_hash CHAR(64) NOT NULL,
    _source_doc_id INTEGER,
    _source_collected_at TIMESTAMPTZ NOT NULL,
    _first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _schema_version INTEGER NOT NULL DEFAULT 1,
    _extra_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    "ts_code" TEXT,
    "trade_date" DATE,
    "open" NUMERIC,
    "high" NUMERIC,
    "low" NUMERIC,
    "close" NUMERIC,
    "pre_close" NUMERIC,
    "change" NUMERIC,
    "pct_change" NUMERIC,
    "vol" NUMERIC,
    "amount" NUMERIC,
    "asi_bfq" NUMERIC,
    "asit_bfq" NUMERIC,
    "atr_bfq" NUMERIC,
    "bbi_bfq" NUMERIC,
    "bias1_bfq" NUMERIC,
    "bias2_bfq" NUMERIC,
    "bias3_bfq" NUMERIC,
    "boll_lower_bfq" NUMERIC,
    "boll_mid_bfq" NUMERIC,
    "boll_upper_bfq" NUMERIC,
    "brar_ar_bfq" NUMERIC,
    "brar_br_bfq" NUMERIC,
    "cci_bfq" NUMERIC,
    "cr_bfq" NUMERIC,
    "dfma_dif_bfq" NUMERIC,
    "dfma_difma_bfq" NUMERIC,
    "dmi_adx_bfq" NUMERIC,
    "dmi_adxr_bfq" NUMERIC,
    "dmi_mdi_bfq" NUMERIC,
    "dmi_pdi_bfq" NUMERIC,
    "downdays" NUMERIC,
    "updays" NUMERIC,
    "dpo_bfq" NUMERIC,
    "madpo_bfq" NUMERIC,
    "ema_bfq_10" NUMERIC,
    "ema_bfq_20" NUMERIC,
    "ema_bfq_250" NUMERIC,
    "ema_bfq_30" NUMERIC,
    "ema_bfq_5" NUMERIC,
    "ema_bfq_60" NUMERIC,
    "ema_bfq_90" NUMERIC,
    "emv_bfq" NUMERIC,
    "maemv_bfq" NUMERIC,
    "expma_12_bfq" NUMERIC,
    "expma_50_bfq" NUMERIC,
    "kdj_bfq" NUMERIC,
    "kdj_d_bfq" NUMERIC,
    "kdj_k_bfq" NUMERIC,
    "ktn_down_bfq" NUMERIC,
    "ktn_mid_bfq" NUMERIC,
    "ktn_upper_bfq" NUMERIC,
    "lowdays" NUMERIC,
    "topdays" NUMERIC,
    "ma_bfq_10" NUMERIC,
    "ma_bfq_20" NUMERIC,
    "ma_bfq_250" NUMERIC,
    "ma_bfq_30" NUMERIC,
    "ma_bfq_5" NUMERIC,
    "ma_bfq_60" NUMERIC,
    "ma_bfq_90" NUMERIC,
    "macd_bfq" NUMERIC,
    "macd_dea_bfq" NUMERIC,
    "macd_dif_bfq" NUMERIC,
    "mass_bfq" NUMERIC,
    "ma_mass_bfq" NUMERIC,
    "mfi_bfq" NUMERIC,
    "mtm_bfq" NUMERIC,
    "mtmma_bfq" NUMERIC,
    "obv_bfq" NUMERIC,
    "psy_bfq" NUMERIC,
    "psyma_bfq" NUMERIC,
    "roc_bfq" NUMERIC,
    "maroc_bfq" NUMERIC,
    "rsi_bfq_12" NUMERIC,
    "rsi_bfq_24" NUMERIC,
    "rsi_bfq_6" NUMERIC,
    "taq_down_bfq" NUMERIC,
    "taq_mid_bfq" NUMERIC,
    "taq_up_bfq" NUMERIC,
    "trix_bfq" NUMERIC,
    "trma_bfq" NUMERIC,
    "vr_bfq" NUMERIC,
    "wr_bfq" NUMERIC,
    "wr1_bfq" NUMERIC,
    "xsii_td1_bfq" NUMERIC,
    "xsii_td2_bfq" NUMERIC,
    "xsii_td3_bfq" NUMERIC,
    "xsii_td4_bfq" NUMERIC
);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_idx_factor_pro_source" ON "tushare_norm_idx_factor_pro" (_source_collected_at DESC);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_idx_factor_pro_date" ON "tushare_norm_idx_factor_pro" ("trade_date" DESC);
COMMENT ON TABLE "tushare_norm_idx_factor_pro" IS '指数技术因子(专业版)；契约驱动标准化表' ;
COMMENT ON COLUMN "tushare_norm_idx_factor_pro"."ts_code" IS '指数代码';
COMMENT ON COLUMN "tushare_norm_idx_factor_pro"."trade_date" IS '交易日期';
COMMENT ON COLUMN "tushare_norm_idx_factor_pro"."open" IS '开盘价';
COMMENT ON COLUMN "tushare_norm_idx_factor_pro"."high" IS '最高价';
COMMENT ON COLUMN "tushare_norm_idx_factor_pro"."low" IS '最低价';
COMMENT ON COLUMN "tushare_norm_idx_factor_pro"."close" IS '收盘价';
COMMENT ON COLUMN "tushare_norm_idx_factor_pro"."pre_close" IS '昨收价';
COMMENT ON COLUMN "tushare_norm_idx_factor_pro"."change" IS '涨跌额';
COMMENT ON COLUMN "tushare_norm_idx_factor_pro"."pct_change" IS '涨跌幅 （未复权，如果是复权请用 通用行情接口 ）';
COMMENT ON COLUMN "tushare_norm_idx_factor_pro"."vol" IS '成交量 （手）';
COMMENT ON COLUMN "tushare_norm_idx_factor_pro"."amount" IS '成交额 （千元）';
COMMENT ON COLUMN "tushare_norm_idx_factor_pro"."asi_bfq" IS '振动升降指标-OPEN, CLOSE, HIGH, LOW, M1=26, M2=10';
COMMENT ON COLUMN "tushare_norm_idx_factor_pro"."asit_bfq" IS '振动升降指标-OPEN, CLOSE, HIGH, LOW, M1=26, M2=10';
COMMENT ON COLUMN "tushare_norm_idx_factor_pro"."atr_bfq" IS '真实波动N日平均值-CLOSE, HIGH, LOW, N=20';
COMMENT ON COLUMN "tushare_norm_idx_factor_pro"."bbi_bfq" IS 'BBI多空指标-CLOSE, M1=3, M2=6, M3=12, M4=20';
COMMENT ON COLUMN "tushare_norm_idx_factor_pro"."bias1_bfq" IS 'BIAS乖离率-CLOSE, L1=6, L2=12, L3=24';
COMMENT ON COLUMN "tushare_norm_idx_factor_pro"."bias2_bfq" IS 'BIAS乖离率-CLOSE, L1=6, L2=12, L3=24';
COMMENT ON COLUMN "tushare_norm_idx_factor_pro"."bias3_bfq" IS 'BIAS乖离率-CLOSE, L1=6, L2=12, L3=24';
COMMENT ON COLUMN "tushare_norm_idx_factor_pro"."boll_lower_bfq" IS 'BOLL指标，布林带-CLOSE, N=20, P=2';
COMMENT ON COLUMN "tushare_norm_idx_factor_pro"."boll_mid_bfq" IS 'BOLL指标，布林带-CLOSE, N=20, P=2';
COMMENT ON COLUMN "tushare_norm_idx_factor_pro"."boll_upper_bfq" IS 'BOLL指标，布林带-CLOSE, N=20, P=2';
COMMENT ON COLUMN "tushare_norm_idx_factor_pro"."brar_ar_bfq" IS 'BRAR情绪指标-OPEN, CLOSE, HIGH, LOW, M1=26';
COMMENT ON COLUMN "tushare_norm_idx_factor_pro"."brar_br_bfq" IS 'BRAR情绪指标-OPEN, CLOSE, HIGH, LOW, M1=26';
COMMENT ON COLUMN "tushare_norm_idx_factor_pro"."cci_bfq" IS '顺势指标又叫CCI指标-CLOSE, HIGH, LOW, N=14';
COMMENT ON COLUMN "tushare_norm_idx_factor_pro"."cr_bfq" IS 'CR价格动量指标-CLOSE, HIGH, LOW, N=20';
COMMENT ON COLUMN "tushare_norm_idx_factor_pro"."dfma_dif_bfq" IS '平行线差指标-CLOSE, N1=10, N2=50, M=10';
COMMENT ON COLUMN "tushare_norm_idx_factor_pro"."dfma_difma_bfq" IS '平行线差指标-CLOSE, N1=10, N2=50, M=10';
COMMENT ON COLUMN "tushare_norm_idx_factor_pro"."dmi_adx_bfq" IS '动向指标-CLOSE, HIGH, LOW, M1=14, M2=6';
COMMENT ON COLUMN "tushare_norm_idx_factor_pro"."dmi_adxr_bfq" IS '动向指标-CLOSE, HIGH, LOW, M1=14, M2=6';
COMMENT ON COLUMN "tushare_norm_idx_factor_pro"."dmi_mdi_bfq" IS '动向指标-CLOSE, HIGH, LOW, M1=14, M2=6';
COMMENT ON COLUMN "tushare_norm_idx_factor_pro"."dmi_pdi_bfq" IS '动向指标-CLOSE, HIGH, LOW, M1=14, M2=6';
COMMENT ON COLUMN "tushare_norm_idx_factor_pro"."downdays" IS '连跌天数';
COMMENT ON COLUMN "tushare_norm_idx_factor_pro"."updays" IS '连涨天数';
COMMENT ON COLUMN "tushare_norm_idx_factor_pro"."dpo_bfq" IS '区间震荡线-CLOSE, M1=20, M2=10, M3=6';
COMMENT ON COLUMN "tushare_norm_idx_factor_pro"."madpo_bfq" IS '区间震荡线-CLOSE, M1=20, M2=10, M3=6';
COMMENT ON COLUMN "tushare_norm_idx_factor_pro"."ema_bfq_10" IS '指数移动平均-N=10';
COMMENT ON COLUMN "tushare_norm_idx_factor_pro"."ema_bfq_20" IS '指数移动平均-N=20';
COMMENT ON COLUMN "tushare_norm_idx_factor_pro"."ema_bfq_250" IS '指数移动平均-N=250';
COMMENT ON COLUMN "tushare_norm_idx_factor_pro"."ema_bfq_30" IS '指数移动平均-N=30';
COMMENT ON COLUMN "tushare_norm_idx_factor_pro"."ema_bfq_5" IS '指数移动平均-N=5';
COMMENT ON COLUMN "tushare_norm_idx_factor_pro"."ema_bfq_60" IS '指数移动平均-N=60';
COMMENT ON COLUMN "tushare_norm_idx_factor_pro"."ema_bfq_90" IS '指数移动平均-N=90';
COMMENT ON COLUMN "tushare_norm_idx_factor_pro"."emv_bfq" IS '简易波动指标-HIGH, LOW, VOL, N=14, M=9';
COMMENT ON COLUMN "tushare_norm_idx_factor_pro"."maemv_bfq" IS '简易波动指标-HIGH, LOW, VOL, N=14, M=9';
COMMENT ON COLUMN "tushare_norm_idx_factor_pro"."expma_12_bfq" IS 'EMA指数平均数指标-CLOSE, N1=12, N2=50';
COMMENT ON COLUMN "tushare_norm_idx_factor_pro"."expma_50_bfq" IS 'EMA指数平均数指标-CLOSE, N1=12, N2=50';
COMMENT ON COLUMN "tushare_norm_idx_factor_pro"."kdj_bfq" IS 'KDJ指标-CLOSE, HIGH, LOW, N=9, M1=3, M2=3';
COMMENT ON COLUMN "tushare_norm_idx_factor_pro"."kdj_d_bfq" IS 'KDJ指标-CLOSE, HIGH, LOW, N=9, M1=3, M2=3';
COMMENT ON COLUMN "tushare_norm_idx_factor_pro"."kdj_k_bfq" IS 'KDJ指标-CLOSE, HIGH, LOW, N=9, M1=3, M2=3';
COMMENT ON COLUMN "tushare_norm_idx_factor_pro"."ktn_down_bfq" IS '肯特纳交易通道, N选20日，ATR选10日-CLOSE, HIGH, LOW, N=20, M=10';
COMMENT ON COLUMN "tushare_norm_idx_factor_pro"."ktn_mid_bfq" IS '肯特纳交易通道, N选20日，ATR选10日-CLOSE, HIGH, LOW, N=20, M=10';
COMMENT ON COLUMN "tushare_norm_idx_factor_pro"."ktn_upper_bfq" IS '肯特纳交易通道, N选20日，ATR选10日-CLOSE, HIGH, LOW, N=20, M=10';
COMMENT ON COLUMN "tushare_norm_idx_factor_pro"."lowdays" IS 'LOWRANGE(LOW)表示当前最低价是近多少周期内最低价的最小值';
COMMENT ON COLUMN "tushare_norm_idx_factor_pro"."topdays" IS 'TOPRANGE(HIGH)表示当前最高价是近多少周期内最高价的最大值';
COMMENT ON COLUMN "tushare_norm_idx_factor_pro"."ma_bfq_10" IS '简单移动平均-N=10';
COMMENT ON COLUMN "tushare_norm_idx_factor_pro"."ma_bfq_20" IS '简单移动平均-N=20';
COMMENT ON COLUMN "tushare_norm_idx_factor_pro"."ma_bfq_250" IS '简单移动平均-N=250';
COMMENT ON COLUMN "tushare_norm_idx_factor_pro"."ma_bfq_30" IS '简单移动平均-N=30';
COMMENT ON COLUMN "tushare_norm_idx_factor_pro"."ma_bfq_5" IS '简单移动平均-N=5';
COMMENT ON COLUMN "tushare_norm_idx_factor_pro"."ma_bfq_60" IS '简单移动平均-N=60';
COMMENT ON COLUMN "tushare_norm_idx_factor_pro"."ma_bfq_90" IS '简单移动平均-N=90';
COMMENT ON COLUMN "tushare_norm_idx_factor_pro"."macd_bfq" IS 'MACD指标-CLOSE, SHORT=12, LONG=26, M=9';
COMMENT ON COLUMN "tushare_norm_idx_factor_pro"."macd_dea_bfq" IS 'MACD指标-CLOSE, SHORT=12, LONG=26, M=9';
COMMENT ON COLUMN "tushare_norm_idx_factor_pro"."macd_dif_bfq" IS 'MACD指标-CLOSE, SHORT=12, LONG=26, M=9';
COMMENT ON COLUMN "tushare_norm_idx_factor_pro"."mass_bfq" IS '梅斯线-HIGH, LOW, N1=9, N2=25, M=6';
COMMENT ON COLUMN "tushare_norm_idx_factor_pro"."ma_mass_bfq" IS '梅斯线-HIGH, LOW, N1=9, N2=25, M=6';
COMMENT ON COLUMN "tushare_norm_idx_factor_pro"."mfi_bfq" IS 'MFI指标是成交量的RSI指标-CLOSE, HIGH, LOW, VOL, N=14';
COMMENT ON COLUMN "tushare_norm_idx_factor_pro"."mtm_bfq" IS '动量指标-CLOSE, N=12, M=6';
COMMENT ON COLUMN "tushare_norm_idx_factor_pro"."mtmma_bfq" IS '动量指标-CLOSE, N=12, M=6';
COMMENT ON COLUMN "tushare_norm_idx_factor_pro"."obv_bfq" IS '能量潮指标-CLOSE, VOL';
COMMENT ON COLUMN "tushare_norm_idx_factor_pro"."psy_bfq" IS '投资者对股市涨跌产生心理波动的情绪指标-CLOSE, N=12, M=6';
COMMENT ON COLUMN "tushare_norm_idx_factor_pro"."psyma_bfq" IS '投资者对股市涨跌产生心理波动的情绪指标-CLOSE, N=12, M=6';
COMMENT ON COLUMN "tushare_norm_idx_factor_pro"."roc_bfq" IS '变动率指标-CLOSE, N=12, M=6';
COMMENT ON COLUMN "tushare_norm_idx_factor_pro"."maroc_bfq" IS '变动率指标-CLOSE, N=12, M=6';
COMMENT ON COLUMN "tushare_norm_idx_factor_pro"."rsi_bfq_12" IS 'RSI指标-CLOSE, N=12';
COMMENT ON COLUMN "tushare_norm_idx_factor_pro"."rsi_bfq_24" IS 'RSI指标-CLOSE, N=24';
COMMENT ON COLUMN "tushare_norm_idx_factor_pro"."rsi_bfq_6" IS 'RSI指标-CLOSE, N=6';
COMMENT ON COLUMN "tushare_norm_idx_factor_pro"."taq_down_bfq" IS '唐安奇通道(海龟)交易指标-HIGH, LOW, 20';
COMMENT ON COLUMN "tushare_norm_idx_factor_pro"."taq_mid_bfq" IS '唐安奇通道(海龟)交易指标-HIGH, LOW, 20';
COMMENT ON COLUMN "tushare_norm_idx_factor_pro"."taq_up_bfq" IS '唐安奇通道(海龟)交易指标-HIGH, LOW, 20';
COMMENT ON COLUMN "tushare_norm_idx_factor_pro"."trix_bfq" IS '三重指数平滑平均线-CLOSE, M1=12, M2=20';
COMMENT ON COLUMN "tushare_norm_idx_factor_pro"."trma_bfq" IS '三重指数平滑平均线-CLOSE, M1=12, M2=20';
COMMENT ON COLUMN "tushare_norm_idx_factor_pro"."vr_bfq" IS 'VR容量比率-CLOSE, VOL, M1=26';
COMMENT ON COLUMN "tushare_norm_idx_factor_pro"."wr_bfq" IS 'W&R 威廉指标-CLOSE, HIGH, LOW, N=10, N1=6';
COMMENT ON COLUMN "tushare_norm_idx_factor_pro"."wr1_bfq" IS 'W&R 威廉指标-CLOSE, HIGH, LOW, N=10, N1=6';
COMMENT ON COLUMN "tushare_norm_idx_factor_pro"."xsii_td1_bfq" IS '薛斯通道II-CLOSE, HIGH, LOW, N=102, M=7';
COMMENT ON COLUMN "tushare_norm_idx_factor_pro"."xsii_td2_bfq" IS '薛斯通道II-CLOSE, HIGH, LOW, N=102, M=7';
COMMENT ON COLUMN "tushare_norm_idx_factor_pro"."xsii_td3_bfq" IS '薛斯通道II-CLOSE, HIGH, LOW, N=102, M=7';
COMMENT ON COLUMN "tushare_norm_idx_factor_pro"."xsii_td4_bfq" IS '薛斯通道II-CLOSE, HIGH, LOW, N=102, M=7';

CREATE TABLE IF NOT EXISTS "tushare_norm_index_classify" (
    _record_hash CHAR(64) PRIMARY KEY,
    _request_hash CHAR(64) NOT NULL,
    _source_doc_id INTEGER,
    _source_collected_at TIMESTAMPTZ NOT NULL,
    _first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _schema_version INTEGER NOT NULL DEFAULT 1,
    _extra_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    "index_code" TEXT,
    "industry_name" TEXT,
    "parent_code" TEXT,
    "level" TEXT,
    "industry_code" TEXT,
    "is_pub" TEXT,
    "src" TEXT
);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_index_classify_source" ON "tushare_norm_index_classify" (_source_collected_at DESC);
COMMENT ON TABLE "tushare_norm_index_classify" IS '申万行业分类；契约驱动标准化表' ;
COMMENT ON COLUMN "tushare_norm_index_classify"."index_code" IS '指数代码';
COMMENT ON COLUMN "tushare_norm_index_classify"."industry_name" IS '行业名称';
COMMENT ON COLUMN "tushare_norm_index_classify"."parent_code" IS '父级代码';
COMMENT ON COLUMN "tushare_norm_index_classify"."level" IS '行业层级';
COMMENT ON COLUMN "tushare_norm_index_classify"."industry_code" IS '行业代码';
COMMENT ON COLUMN "tushare_norm_index_classify"."is_pub" IS '是否发布了指数';
COMMENT ON COLUMN "tushare_norm_index_classify"."src" IS '行业分类（SW申万）';

CREATE TABLE IF NOT EXISTS "tushare_norm_index_member_all" (
    _record_hash CHAR(64) PRIMARY KEY,
    _request_hash CHAR(64) NOT NULL,
    _source_doc_id INTEGER,
    _source_collected_at TIMESTAMPTZ NOT NULL,
    _first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _schema_version INTEGER NOT NULL DEFAULT 1,
    _extra_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    "l1_code" TEXT,
    "l1_name" TEXT,
    "l2_code" TEXT,
    "l2_name" TEXT,
    "l3_code" TEXT,
    "l3_name" TEXT,
    "ts_code" TEXT,
    "name" TEXT,
    "in_date" DATE,
    "out_date" DATE,
    "is_new" TEXT
);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_index_member_all_source" ON "tushare_norm_index_member_all" (_source_collected_at DESC);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_index_member_all_date" ON "tushare_norm_index_member_all" ("in_date" DESC);
COMMENT ON TABLE "tushare_norm_index_member_all" IS '申万行业成分构成(分级)；契约驱动标准化表' ;
COMMENT ON COLUMN "tushare_norm_index_member_all"."l1_code" IS '一级行业代码';
COMMENT ON COLUMN "tushare_norm_index_member_all"."l1_name" IS '一级行业名称';
COMMENT ON COLUMN "tushare_norm_index_member_all"."l2_code" IS '二级行业代码';
COMMENT ON COLUMN "tushare_norm_index_member_all"."l2_name" IS '二级行业名称';
COMMENT ON COLUMN "tushare_norm_index_member_all"."l3_code" IS '三级行业代码';
COMMENT ON COLUMN "tushare_norm_index_member_all"."l3_name" IS '三级行业名称';
COMMENT ON COLUMN "tushare_norm_index_member_all"."ts_code" IS '成分股票代码';
COMMENT ON COLUMN "tushare_norm_index_member_all"."name" IS '成分股票名称';
COMMENT ON COLUMN "tushare_norm_index_member_all"."in_date" IS '纳入日期';
COMMENT ON COLUMN "tushare_norm_index_member_all"."out_date" IS '剔除日期';
COMMENT ON COLUMN "tushare_norm_index_member_all"."is_new" IS '是否最新Y是N否';

CREATE TABLE IF NOT EXISTS "tushare_norm_index_weight" (
    _record_hash CHAR(64) PRIMARY KEY,
    _request_hash CHAR(64) NOT NULL,
    _source_doc_id INTEGER,
    _source_collected_at TIMESTAMPTZ NOT NULL,
    _first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _schema_version INTEGER NOT NULL DEFAULT 1,
    _extra_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    "index_code" TEXT,
    "con_code" TEXT,
    "trade_date" DATE,
    "weight" NUMERIC
);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_index_weight_source" ON "tushare_norm_index_weight" (_source_collected_at DESC);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_index_weight_date" ON "tushare_norm_index_weight" ("trade_date" DESC);
COMMENT ON TABLE "tushare_norm_index_weight" IS '指数成分和权重；契约驱动标准化表' ;
COMMENT ON COLUMN "tushare_norm_index_weight"."index_code" IS '指数代码';
COMMENT ON COLUMN "tushare_norm_index_weight"."con_code" IS '成分代码';
COMMENT ON COLUMN "tushare_norm_index_weight"."trade_date" IS '交易日期';
COMMENT ON COLUMN "tushare_norm_index_weight"."weight" IS '权重';

CREATE TABLE IF NOT EXISTS "tushare_norm_libor" (
    _record_hash CHAR(64) PRIMARY KEY,
    _request_hash CHAR(64) NOT NULL,
    _source_doc_id INTEGER,
    _source_collected_at TIMESTAMPTZ NOT NULL,
    _first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _schema_version INTEGER NOT NULL DEFAULT 1,
    _extra_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    "date" DATE,
    "curr_type" TEXT,
    "on" NUMERIC,
    "1w" NUMERIC,
    "1m" NUMERIC,
    "2m" NUMERIC,
    "3m" NUMERIC,
    "6m" NUMERIC,
    "12m" NUMERIC
);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_libor_source" ON "tushare_norm_libor" (_source_collected_at DESC);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_libor_date" ON "tushare_norm_libor" ("date" DESC);
COMMENT ON TABLE "tushare_norm_libor" IS 'Libor拆借利率；契约驱动标准化表' ;
COMMENT ON COLUMN "tushare_norm_libor"."date" IS '日期';
COMMENT ON COLUMN "tushare_norm_libor"."curr_type" IS '货币';
COMMENT ON COLUMN "tushare_norm_libor"."on" IS '隔夜';
COMMENT ON COLUMN "tushare_norm_libor"."1w" IS '1周';
COMMENT ON COLUMN "tushare_norm_libor"."1m" IS '1个月';
COMMENT ON COLUMN "tushare_norm_libor"."2m" IS '2个月';
COMMENT ON COLUMN "tushare_norm_libor"."3m" IS '3个月';
COMMENT ON COLUMN "tushare_norm_libor"."6m" IS '6个月';
COMMENT ON COLUMN "tushare_norm_libor"."12m" IS '12个月';

CREATE TABLE IF NOT EXISTS "tushare_norm_limit_list_ths" (
    _record_hash CHAR(64) PRIMARY KEY,
    _request_hash CHAR(64) NOT NULL,
    _source_doc_id INTEGER,
    _source_collected_at TIMESTAMPTZ NOT NULL,
    _first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _schema_version INTEGER NOT NULL DEFAULT 1,
    _extra_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    "trade_date" DATE,
    "ts_code" TEXT,
    "name" TEXT,
    "price" NUMERIC,
    "pct_chg" NUMERIC,
    "open_num" BIGINT,
    "lu_desc" TEXT,
    "limit_type" TEXT,
    "tag" TEXT,
    "status" TEXT,
    "first_lu_time" TEXT,
    "last_lu_time" TEXT,
    "first_ld_time" TEXT,
    "last_ld_time" TEXT,
    "limit_order" NUMERIC,
    "limit_amount" NUMERIC,
    "turnover_rate" NUMERIC,
    "free_float" NUMERIC,
    "lu_limit_order" NUMERIC,
    "limit_up_suc_rate" NUMERIC,
    "turnover" NUMERIC,
    "rise_rate" NUMERIC,
    "sum_float" NUMERIC,
    "market_type" TEXT
);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_limit_list_ths_source" ON "tushare_norm_limit_list_ths" (_source_collected_at DESC);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_limit_list_ths_date" ON "tushare_norm_limit_list_ths" ("trade_date" DESC);
COMMENT ON TABLE "tushare_norm_limit_list_ths" IS '涨跌停榜单（同花顺）；契约驱动标准化表' ;
COMMENT ON COLUMN "tushare_norm_limit_list_ths"."trade_date" IS '交易日期';
COMMENT ON COLUMN "tushare_norm_limit_list_ths"."ts_code" IS '股票代码';
COMMENT ON COLUMN "tushare_norm_limit_list_ths"."name" IS '股票名称';
COMMENT ON COLUMN "tushare_norm_limit_list_ths"."price" IS '收盘价(元)';
COMMENT ON COLUMN "tushare_norm_limit_list_ths"."pct_chg" IS '涨跌幅%';
COMMENT ON COLUMN "tushare_norm_limit_list_ths"."open_num" IS '打开次数';
COMMENT ON COLUMN "tushare_norm_limit_list_ths"."lu_desc" IS '涨停原因';
COMMENT ON COLUMN "tushare_norm_limit_list_ths"."limit_type" IS '板单类别';
COMMENT ON COLUMN "tushare_norm_limit_list_ths"."tag" IS '涨停标签';
COMMENT ON COLUMN "tushare_norm_limit_list_ths"."status" IS '涨停状态（N连板、一字板）';
COMMENT ON COLUMN "tushare_norm_limit_list_ths"."first_lu_time" IS '首次涨停时间';
COMMENT ON COLUMN "tushare_norm_limit_list_ths"."last_lu_time" IS '最后涨停时间';
COMMENT ON COLUMN "tushare_norm_limit_list_ths"."first_ld_time" IS '首次跌停时间';
COMMENT ON COLUMN "tushare_norm_limit_list_ths"."last_ld_time" IS '最后跌停时间';
COMMENT ON COLUMN "tushare_norm_limit_list_ths"."limit_order" IS '封单量(元';
COMMENT ON COLUMN "tushare_norm_limit_list_ths"."limit_amount" IS '封单额(元';
COMMENT ON COLUMN "tushare_norm_limit_list_ths"."turnover_rate" IS '换手率%';
COMMENT ON COLUMN "tushare_norm_limit_list_ths"."free_float" IS '实际流通(元';
COMMENT ON COLUMN "tushare_norm_limit_list_ths"."lu_limit_order" IS '最大封单(元';
COMMENT ON COLUMN "tushare_norm_limit_list_ths"."limit_up_suc_rate" IS '近一年涨停封板率';
COMMENT ON COLUMN "tushare_norm_limit_list_ths"."turnover" IS '成交额';
COMMENT ON COLUMN "tushare_norm_limit_list_ths"."rise_rate" IS '涨速';
COMMENT ON COLUMN "tushare_norm_limit_list_ths"."sum_float" IS '总市值（亿元）';
COMMENT ON COLUMN "tushare_norm_limit_list_ths"."market_type" IS '股票类型：HS沪深主板、GEM创业板、STAR科创板';

CREATE TABLE IF NOT EXISTS "tushare_norm_major_news" (
    _record_hash CHAR(64) PRIMARY KEY,
    _request_hash CHAR(64) NOT NULL,
    _source_doc_id INTEGER,
    _source_collected_at TIMESTAMPTZ NOT NULL,
    _first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _schema_version INTEGER NOT NULL DEFAULT 1,
    _extra_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    "title" TEXT,
    "content" TEXT,
    "pub_time" TIMESTAMP WITHOUT TIME ZONE,
    "src" TEXT
);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_major_news_source" ON "tushare_norm_major_news" (_source_collected_at DESC);
COMMENT ON TABLE "tushare_norm_major_news" IS '新闻通讯；契约驱动标准化表' ;
COMMENT ON COLUMN "tushare_norm_major_news"."title" IS '标题';
COMMENT ON COLUMN "tushare_norm_major_news"."content" IS '内容 (默认不显示，需要在fields里指定)';
COMMENT ON COLUMN "tushare_norm_major_news"."pub_time" IS '发布时间';
COMMENT ON COLUMN "tushare_norm_major_news"."src" IS '来源网站';

CREATE TABLE IF NOT EXISTS "tushare_norm_mkt_idx_bmk" (
    _record_hash CHAR(64) PRIMARY KEY,
    _request_hash CHAR(64) NOT NULL,
    _source_doc_id INTEGER,
    _source_collected_at TIMESTAMPTZ NOT NULL,
    _first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _schema_version INTEGER NOT NULL DEFAULT 1,
    _extra_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    "ts_code" TEXT,
    "symbol" TEXT,
    "name" TEXT,
    "fullname" TEXT,
    "bmk_level" TEXT,
    "bmk_type" TEXT,
    "bmk_src" TEXT,
    "idx_type" TEXT
);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_mkt_idx_bmk_source" ON "tushare_norm_mkt_idx_bmk" (_source_collected_at DESC);
COMMENT ON TABLE "tushare_norm_mkt_idx_bmk" IS '公募基金业绩基准库；契约驱动标准化表' ;
COMMENT ON COLUMN "tushare_norm_mkt_idx_bmk"."ts_code" IS 'TS代码';
COMMENT ON COLUMN "tushare_norm_mkt_idx_bmk"."symbol" IS '代码';
COMMENT ON COLUMN "tushare_norm_mkt_idx_bmk"."name" IS '指数简称';
COMMENT ON COLUMN "tushare_norm_mkt_idx_bmk"."fullname" IS '指数名称';
COMMENT ON COLUMN "tushare_norm_mkt_idx_bmk"."bmk_level" IS '基准库分层 一类库、二类库';
COMMENT ON COLUMN "tushare_norm_mkt_idx_bmk"."bmk_type" IS '基准类型 策略、宽基、行业主题';
COMMENT ON COLUMN "tushare_norm_mkt_idx_bmk"."bmk_src" IS '指数编制机构';
COMMENT ON COLUMN "tushare_norm_mkt_idx_bmk"."idx_type" IS '指数类型 策略类指数；规模类指数；主题类指数；综合类指数；行业类指数；风格类指数';

CREATE TABLE IF NOT EXISTS "tushare_norm_opt_basic" (
    _record_hash CHAR(64) PRIMARY KEY,
    _request_hash CHAR(64) NOT NULL,
    _source_doc_id INTEGER,
    _source_collected_at TIMESTAMPTZ NOT NULL,
    _first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _schema_version INTEGER NOT NULL DEFAULT 1,
    _extra_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    "ts_code" TEXT,
    "symbol" TEXT,
    "exchange" TEXT,
    "name" TEXT,
    "per_unit" TEXT,
    "opt_code" TEXT,
    "opt_type" TEXT,
    "call_put" TEXT,
    "exercise_type" TEXT,
    "exercise_price" NUMERIC,
    "opt_multiplier" NUMERIC,
    "s_month" TEXT,
    "maturity_date" DATE,
    "list_price" NUMERIC,
    "list_date" DATE,
    "delist_date" DATE,
    "last_edate" TEXT,
    "last_ddate" TEXT,
    "quote_unit" TEXT,
    "min_price_chg" TEXT
);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_opt_basic_source" ON "tushare_norm_opt_basic" (_source_collected_at DESC);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_opt_basic_date" ON "tushare_norm_opt_basic" ("delist_date" DESC);
COMMENT ON TABLE "tushare_norm_opt_basic" IS '期权合约信息；契约驱动标准化表' ;
COMMENT ON COLUMN "tushare_norm_opt_basic"."ts_code" IS 'TS代码';
COMMENT ON COLUMN "tushare_norm_opt_basic"."symbol" IS '交易代码';
COMMENT ON COLUMN "tushare_norm_opt_basic"."exchange" IS '交易市场';
COMMENT ON COLUMN "tushare_norm_opt_basic"."name" IS '合约名称';
COMMENT ON COLUMN "tushare_norm_opt_basic"."per_unit" IS '合约单位';
COMMENT ON COLUMN "tushare_norm_opt_basic"."opt_code" IS '标的合约代码';
COMMENT ON COLUMN "tushare_norm_opt_basic"."opt_type" IS '合约类型';
COMMENT ON COLUMN "tushare_norm_opt_basic"."call_put" IS '期权类型';
COMMENT ON COLUMN "tushare_norm_opt_basic"."exercise_type" IS '行权方式';
COMMENT ON COLUMN "tushare_norm_opt_basic"."exercise_price" IS '行权价格，经过除权除息调整';
COMMENT ON COLUMN "tushare_norm_opt_basic"."opt_multiplier" IS '合约单位，经过除权除息调整';
COMMENT ON COLUMN "tushare_norm_opt_basic"."s_month" IS '结算月';
COMMENT ON COLUMN "tushare_norm_opt_basic"."maturity_date" IS '到期日';
COMMENT ON COLUMN "tushare_norm_opt_basic"."list_price" IS '挂牌基准价';
COMMENT ON COLUMN "tushare_norm_opt_basic"."list_date" IS '开始交易日期';
COMMENT ON COLUMN "tushare_norm_opt_basic"."delist_date" IS '最后交易日期';
COMMENT ON COLUMN "tushare_norm_opt_basic"."last_edate" IS '最后行权日期';
COMMENT ON COLUMN "tushare_norm_opt_basic"."last_ddate" IS '最后交割日期';
COMMENT ON COLUMN "tushare_norm_opt_basic"."quote_unit" IS '报价单位';
COMMENT ON COLUMN "tushare_norm_opt_basic"."min_price_chg" IS '最小价格波幅';

CREATE TABLE IF NOT EXISTS "tushare_norm_opt_daily" (
    _record_hash CHAR(64) PRIMARY KEY,
    _request_hash CHAR(64) NOT NULL,
    _source_doc_id INTEGER,
    _source_collected_at TIMESTAMPTZ NOT NULL,
    _first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _schema_version INTEGER NOT NULL DEFAULT 1,
    _extra_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    "ts_code" TEXT,
    "trade_date" DATE,
    "exchange" TEXT,
    "pre_settle" NUMERIC,
    "pre_close" NUMERIC,
    "open" NUMERIC,
    "high" NUMERIC,
    "low" NUMERIC,
    "close" NUMERIC,
    "settle" NUMERIC,
    "vol" NUMERIC,
    "amount" NUMERIC,
    "oi" NUMERIC
);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_opt_daily_source" ON "tushare_norm_opt_daily" (_source_collected_at DESC);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_opt_daily_date" ON "tushare_norm_opt_daily" ("trade_date" DESC);
COMMENT ON TABLE "tushare_norm_opt_daily" IS '期权日线行情；契约驱动标准化表' ;
COMMENT ON COLUMN "tushare_norm_opt_daily"."ts_code" IS 'TS代码';
COMMENT ON COLUMN "tushare_norm_opt_daily"."trade_date" IS '交易日期';
COMMENT ON COLUMN "tushare_norm_opt_daily"."exchange" IS '交易市场';
COMMENT ON COLUMN "tushare_norm_opt_daily"."pre_settle" IS '昨结算价';
COMMENT ON COLUMN "tushare_norm_opt_daily"."pre_close" IS '前收盘价';
COMMENT ON COLUMN "tushare_norm_opt_daily"."open" IS '开盘价';
COMMENT ON COLUMN "tushare_norm_opt_daily"."high" IS '最高价';
COMMENT ON COLUMN "tushare_norm_opt_daily"."low" IS '最低价';
COMMENT ON COLUMN "tushare_norm_opt_daily"."close" IS '收盘价';
COMMENT ON COLUMN "tushare_norm_opt_daily"."settle" IS '结算价';
COMMENT ON COLUMN "tushare_norm_opt_daily"."vol" IS '成交量(手)';
COMMENT ON COLUMN "tushare_norm_opt_daily"."amount" IS '成交金额(万元)';
COMMENT ON COLUMN "tushare_norm_opt_daily"."oi" IS '持仓量(手)';

CREATE TABLE IF NOT EXISTS "tushare_norm_p_get" (
    _record_hash CHAR(64) PRIMARY KEY,
    _request_hash CHAR(64) NOT NULL,
    _source_doc_id INTEGER,
    _source_collected_at TIMESTAMPTZ NOT NULL,
    _first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _schema_version INTEGER NOT NULL DEFAULT 1,
    _extra_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    "id" BIGINT,
    "ts_code" TEXT,
    "ts_type" TEXT,
    "name" TEXT,
    "desc" TEXT,
    "weight" NUMERIC,
    "create_time" TIMESTAMP WITHOUT TIME ZONE,
    "update_time" TIMESTAMP WITHOUT TIME ZONE
);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_p_get_source" ON "tushare_norm_p_get" (_source_collected_at DESC);
COMMENT ON TABLE "tushare_norm_p_get" IS '自选股组合查询；契约驱动标准化表' ;
COMMENT ON COLUMN "tushare_norm_p_get"."id" IS '编号';
COMMENT ON COLUMN "tushare_norm_p_get"."ts_code" IS '成分代码';
COMMENT ON COLUMN "tushare_norm_p_get"."ts_type" IS '成份类型（用户自定义类型，比如按行业、按概念板块或其他）';
COMMENT ON COLUMN "tushare_norm_p_get"."name" IS '名称';
COMMENT ON COLUMN "tushare_norm_p_get"."desc" IS '描述';
COMMENT ON COLUMN "tushare_norm_p_get"."weight" IS '权重';
COMMENT ON COLUMN "tushare_norm_p_get"."create_time" IS '创建时间';
COMMENT ON COLUMN "tushare_norm_p_get"."update_time" IS '修改时间';

CREATE TABLE IF NOT EXISTS "tushare_norm_p_list" (
    _record_hash CHAR(64) PRIMARY KEY,
    _request_hash CHAR(64) NOT NULL,
    _source_doc_id INTEGER,
    _source_collected_at TIMESTAMPTZ NOT NULL,
    _first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _schema_version INTEGER NOT NULL DEFAULT 1,
    _extra_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    "id" BIGINT,
    "name" TEXT,
    "desc" TEXT,
    "create_time" TIMESTAMP WITHOUT TIME ZONE,
    "update_time" TIMESTAMP WITHOUT TIME ZONE
);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_p_list_source" ON "tushare_norm_p_list" (_source_collected_at DESC);
COMMENT ON TABLE "tushare_norm_p_list" IS '自选股组合查询；契约驱动标准化表' ;
COMMENT ON COLUMN "tushare_norm_p_list"."id" IS '主键';
COMMENT ON COLUMN "tushare_norm_p_list"."name" IS '名称';
COMMENT ON COLUMN "tushare_norm_p_list"."desc" IS '描述';
COMMENT ON COLUMN "tushare_norm_p_list"."create_time" IS '创建时间';
COMMENT ON COLUMN "tushare_norm_p_list"."update_time" IS '修改时间';

CREATE TABLE IF NOT EXISTS "tushare_norm_repo_daily" (
    _record_hash CHAR(64) PRIMARY KEY,
    _request_hash CHAR(64) NOT NULL,
    _source_doc_id INTEGER,
    _source_collected_at TIMESTAMPTZ NOT NULL,
    _first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _schema_version INTEGER NOT NULL DEFAULT 1,
    _extra_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    "ts_code" TEXT,
    "trade_date" DATE,
    "repo_maturity" TEXT,
    "pre_close" NUMERIC,
    "open" NUMERIC,
    "high" NUMERIC,
    "low" NUMERIC,
    "close" NUMERIC,
    "weight" NUMERIC,
    "weight_r" NUMERIC,
    "amount" NUMERIC,
    "num" BIGINT
);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_repo_daily_source" ON "tushare_norm_repo_daily" (_source_collected_at DESC);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_repo_daily_date" ON "tushare_norm_repo_daily" ("trade_date" DESC);
COMMENT ON TABLE "tushare_norm_repo_daily" IS '债券回购日行情；契约驱动标准化表' ;
COMMENT ON COLUMN "tushare_norm_repo_daily"."ts_code" IS 'TS代码';
COMMENT ON COLUMN "tushare_norm_repo_daily"."trade_date" IS '交易日期';
COMMENT ON COLUMN "tushare_norm_repo_daily"."repo_maturity" IS '期限品种';
COMMENT ON COLUMN "tushare_norm_repo_daily"."pre_close" IS '前收盘(%)';
COMMENT ON COLUMN "tushare_norm_repo_daily"."open" IS '开盘价(%)';
COMMENT ON COLUMN "tushare_norm_repo_daily"."high" IS '最高价(%)';
COMMENT ON COLUMN "tushare_norm_repo_daily"."low" IS '最低价(%)';
COMMENT ON COLUMN "tushare_norm_repo_daily"."close" IS '收盘价(%)';
COMMENT ON COLUMN "tushare_norm_repo_daily"."weight" IS '加权价(%)';
COMMENT ON COLUMN "tushare_norm_repo_daily"."weight_r" IS '加权价(利率债)(%)';
COMMENT ON COLUMN "tushare_norm_repo_daily"."amount" IS '成交金额(万元)';
COMMENT ON COLUMN "tushare_norm_repo_daily"."num" IS '成交笔数(笔)';

CREATE TABLE IF NOT EXISTS "tushare_norm_sf_month" (
    _record_hash CHAR(64) PRIMARY KEY,
    _request_hash CHAR(64) NOT NULL,
    _source_doc_id INTEGER,
    _source_collected_at TIMESTAMPTZ NOT NULL,
    _first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _schema_version INTEGER NOT NULL DEFAULT 1,
    _extra_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    "month" TEXT,
    "inc_month" NUMERIC,
    "inc_cumval" NUMERIC,
    "stk_endval" NUMERIC
);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_sf_month_source" ON "tushare_norm_sf_month" (_source_collected_at DESC);
COMMENT ON TABLE "tushare_norm_sf_month" IS '社融数据（月度）；契约驱动标准化表' ;
COMMENT ON COLUMN "tushare_norm_sf_month"."month" IS '月度';
COMMENT ON COLUMN "tushare_norm_sf_month"."inc_month" IS '社融增量当月值（亿元）';
COMMENT ON COLUMN "tushare_norm_sf_month"."inc_cumval" IS '社融增量累计值（亿元）';
COMMENT ON COLUMN "tushare_norm_sf_month"."stk_endval" IS '社融存量期末值（万亿元）';

CREATE TABLE IF NOT EXISTS "tushare_norm_shibor" (
    _record_hash CHAR(64) PRIMARY KEY,
    _request_hash CHAR(64) NOT NULL,
    _source_doc_id INTEGER,
    _source_collected_at TIMESTAMPTZ NOT NULL,
    _first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _schema_version INTEGER NOT NULL DEFAULT 1,
    _extra_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    "date" DATE,
    "on" NUMERIC,
    "1w" NUMERIC,
    "2w" NUMERIC,
    "1m" NUMERIC,
    "3m" NUMERIC,
    "6m" NUMERIC,
    "9m" NUMERIC,
    "1y" NUMERIC
);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_shibor_source" ON "tushare_norm_shibor" (_source_collected_at DESC);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_shibor_date" ON "tushare_norm_shibor" ("date" DESC);
COMMENT ON TABLE "tushare_norm_shibor" IS 'Shibor利率数据；契约驱动标准化表' ;
COMMENT ON COLUMN "tushare_norm_shibor"."date" IS '日期';
COMMENT ON COLUMN "tushare_norm_shibor"."on" IS '隔夜';
COMMENT ON COLUMN "tushare_norm_shibor"."1w" IS '1周';
COMMENT ON COLUMN "tushare_norm_shibor"."2w" IS '2周';
COMMENT ON COLUMN "tushare_norm_shibor"."1m" IS '1个月';
COMMENT ON COLUMN "tushare_norm_shibor"."3m" IS '3个月';
COMMENT ON COLUMN "tushare_norm_shibor"."6m" IS '6个月';
COMMENT ON COLUMN "tushare_norm_shibor"."9m" IS '9个月';
COMMENT ON COLUMN "tushare_norm_shibor"."1y" IS '1年';

CREATE TABLE IF NOT EXISTS "tushare_norm_shibor_lpr" (
    _record_hash CHAR(64) PRIMARY KEY,
    _request_hash CHAR(64) NOT NULL,
    _source_doc_id INTEGER,
    _source_collected_at TIMESTAMPTZ NOT NULL,
    _first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _schema_version INTEGER NOT NULL DEFAULT 1,
    _extra_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    "date" DATE,
    "1y" NUMERIC,
    "5y" NUMERIC
);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_shibor_lpr_source" ON "tushare_norm_shibor_lpr" (_source_collected_at DESC);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_shibor_lpr_date" ON "tushare_norm_shibor_lpr" ("date" DESC);
COMMENT ON TABLE "tushare_norm_shibor_lpr" IS 'LPR贷款基础利率；契约驱动标准化表' ;
COMMENT ON COLUMN "tushare_norm_shibor_lpr"."date" IS '日期';
COMMENT ON COLUMN "tushare_norm_shibor_lpr"."1y" IS '1年贷款利率';
COMMENT ON COLUMN "tushare_norm_shibor_lpr"."5y" IS '5年贷款利率';

CREATE TABLE IF NOT EXISTS "tushare_norm_shibor_quote" (
    _record_hash CHAR(64) PRIMARY KEY,
    _request_hash CHAR(64) NOT NULL,
    _source_doc_id INTEGER,
    _source_collected_at TIMESTAMPTZ NOT NULL,
    _first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _schema_version INTEGER NOT NULL DEFAULT 1,
    _extra_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    "date" DATE,
    "bank" TEXT,
    "on_b" NUMERIC,
    "on_a" NUMERIC,
    "1w_b" NUMERIC,
    "1w_a" NUMERIC,
    "2w_b" NUMERIC,
    "2w_a" NUMERIC,
    "1m_b" NUMERIC,
    "1m_a" NUMERIC,
    "3m_b" NUMERIC,
    "3m_a" NUMERIC,
    "6m_b" NUMERIC,
    "6m_a" NUMERIC,
    "9m_b" NUMERIC,
    "9m_a" NUMERIC,
    "1y_b" NUMERIC,
    "1y_a" NUMERIC
);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_shibor_quote_source" ON "tushare_norm_shibor_quote" (_source_collected_at DESC);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_shibor_quote_date" ON "tushare_norm_shibor_quote" ("date" DESC);
COMMENT ON TABLE "tushare_norm_shibor_quote" IS 'Shibor报价数据；契约驱动标准化表' ;
COMMENT ON COLUMN "tushare_norm_shibor_quote"."date" IS '日期';
COMMENT ON COLUMN "tushare_norm_shibor_quote"."bank" IS '报价银行';
COMMENT ON COLUMN "tushare_norm_shibor_quote"."on_b" IS '隔夜_Bid';
COMMENT ON COLUMN "tushare_norm_shibor_quote"."on_a" IS '隔夜_Ask';
COMMENT ON COLUMN "tushare_norm_shibor_quote"."1w_b" IS '1周_Bid';
COMMENT ON COLUMN "tushare_norm_shibor_quote"."1w_a" IS '1周_Ask';
COMMENT ON COLUMN "tushare_norm_shibor_quote"."2w_b" IS '2周_Bid';
COMMENT ON COLUMN "tushare_norm_shibor_quote"."2w_a" IS '2周_Ask';
COMMENT ON COLUMN "tushare_norm_shibor_quote"."1m_b" IS '1月_Bid';
COMMENT ON COLUMN "tushare_norm_shibor_quote"."1m_a" IS '1月_Ask';
COMMENT ON COLUMN "tushare_norm_shibor_quote"."3m_b" IS '3月_Bid';
COMMENT ON COLUMN "tushare_norm_shibor_quote"."3m_a" IS '3月_Ask';
COMMENT ON COLUMN "tushare_norm_shibor_quote"."6m_b" IS '6月_Bid';
COMMENT ON COLUMN "tushare_norm_shibor_quote"."6m_a" IS '6月_Ask';
COMMENT ON COLUMN "tushare_norm_shibor_quote"."9m_b" IS '9月_Bid';
COMMENT ON COLUMN "tushare_norm_shibor_quote"."9m_a" IS '9月_Ask';
COMMENT ON COLUMN "tushare_norm_shibor_quote"."1y_b" IS '1年_Bid';
COMMENT ON COLUMN "tushare_norm_shibor_quote"."1y_a" IS '1年_Ask';

CREATE TABLE IF NOT EXISTS "tushare_norm_slb_len_mm" (
    _record_hash CHAR(64) PRIMARY KEY,
    _request_hash CHAR(64) NOT NULL,
    _source_doc_id INTEGER,
    _source_collected_at TIMESTAMPTZ NOT NULL,
    _first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _schema_version INTEGER NOT NULL DEFAULT 1,
    _extra_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    "trade_date" DATE,
    "ts_code" TEXT,
    "name" TEXT,
    "ope_inv" NUMERIC,
    "lent_qnt" NUMERIC,
    "cls_inv" NUMERIC,
    "end_bal" NUMERIC
);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_slb_len_mm_source" ON "tushare_norm_slb_len_mm" (_source_collected_at DESC);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_slb_len_mm_date" ON "tushare_norm_slb_len_mm" ("trade_date" DESC);
COMMENT ON TABLE "tushare_norm_slb_len_mm" IS '做市借券交易汇总；契约驱动标准化表' ;
COMMENT ON COLUMN "tushare_norm_slb_len_mm"."trade_date" IS '交易日期（YYYYMMDD）';
COMMENT ON COLUMN "tushare_norm_slb_len_mm"."ts_code" IS '股票代码';
COMMENT ON COLUMN "tushare_norm_slb_len_mm"."name" IS '股票名称';
COMMENT ON COLUMN "tushare_norm_slb_len_mm"."ope_inv" IS '期初余量(万股)';
COMMENT ON COLUMN "tushare_norm_slb_len_mm"."lent_qnt" IS '融出数量(万股)';
COMMENT ON COLUMN "tushare_norm_slb_len_mm"."cls_inv" IS '期末余量(万股)';
COMMENT ON COLUMN "tushare_norm_slb_len_mm"."end_bal" IS '期末余额(万元)';

CREATE TABLE IF NOT EXISTS "tushare_norm_slb_sec" (
    _record_hash CHAR(64) PRIMARY KEY,
    _request_hash CHAR(64) NOT NULL,
    _source_doc_id INTEGER,
    _source_collected_at TIMESTAMPTZ NOT NULL,
    _first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _schema_version INTEGER NOT NULL DEFAULT 1,
    _extra_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    "trade_date" DATE,
    "ts_code" TEXT,
    "name" TEXT,
    "ope_inv" NUMERIC,
    "lent_qnt" NUMERIC,
    "cls_inv" NUMERIC,
    "end_bal" NUMERIC
);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_slb_sec_source" ON "tushare_norm_slb_sec" (_source_collected_at DESC);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_slb_sec_date" ON "tushare_norm_slb_sec" ("trade_date" DESC);
COMMENT ON TABLE "tushare_norm_slb_sec" IS '转融券交易汇总；契约驱动标准化表' ;
COMMENT ON COLUMN "tushare_norm_slb_sec"."trade_date" IS '交易日期（YYYYMMDD）';
COMMENT ON COLUMN "tushare_norm_slb_sec"."ts_code" IS '股票代码';
COMMENT ON COLUMN "tushare_norm_slb_sec"."name" IS '股票名称';
COMMENT ON COLUMN "tushare_norm_slb_sec"."ope_inv" IS '期初余量(万股)';
COMMENT ON COLUMN "tushare_norm_slb_sec"."lent_qnt" IS '转融券融出数量(万股)';
COMMENT ON COLUMN "tushare_norm_slb_sec"."cls_inv" IS '期末余量(万股)';
COMMENT ON COLUMN "tushare_norm_slb_sec"."end_bal" IS '期末余额(万元)';

CREATE TABLE IF NOT EXISTS "tushare_norm_slb_sec_detail" (
    _record_hash CHAR(64) PRIMARY KEY,
    _request_hash CHAR(64) NOT NULL,
    _source_doc_id INTEGER,
    _source_collected_at TIMESTAMPTZ NOT NULL,
    _first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _schema_version INTEGER NOT NULL DEFAULT 1,
    _extra_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    "trade_date" DATE,
    "ts_code" TEXT,
    "name" TEXT,
    "tenor" TEXT,
    "fee_rate" NUMERIC,
    "lent_qnt" NUMERIC
);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_slb_sec_detail_source" ON "tushare_norm_slb_sec_detail" (_source_collected_at DESC);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_slb_sec_detail_date" ON "tushare_norm_slb_sec_detail" ("trade_date" DESC);
COMMENT ON TABLE "tushare_norm_slb_sec_detail" IS '转融券交易明细；契约驱动标准化表' ;
COMMENT ON COLUMN "tushare_norm_slb_sec_detail"."trade_date" IS '交易日期（YYYYMMDD）';
COMMENT ON COLUMN "tushare_norm_slb_sec_detail"."ts_code" IS '股票代码';
COMMENT ON COLUMN "tushare_norm_slb_sec_detail"."name" IS '股票名称';
COMMENT ON COLUMN "tushare_norm_slb_sec_detail"."tenor" IS '期 限(天)';
COMMENT ON COLUMN "tushare_norm_slb_sec_detail"."fee_rate" IS '融出费率(%)';
COMMENT ON COLUMN "tushare_norm_slb_sec_detail"."lent_qnt" IS '转融券融出数量(万股)';

CREATE TABLE IF NOT EXISTS "tushare_norm_stk_account" (
    _record_hash CHAR(64) PRIMARY KEY,
    _request_hash CHAR(64) NOT NULL,
    _source_doc_id INTEGER,
    _source_collected_at TIMESTAMPTZ NOT NULL,
    _first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _schema_version INTEGER NOT NULL DEFAULT 1,
    _extra_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    "date" DATE,
    "weekly_new" NUMERIC,
    "total" NUMERIC,
    "weekly_hold" NUMERIC,
    "weekly_trade" NUMERIC
);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_stk_account_source" ON "tushare_norm_stk_account" (_source_collected_at DESC);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_stk_account_date" ON "tushare_norm_stk_account" ("date" DESC);
COMMENT ON TABLE "tushare_norm_stk_account" IS '股票账户开户数据；契约驱动标准化表' ;
COMMENT ON COLUMN "tushare_norm_stk_account"."date" IS '统计周期';
COMMENT ON COLUMN "tushare_norm_stk_account"."weekly_new" IS '本周新增（万）';
COMMENT ON COLUMN "tushare_norm_stk_account"."total" IS '期末总账户数（万）';
COMMENT ON COLUMN "tushare_norm_stk_account"."weekly_hold" IS '本周持仓账户数（万）';
COMMENT ON COLUMN "tushare_norm_stk_account"."weekly_trade" IS '本周参与交易账户数（万）';

CREATE TABLE IF NOT EXISTS "tushare_norm_stk_factor" (
    _record_hash CHAR(64) PRIMARY KEY,
    _request_hash CHAR(64) NOT NULL,
    _source_doc_id INTEGER,
    _source_collected_at TIMESTAMPTZ NOT NULL,
    _first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _schema_version INTEGER NOT NULL DEFAULT 1,
    _extra_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    "ts_code" TEXT,
    "trade_date" DATE,
    "close" NUMERIC,
    "open" NUMERIC,
    "high" NUMERIC,
    "low" NUMERIC,
    "pre_close" NUMERIC,
    "change" NUMERIC,
    "pct_change" NUMERIC,
    "vol" NUMERIC,
    "amount" NUMERIC,
    "adj_factor" NUMERIC,
    "open_hfq" NUMERIC,
    "open_qfq" NUMERIC,
    "close_hfq" NUMERIC,
    "close_qfq" NUMERIC,
    "high_hfq" NUMERIC,
    "high_qfq" NUMERIC,
    "low_hfq" NUMERIC,
    "low_qfq" NUMERIC,
    "pre_close_hfq" NUMERIC,
    "pre_close_qfq" NUMERIC,
    "macd_dif" NUMERIC,
    "macd_dea" NUMERIC,
    "macd" NUMERIC,
    "kdj_k" NUMERIC,
    "kdj_d" NUMERIC,
    "kdj_j" NUMERIC,
    "rsi_6" NUMERIC,
    "rsi_12" NUMERIC,
    "rsi_24" NUMERIC,
    "boll_upper" NUMERIC,
    "boll_mid" NUMERIC,
    "boll_lower" NUMERIC,
    "cci" NUMERIC
);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_stk_factor_source" ON "tushare_norm_stk_factor" (_source_collected_at DESC);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_stk_factor_date" ON "tushare_norm_stk_factor" ("trade_date" DESC);
COMMENT ON TABLE "tushare_norm_stk_factor" IS '股票技术因子（量化因子）；契约驱动标准化表' ;
COMMENT ON COLUMN "tushare_norm_stk_factor"."ts_code" IS '股票代码';
COMMENT ON COLUMN "tushare_norm_stk_factor"."trade_date" IS '交易日期';
COMMENT ON COLUMN "tushare_norm_stk_factor"."close" IS '收盘价';
COMMENT ON COLUMN "tushare_norm_stk_factor"."open" IS '开盘价';
COMMENT ON COLUMN "tushare_norm_stk_factor"."high" IS '最高价';
COMMENT ON COLUMN "tushare_norm_stk_factor"."low" IS '最低价';
COMMENT ON COLUMN "tushare_norm_stk_factor"."pre_close" IS '昨收价';
COMMENT ON COLUMN "tushare_norm_stk_factor"."change" IS '涨跌额';
COMMENT ON COLUMN "tushare_norm_stk_factor"."pct_change" IS '涨跌幅';
COMMENT ON COLUMN "tushare_norm_stk_factor"."vol" IS '成交量 （手）';
COMMENT ON COLUMN "tushare_norm_stk_factor"."amount" IS '成交额 （千元）';
COMMENT ON COLUMN "tushare_norm_stk_factor"."adj_factor" IS '复权因子';
COMMENT ON COLUMN "tushare_norm_stk_factor"."open_hfq" IS '开盘价后复权';
COMMENT ON COLUMN "tushare_norm_stk_factor"."open_qfq" IS '开盘价前复权';
COMMENT ON COLUMN "tushare_norm_stk_factor"."close_hfq" IS '收盘价后复权';
COMMENT ON COLUMN "tushare_norm_stk_factor"."close_qfq" IS '收盘价前复权';
COMMENT ON COLUMN "tushare_norm_stk_factor"."high_hfq" IS '最高价后复权';
COMMENT ON COLUMN "tushare_norm_stk_factor"."high_qfq" IS '最高价前复权';
COMMENT ON COLUMN "tushare_norm_stk_factor"."low_hfq" IS '最低价后复权';
COMMENT ON COLUMN "tushare_norm_stk_factor"."low_qfq" IS '最低价前复权';
COMMENT ON COLUMN "tushare_norm_stk_factor"."pre_close_hfq" IS '昨收价后复权';
COMMENT ON COLUMN "tushare_norm_stk_factor"."pre_close_qfq" IS '昨收价前复权';
COMMENT ON COLUMN "tushare_norm_stk_factor"."macd_dif" IS 'MACD_DIF (基于前复权价格计算，下同)';
COMMENT ON COLUMN "tushare_norm_stk_factor"."macd_dea" IS 'MACD_DEA';
COMMENT ON COLUMN "tushare_norm_stk_factor"."macd" IS 'MACD';
COMMENT ON COLUMN "tushare_norm_stk_factor"."kdj_k" IS 'KDJ_K';
COMMENT ON COLUMN "tushare_norm_stk_factor"."kdj_d" IS 'KDJ_D';
COMMENT ON COLUMN "tushare_norm_stk_factor"."kdj_j" IS 'KDJ_J';
COMMENT ON COLUMN "tushare_norm_stk_factor"."rsi_6" IS 'RSI_6';
COMMENT ON COLUMN "tushare_norm_stk_factor"."rsi_12" IS 'RSI_12';
COMMENT ON COLUMN "tushare_norm_stk_factor"."rsi_24" IS 'RSI_24';
COMMENT ON COLUMN "tushare_norm_stk_factor"."boll_upper" IS 'BOLL_UPPER';
COMMENT ON COLUMN "tushare_norm_stk_factor"."boll_mid" IS 'BOLL_MID';
COMMENT ON COLUMN "tushare_norm_stk_factor"."boll_lower" IS 'BOLL_LOWER';
COMMENT ON COLUMN "tushare_norm_stk_factor"."cci" IS 'CCI';

CREATE TABLE IF NOT EXISTS "tushare_norm_stk_mins" (
    _record_hash CHAR(64) PRIMARY KEY,
    _request_hash CHAR(64) NOT NULL,
    _source_doc_id INTEGER,
    _source_collected_at TIMESTAMPTZ NOT NULL,
    _first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _schema_version INTEGER NOT NULL DEFAULT 1,
    _extra_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    "ts_code" TEXT,
    "trade_time" TIMESTAMP WITHOUT TIME ZONE,
    "open" NUMERIC,
    "close" NUMERIC,
    "high" NUMERIC,
    "low" NUMERIC,
    "vol" BIGINT,
    "amount" NUMERIC
);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_stk_mins_source" ON "tushare_norm_stk_mins" (_source_collected_at DESC);
COMMENT ON TABLE "tushare_norm_stk_mins" IS '股票历史分钟行情；契约驱动标准化表' ;
COMMENT ON COLUMN "tushare_norm_stk_mins"."ts_code" IS '股票代码';
COMMENT ON COLUMN "tushare_norm_stk_mins"."trade_time" IS '交易时间';
COMMENT ON COLUMN "tushare_norm_stk_mins"."open" IS '开盘价';
COMMENT ON COLUMN "tushare_norm_stk_mins"."close" IS '收盘价';
COMMENT ON COLUMN "tushare_norm_stk_mins"."high" IS '最高价';
COMMENT ON COLUMN "tushare_norm_stk_mins"."low" IS '最低价';
COMMENT ON COLUMN "tushare_norm_stk_mins"."vol" IS '成交量(股)';
COMMENT ON COLUMN "tushare_norm_stk_mins"."amount" IS '成交金额（元）';

CREATE TABLE IF NOT EXISTS "tushare_norm_stk_week_month_adj" (
    _record_hash CHAR(64) PRIMARY KEY,
    _request_hash CHAR(64) NOT NULL,
    _source_doc_id INTEGER,
    _source_collected_at TIMESTAMPTZ NOT NULL,
    _first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _schema_version INTEGER NOT NULL DEFAULT 1,
    _extra_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    "ts_code" TEXT,
    "trade_date" DATE,
    "end_date" DATE,
    "freq" TEXT,
    "open" NUMERIC,
    "high" NUMERIC,
    "low" NUMERIC,
    "close" NUMERIC,
    "pre_close" NUMERIC,
    "open_qfq" NUMERIC,
    "high_qfq" NUMERIC,
    "low_qfq" NUMERIC,
    "close_qfq" NUMERIC,
    "open_hfq" NUMERIC,
    "high_hfq" NUMERIC,
    "low_hfq" NUMERIC,
    "close_hfq" NUMERIC,
    "vol" NUMERIC,
    "amount" NUMERIC,
    "change" NUMERIC,
    "pct_chg" NUMERIC
);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_stk_week_month_adj_source" ON "tushare_norm_stk_week_month_adj" (_source_collected_at DESC);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_stk_week_month_adj_date" ON "tushare_norm_stk_week_month_adj" ("trade_date" DESC);
COMMENT ON TABLE "tushare_norm_stk_week_month_adj" IS '股票周/月线行情(复权--每日更新)；契约驱动标准化表' ;
COMMENT ON COLUMN "tushare_norm_stk_week_month_adj"."ts_code" IS '股票代码';
COMMENT ON COLUMN "tushare_norm_stk_week_month_adj"."trade_date" IS '交易日期（每周五或者月末日期）';
COMMENT ON COLUMN "tushare_norm_stk_week_month_adj"."end_date" IS '计算截至日期';
COMMENT ON COLUMN "tushare_norm_stk_week_month_adj"."freq" IS '频率(周week,月month)';
COMMENT ON COLUMN "tushare_norm_stk_week_month_adj"."open" IS '(周/月)开盘价';
COMMENT ON COLUMN "tushare_norm_stk_week_month_adj"."high" IS '(周/月)最高价';
COMMENT ON COLUMN "tushare_norm_stk_week_month_adj"."low" IS '(周/月)最低价';
COMMENT ON COLUMN "tushare_norm_stk_week_month_adj"."close" IS '(周/月)收盘价';
COMMENT ON COLUMN "tushare_norm_stk_week_month_adj"."pre_close" IS '上一(周/月)收盘价【除权价，前复权】';
COMMENT ON COLUMN "tushare_norm_stk_week_month_adj"."open_qfq" IS '前复权(周/月)开盘价';
COMMENT ON COLUMN "tushare_norm_stk_week_month_adj"."high_qfq" IS '前复权(周/月)最高价';
COMMENT ON COLUMN "tushare_norm_stk_week_month_adj"."low_qfq" IS '前复权(周/月)最低价';
COMMENT ON COLUMN "tushare_norm_stk_week_month_adj"."close_qfq" IS '前复权(周/月)收盘价';
COMMENT ON COLUMN "tushare_norm_stk_week_month_adj"."open_hfq" IS '后复权(周/月)开盘价';
COMMENT ON COLUMN "tushare_norm_stk_week_month_adj"."high_hfq" IS '后复权(周/月)最高价';
COMMENT ON COLUMN "tushare_norm_stk_week_month_adj"."low_hfq" IS '后复权(周/月)最低价';
COMMENT ON COLUMN "tushare_norm_stk_week_month_adj"."close_hfq" IS '后复权(周/月)收盘价';
COMMENT ON COLUMN "tushare_norm_stk_week_month_adj"."vol" IS '(周/月)成交量';
COMMENT ON COLUMN "tushare_norm_stk_week_month_adj"."amount" IS '(周/月)成交额';
COMMENT ON COLUMN "tushare_norm_stk_week_month_adj"."change" IS '(周/月)涨跌额';
COMMENT ON COLUMN "tushare_norm_stk_week_month_adj"."pct_chg" IS '(周/月)涨跌幅 【基于除权后的昨收计算的涨跌幅：（今收-除权昨收）/除权昨收 】';

CREATE TABLE IF NOT EXISTS "tushare_norm_sw_daily" (
    _record_hash CHAR(64) PRIMARY KEY,
    _request_hash CHAR(64) NOT NULL,
    _source_doc_id INTEGER,
    _source_collected_at TIMESTAMPTZ NOT NULL,
    _first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _schema_version INTEGER NOT NULL DEFAULT 1,
    _extra_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    "ts_code" TEXT,
    "trade_date" DATE,
    "name" TEXT,
    "open" NUMERIC,
    "low" NUMERIC,
    "high" NUMERIC,
    "close" NUMERIC,
    "change" NUMERIC,
    "pct_change" NUMERIC,
    "vol" NUMERIC,
    "amount" NUMERIC,
    "pe" NUMERIC,
    "pb" NUMERIC,
    "float_mv" NUMERIC,
    "total_mv" NUMERIC
);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_sw_daily_source" ON "tushare_norm_sw_daily" (_source_collected_at DESC);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_sw_daily_date" ON "tushare_norm_sw_daily" ("trade_date" DESC);
COMMENT ON TABLE "tushare_norm_sw_daily" IS '申万行业日线行情；契约驱动标准化表' ;
COMMENT ON COLUMN "tushare_norm_sw_daily"."ts_code" IS '指数代码';
COMMENT ON COLUMN "tushare_norm_sw_daily"."trade_date" IS '交易日期';
COMMENT ON COLUMN "tushare_norm_sw_daily"."name" IS '指数名称';
COMMENT ON COLUMN "tushare_norm_sw_daily"."open" IS '开盘点位';
COMMENT ON COLUMN "tushare_norm_sw_daily"."low" IS '最低点位';
COMMENT ON COLUMN "tushare_norm_sw_daily"."high" IS '最高点位';
COMMENT ON COLUMN "tushare_norm_sw_daily"."close" IS '收盘点位';
COMMENT ON COLUMN "tushare_norm_sw_daily"."change" IS '涨跌点位';
COMMENT ON COLUMN "tushare_norm_sw_daily"."pct_change" IS '涨跌幅';
COMMENT ON COLUMN "tushare_norm_sw_daily"."vol" IS '成交量（万股）';
COMMENT ON COLUMN "tushare_norm_sw_daily"."amount" IS '成交额（万元）';
COMMENT ON COLUMN "tushare_norm_sw_daily"."pe" IS '市盈率';
COMMENT ON COLUMN "tushare_norm_sw_daily"."pb" IS '市净率';
COMMENT ON COLUMN "tushare_norm_sw_daily"."float_mv" IS '流通市值（万元）';
COMMENT ON COLUMN "tushare_norm_sw_daily"."total_mv" IS '总市值（万元）';

CREATE TABLE IF NOT EXISTS "tushare_norm_sz_daily_info" (
    _record_hash CHAR(64) PRIMARY KEY,
    _request_hash CHAR(64) NOT NULL,
    _source_doc_id INTEGER,
    _source_collected_at TIMESTAMPTZ NOT NULL,
    _first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _schema_version INTEGER NOT NULL DEFAULT 1,
    _extra_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    "trade_date" DATE,
    "ts_code" TEXT,
    "count" BIGINT,
    "amount" NUMERIC,
    "vol" BIGINT,
    "total_share" NUMERIC,
    "total_mv" NUMERIC,
    "float_share" NUMERIC,
    "float_mv" NUMERIC
);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_sz_daily_info_source" ON "tushare_norm_sz_daily_info" (_source_collected_at DESC);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_sz_daily_info_date" ON "tushare_norm_sz_daily_info" ("trade_date" DESC);
COMMENT ON TABLE "tushare_norm_sz_daily_info" IS '深圳市场每日交易概况；契约驱动标准化表' ;
COMMENT ON COLUMN "tushare_norm_sz_daily_info"."ts_code" IS '市场类型';
COMMENT ON COLUMN "tushare_norm_sz_daily_info"."count" IS '股票个数';
COMMENT ON COLUMN "tushare_norm_sz_daily_info"."amount" IS '成交金额';
COMMENT ON COLUMN "tushare_norm_sz_daily_info"."vol" IS '成交量';
COMMENT ON COLUMN "tushare_norm_sz_daily_info"."total_share" IS '总股本';
COMMENT ON COLUMN "tushare_norm_sz_daily_info"."total_mv" IS '总市值';
COMMENT ON COLUMN "tushare_norm_sz_daily_info"."float_share" IS '流通股票';
COMMENT ON COLUMN "tushare_norm_sz_daily_info"."float_mv" IS '流通市值';

CREATE TABLE IF NOT EXISTS "tushare_norm_top10_cb_holders" (
    _record_hash CHAR(64) PRIMARY KEY,
    _request_hash CHAR(64) NOT NULL,
    _source_doc_id INTEGER,
    _source_collected_at TIMESTAMPTZ NOT NULL,
    _first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _schema_version INTEGER NOT NULL DEFAULT 1,
    _extra_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    "ts_code" TEXT,
    "end_date" DATE,
    "holder_rank" BIGINT,
    "holder_name" TEXT,
    "hold_amount" NUMERIC,
    "hold_ratio" NUMERIC
);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_top10_cb_holders_source" ON "tushare_norm_top10_cb_holders" (_source_collected_at DESC);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_top10_cb_holders_date" ON "tushare_norm_top10_cb_holders" ("end_date" DESC);
COMMENT ON TABLE "tushare_norm_top10_cb_holders" IS '可转债十大持有人；契约驱动标准化表' ;
COMMENT ON COLUMN "tushare_norm_top10_cb_holders"."ts_code" IS '转债代码';
COMMENT ON COLUMN "tushare_norm_top10_cb_holders"."end_date" IS '报告期';
COMMENT ON COLUMN "tushare_norm_top10_cb_holders"."holder_rank" IS '持有排名';
COMMENT ON COLUMN "tushare_norm_top10_cb_holders"."holder_name" IS '持有人名称';
COMMENT ON COLUMN "tushare_norm_top10_cb_holders"."hold_amount" IS '持有数量(万张)';
COMMENT ON COLUMN "tushare_norm_top10_cb_holders"."hold_ratio" IS '持有比例(%)';

CREATE TABLE IF NOT EXISTS "tushare_norm_us_basic" (
    _record_hash CHAR(64) PRIMARY KEY,
    _request_hash CHAR(64) NOT NULL,
    _source_doc_id INTEGER,
    _source_collected_at TIMESTAMPTZ NOT NULL,
    _first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _schema_version INTEGER NOT NULL DEFAULT 1,
    _extra_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    "ts_code" TEXT,
    "name" TEXT,
    "enname" TEXT,
    "classify" TEXT,
    "list_date" DATE,
    "delist_date" DATE
);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_us_basic_source" ON "tushare_norm_us_basic" (_source_collected_at DESC);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_us_basic_date" ON "tushare_norm_us_basic" ("delist_date" DESC);
COMMENT ON TABLE "tushare_norm_us_basic" IS '美股列表；契约驱动标准化表' ;
COMMENT ON COLUMN "tushare_norm_us_basic"."ts_code" IS '美股代码';
COMMENT ON COLUMN "tushare_norm_us_basic"."name" IS '中文名称';
COMMENT ON COLUMN "tushare_norm_us_basic"."enname" IS '英文名称';
COMMENT ON COLUMN "tushare_norm_us_basic"."classify" IS '分类:ADR-美国存托凭证；GDR-全球存托凭证；EQ-普通股；PF-优先股';
COMMENT ON COLUMN "tushare_norm_us_basic"."list_date" IS '上市日期';
COMMENT ON COLUMN "tushare_norm_us_basic"."delist_date" IS '退市日期';

CREATE TABLE IF NOT EXISTS "tushare_norm_us_tbr" (
    _record_hash CHAR(64) PRIMARY KEY,
    _request_hash CHAR(64) NOT NULL,
    _source_doc_id INTEGER,
    _source_collected_at TIMESTAMPTZ NOT NULL,
    _first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _schema_version INTEGER NOT NULL DEFAULT 1,
    _extra_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    "date" DATE,
    "w4_bd" NUMERIC,
    "w4_ce" NUMERIC,
    "w8_bd" NUMERIC,
    "w8_ce" NUMERIC,
    "w13_bd" NUMERIC,
    "w13_ce" NUMERIC,
    "w17_bd" NUMERIC,
    "w17_ce" NUMERIC,
    "w26_bd" NUMERIC,
    "w26_ce" NUMERIC,
    "w52_bd" NUMERIC,
    "w52_ce" NUMERIC
);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_us_tbr_source" ON "tushare_norm_us_tbr" (_source_collected_at DESC);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_us_tbr_date" ON "tushare_norm_us_tbr" ("date" DESC);
COMMENT ON TABLE "tushare_norm_us_tbr" IS '短期国债利率；契约驱动标准化表' ;
COMMENT ON COLUMN "tushare_norm_us_tbr"."date" IS '日期';
COMMENT ON COLUMN "tushare_norm_us_tbr"."w4_bd" IS '4周银行折现收益率';
COMMENT ON COLUMN "tushare_norm_us_tbr"."w4_ce" IS '4周票面利率';
COMMENT ON COLUMN "tushare_norm_us_tbr"."w8_bd" IS '8周银行折现收益率';
COMMENT ON COLUMN "tushare_norm_us_tbr"."w8_ce" IS '8周票面利率';
COMMENT ON COLUMN "tushare_norm_us_tbr"."w13_bd" IS '13周银行折现收益率';
COMMENT ON COLUMN "tushare_norm_us_tbr"."w13_ce" IS '13周票面利率';
COMMENT ON COLUMN "tushare_norm_us_tbr"."w17_bd" IS '17周银行折现收益率（数据从20221019开始）';
COMMENT ON COLUMN "tushare_norm_us_tbr"."w17_ce" IS '17周票面利率（数据从20221019开始）';
COMMENT ON COLUMN "tushare_norm_us_tbr"."w26_bd" IS '26周银行折现收益率';
COMMENT ON COLUMN "tushare_norm_us_tbr"."w26_ce" IS '26周票面利率';
COMMENT ON COLUMN "tushare_norm_us_tbr"."w52_bd" IS '52周银行折现收益率';
COMMENT ON COLUMN "tushare_norm_us_tbr"."w52_ce" IS '52周票面利率';

CREATE TABLE IF NOT EXISTS "tushare_norm_us_tltr" (
    _record_hash CHAR(64) PRIMARY KEY,
    _request_hash CHAR(64) NOT NULL,
    _source_doc_id INTEGER,
    _source_collected_at TIMESTAMPTZ NOT NULL,
    _first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _schema_version INTEGER NOT NULL DEFAULT 1,
    _extra_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    "date" DATE,
    "ltc" NUMERIC,
    "cmt" NUMERIC,
    "e_factor" NUMERIC
);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_us_tltr_source" ON "tushare_norm_us_tltr" (_source_collected_at DESC);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_us_tltr_date" ON "tushare_norm_us_tltr" ("date" DESC);
COMMENT ON TABLE "tushare_norm_us_tltr" IS '国债长期利率；契约驱动标准化表' ;
COMMENT ON COLUMN "tushare_norm_us_tltr"."date" IS '日期';
COMMENT ON COLUMN "tushare_norm_us_tltr"."ltc" IS '收益率 LT COMPOSITE (>10 Yrs)';
COMMENT ON COLUMN "tushare_norm_us_tltr"."cmt" IS '20年期CMT利率(TREASURY 20-Yr CMT)';
COMMENT ON COLUMN "tushare_norm_us_tltr"."e_factor" IS '外推因子EXTRAPOLATION FACTOR';

CREATE TABLE IF NOT EXISTS "tushare_norm_us_tradecal" (
    _record_hash CHAR(64) PRIMARY KEY,
    _request_hash CHAR(64) NOT NULL,
    _source_doc_id INTEGER,
    _source_collected_at TIMESTAMPTZ NOT NULL,
    _first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _schema_version INTEGER NOT NULL DEFAULT 1,
    _extra_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    "cal_date" DATE,
    "is_open" BIGINT,
    "pretrade_date" DATE
);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_us_tradecal_source" ON "tushare_norm_us_tradecal" (_source_collected_at DESC);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_us_tradecal_date" ON "tushare_norm_us_tradecal" ("cal_date" DESC);
COMMENT ON TABLE "tushare_norm_us_tradecal" IS '美股交易日历；契约驱动标准化表' ;
COMMENT ON COLUMN "tushare_norm_us_tradecal"."cal_date" IS '日历日期';
COMMENT ON COLUMN "tushare_norm_us_tradecal"."is_open" IS '是否交易 ''0''休市 ''1''交易';
COMMENT ON COLUMN "tushare_norm_us_tradecal"."pretrade_date" IS '上一个交易日';

CREATE TABLE IF NOT EXISTS "tushare_norm_us_trltr" (
    _record_hash CHAR(64) PRIMARY KEY,
    _request_hash CHAR(64) NOT NULL,
    _source_doc_id INTEGER,
    _source_collected_at TIMESTAMPTZ NOT NULL,
    _first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _schema_version INTEGER NOT NULL DEFAULT 1,
    _extra_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    "date" DATE,
    "ltr_avg" NUMERIC
);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_us_trltr_source" ON "tushare_norm_us_trltr" (_source_collected_at DESC);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_us_trltr_date" ON "tushare_norm_us_trltr" ("date" DESC);
COMMENT ON TABLE "tushare_norm_us_trltr" IS '国债实际长期利率平均值；契约驱动标准化表' ;
COMMENT ON COLUMN "tushare_norm_us_trltr"."date" IS '日期';
COMMENT ON COLUMN "tushare_norm_us_trltr"."ltr_avg" IS '实际平均利率LT Real Average (10> Yrs)';

CREATE TABLE IF NOT EXISTS "tushare_norm_us_trycr" (
    _record_hash CHAR(64) PRIMARY KEY,
    _request_hash CHAR(64) NOT NULL,
    _source_doc_id INTEGER,
    _source_collected_at TIMESTAMPTZ NOT NULL,
    _first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _schema_version INTEGER NOT NULL DEFAULT 1,
    _extra_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    "date" DATE,
    "y5" NUMERIC,
    "y7" NUMERIC,
    "y10" NUMERIC,
    "y20" NUMERIC,
    "y30" NUMERIC
);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_us_trycr_source" ON "tushare_norm_us_trycr" (_source_collected_at DESC);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_us_trycr_date" ON "tushare_norm_us_trycr" ("date" DESC);
COMMENT ON TABLE "tushare_norm_us_trycr" IS '国债实际收益率曲线利率；契约驱动标准化表' ;
COMMENT ON COLUMN "tushare_norm_us_trycr"."date" IS '日期';
COMMENT ON COLUMN "tushare_norm_us_trycr"."y5" IS '5年期';
COMMENT ON COLUMN "tushare_norm_us_trycr"."y7" IS '7年期';
COMMENT ON COLUMN "tushare_norm_us_trycr"."y10" IS '10年期';
COMMENT ON COLUMN "tushare_norm_us_trycr"."y20" IS '20年期';
COMMENT ON COLUMN "tushare_norm_us_trycr"."y30" IS '30年期';

CREATE TABLE IF NOT EXISTS "tushare_norm_us_tycr" (
    _record_hash CHAR(64) PRIMARY KEY,
    _request_hash CHAR(64) NOT NULL,
    _source_doc_id INTEGER,
    _source_collected_at TIMESTAMPTZ NOT NULL,
    _first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _schema_version INTEGER NOT NULL DEFAULT 1,
    _extra_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    "date" DATE,
    "m1" NUMERIC,
    "m2" NUMERIC,
    "m3" NUMERIC,
    "m4" NUMERIC,
    "m6" NUMERIC,
    "y1" NUMERIC,
    "y2" NUMERIC,
    "y3" NUMERIC,
    "y5" NUMERIC,
    "y7" NUMERIC,
    "y10" NUMERIC,
    "y20" NUMERIC,
    "y30" NUMERIC
);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_us_tycr_source" ON "tushare_norm_us_tycr" (_source_collected_at DESC);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_us_tycr_date" ON "tushare_norm_us_tycr" ("date" DESC);
COMMENT ON TABLE "tushare_norm_us_tycr" IS '国债收益率曲线利率（日频）；契约驱动标准化表' ;
COMMENT ON COLUMN "tushare_norm_us_tycr"."date" IS '日期';
COMMENT ON COLUMN "tushare_norm_us_tycr"."m1" IS '1月期';
COMMENT ON COLUMN "tushare_norm_us_tycr"."m2" IS '2月期';
COMMENT ON COLUMN "tushare_norm_us_tycr"."m3" IS '3月期';
COMMENT ON COLUMN "tushare_norm_us_tycr"."m4" IS '4月期（数据从20221019开始）';
COMMENT ON COLUMN "tushare_norm_us_tycr"."m6" IS '6月期';
COMMENT ON COLUMN "tushare_norm_us_tycr"."y1" IS '1年期';
COMMENT ON COLUMN "tushare_norm_us_tycr"."y2" IS '2年期';
COMMENT ON COLUMN "tushare_norm_us_tycr"."y3" IS '3年期';
COMMENT ON COLUMN "tushare_norm_us_tycr"."y5" IS '5年期';
COMMENT ON COLUMN "tushare_norm_us_tycr"."y7" IS '7年期';
COMMENT ON COLUMN "tushare_norm_us_tycr"."y10" IS '10年期';
COMMENT ON COLUMN "tushare_norm_us_tycr"."y20" IS '20年期';
COMMENT ON COLUMN "tushare_norm_us_tycr"."y30" IS '30年期';

CREATE TABLE IF NOT EXISTS "tushare_norm_wz_index" (
    _record_hash CHAR(64) PRIMARY KEY,
    _request_hash CHAR(64) NOT NULL,
    _source_doc_id INTEGER,
    _source_collected_at TIMESTAMPTZ NOT NULL,
    _first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _schema_version INTEGER NOT NULL DEFAULT 1,
    _extra_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    "date" DATE,
    "comp_rate" NUMERIC,
    "center_rate" NUMERIC,
    "micro_rate" NUMERIC,
    "cm_rate" NUMERIC,
    "sdb_rate" NUMERIC,
    "om_rate" NUMERIC,
    "aa_rate" NUMERIC,
    "m1_rate" NUMERIC,
    "m3_rate" NUMERIC,
    "m6_rate" NUMERIC,
    "m12_rate" NUMERIC,
    "long_rate" NUMERIC
);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_wz_index_source" ON "tushare_norm_wz_index" (_source_collected_at DESC);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_wz_index_date" ON "tushare_norm_wz_index" ("date" DESC);
COMMENT ON TABLE "tushare_norm_wz_index" IS '温州民间借贷利率；契约驱动标准化表' ;
COMMENT ON COLUMN "tushare_norm_wz_index"."date" IS '日期';
COMMENT ON COLUMN "tushare_norm_wz_index"."comp_rate" IS '温州民间融资综合利率指数 (%，下同)';
COMMENT ON COLUMN "tushare_norm_wz_index"."center_rate" IS '民间借贷服务中心利率';
COMMENT ON COLUMN "tushare_norm_wz_index"."micro_rate" IS '小额贷款公司放款利率';
COMMENT ON COLUMN "tushare_norm_wz_index"."cm_rate" IS '民间资本管理公司融资价格';
COMMENT ON COLUMN "tushare_norm_wz_index"."sdb_rate" IS '社会直接借贷利率';
COMMENT ON COLUMN "tushare_norm_wz_index"."om_rate" IS '其他市场主体利率';
COMMENT ON COLUMN "tushare_norm_wz_index"."aa_rate" IS '农村互助会互助金费率';
COMMENT ON COLUMN "tushare_norm_wz_index"."m1_rate" IS '温州地区民间借贷分期限利率（一月期）';
COMMENT ON COLUMN "tushare_norm_wz_index"."m3_rate" IS '温州地区民间借贷分期限利率（三月期）';
COMMENT ON COLUMN "tushare_norm_wz_index"."m6_rate" IS '温州地区民间借贷分期限利率（六月期）';
COMMENT ON COLUMN "tushare_norm_wz_index"."m12_rate" IS '温州地区民间借贷分期限利率（一年期）';
COMMENT ON COLUMN "tushare_norm_wz_index"."long_rate" IS '温州地区民间借贷分期限利率（长期）';
