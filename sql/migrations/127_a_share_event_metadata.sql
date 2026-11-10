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

CREATE TABLE IF NOT EXISTS "tushare_norm_stk_seasoned" (
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
    "first_ann_date" DATE,
    "proj_info_source" TEXT,
    "board_approval_dt" TEXT,
    "sh_approval_dt" TEXT,
    "sasac_approval_dt" TEXT,
    "csrc_approval_dt" TEXT,
    "fo_type" TEXT,
    "fo_stock_type" TEXT,
    "cur_stage" TEXT,
    "valid_st_dt" TEXT,
    "valid_end_dt" TEXT,
    "plan_chg_type" TEXT,
    "plan_chg_ann_dt" TEXT,
    "pricing_method" TEXT,
    "pricing_base_dt" TEXT,
    "price_basis" TEXT,
    "fo_vol_high" TEXT,
    "fo_vol_low" TEXT,
    "fo_price_high" NUMERIC,
    "fo_price_low" NUMERIC,
    "fo_price_ratio" NUMERIC,
    "fo_raise_total" NUMERIC,
    "fo_purpose" TEXT,
    "fo_investor" TEXT,
    "sub_method" TEXT,
    "fo_price_act" NUMERIC,
    "fo_vol_act" TEXT,
    "fo_raise_total_act" NUMERIC,
    "fo_raise_net_act" NUMERIC,
    "fo_exp_total" NUMERIC,
    "uw_fee" NUMERIC,
    "fo_exp_audit" NUMERIC,
    "fo_exp_legal" NUMERIC,
    "fo_exp_inst" NUMERIC,
    "fo_exp_pub" NUMERIC,
    "fo_exp_reg" NUMERIC,
    "fo_exp_other" NUMERIC,
    "fo_exp_per_share" NUMERIC,
    "issue_obj_type" TEXT,
    "pe_issue" NUMERIC,
    "pub_plac_qty" TEXT,
    "onl_pch_vol" TEXT,
    "onl_pch_num" TEXT,
    "onl_pch_excess" NUMERIC,
    "onl_winning_rate" NUMERIC,
    "inst_plac_qty" TEXT,
    "inst_sub_eff_total" TEXT,
    "inst_sub_eff_cnt" TEXT,
    "inst_oversub_times" NUMERIC,
    "a_inv_plac_qty" TEXT,
    "b_inv_plac_qty" TEXT,
    "old_sh_pre_plac_qty" TEXT,
    "old_sh_pre_plac_ratio" NUMERIC,
    "clw_between_inst_pub" TEXT,
    "prospectus_pub_dt" TEXT,
    "offer_intent_pub_dt" TEXT,
    "apply_date" DATE,
    "old_sh_pre_plac_dt" TEXT,
    "onl_issue_date" DATE,
    "uw_start_dt" TEXT,
    "uw_end_dt" TEXT,
    "uw_mode" TEXT,
    "new_share_list_dt" TEXT,
    "list_circ_qty" TEXT,
    "right_reg_dt" TEXT,
    "ex_right_dt" TEXT,
    "update_flag" TEXT
);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_stk_seasoned_source" ON "tushare_norm_stk_seasoned" (_source_collected_at DESC);
CREATE INDEX IF NOT EXISTS "idx_tushare_norm_stk_seasoned_date" ON "tushare_norm_stk_seasoned" ("ann_date" DESC);
COMMENT ON TABLE "tushare_norm_stk_seasoned" IS 'A股增发事件；契约驱动标准化表' ;
COMMENT ON COLUMN "tushare_norm_stk_seasoned"."ts_code" IS '股票代码';
COMMENT ON COLUMN "tushare_norm_stk_seasoned"."ann_date" IS '公告日期';
COMMENT ON COLUMN "tushare_norm_stk_seasoned"."first_ann_date" IS '首次发布公告日期';
COMMENT ON COLUMN "tushare_norm_stk_seasoned"."proj_info_source" IS '信息来源';
COMMENT ON COLUMN "tushare_norm_stk_seasoned"."board_approval_dt" IS '董事会审议通过并公告日期';
COMMENT ON COLUMN "tushare_norm_stk_seasoned"."sh_approval_dt" IS '股东大会决议公告日期';
COMMENT ON COLUMN "tushare_norm_stk_seasoned"."sasac_approval_dt" IS '国资委通过公告日';
COMMENT ON COLUMN "tushare_norm_stk_seasoned"."csrc_approval_dt" IS '证监会批准公告日';
COMMENT ON COLUMN "tushare_norm_stk_seasoned"."fo_type" IS '增发类别:公开;非公开';
COMMENT ON COLUMN "tushare_norm_stk_seasoned"."fo_stock_type" IS '增发A股类型';
COMMENT ON COLUMN "tushare_norm_stk_seasoned"."cur_stage" IS '进程:意向;董事会预案;监管审批;实施;终止';
COMMENT ON COLUMN "tushare_norm_stk_seasoned"."valid_st_dt" IS '预案有效期起始日期';
COMMENT ON COLUMN "tushare_norm_stk_seasoned"."valid_end_dt" IS '预案有效期截止日期';
COMMENT ON COLUMN "tushare_norm_stk_seasoned"."plan_chg_type" IS '方案变动类型 方案调整 增发变更 推迟 终止';
COMMENT ON COLUMN "tushare_norm_stk_seasoned"."plan_chg_ann_dt" IS '方案变动公告日期';
COMMENT ON COLUMN "tushare_norm_stk_seasoned"."pricing_method" IS '定价方式 估值定价 协商定价 市价参考 询价方式投 限价约束';
COMMENT ON COLUMN "tushare_norm_stk_seasoned"."pricing_base_dt" IS '定价基准日';
COMMENT ON COLUMN "tushare_norm_stk_seasoned"."price_basis" IS '价格制定依据';
COMMENT ON COLUMN "tushare_norm_stk_seasoned"."fo_vol_high" IS '预计发行量上限（股）';
COMMENT ON COLUMN "tushare_norm_stk_seasoned"."fo_vol_low" IS '预计发行量下限（股）';
COMMENT ON COLUMN "tushare_norm_stk_seasoned"."fo_price_high" IS '预计发行价上限（元）';
COMMENT ON COLUMN "tushare_norm_stk_seasoned"."fo_price_low" IS '预计发行价下限（元）';
COMMENT ON COLUMN "tushare_norm_stk_seasoned"."fo_price_ratio" IS '预计价格相对基准价格比例（%）';
COMMENT ON COLUMN "tushare_norm_stk_seasoned"."fo_raise_total" IS '预计募集资金总额（元）';
COMMENT ON COLUMN "tushare_norm_stk_seasoned"."fo_purpose" IS '增发目的';
COMMENT ON COLUMN "tushare_norm_stk_seasoned"."fo_investor" IS '预计发行对象';
COMMENT ON COLUMN "tushare_norm_stk_seasoned"."sub_method" IS '认购方式 纯现金 资产类 其他';
COMMENT ON COLUMN "tushare_norm_stk_seasoned"."fo_price_act" IS '发行价（元）';
COMMENT ON COLUMN "tushare_norm_stk_seasoned"."fo_vol_act" IS '发行量（股）';
COMMENT ON COLUMN "tushare_norm_stk_seasoned"."fo_raise_total_act" IS '募集资金总额（元）';
COMMENT ON COLUMN "tushare_norm_stk_seasoned"."fo_raise_net_act" IS '募集资金净额（元）';
COMMENT ON COLUMN "tushare_norm_stk_seasoned"."fo_exp_total" IS '发行费用总额（元）';
COMMENT ON COLUMN "tushare_norm_stk_seasoned"."uw_fee" IS '承销保荐费（元）';
COMMENT ON COLUMN "tushare_norm_stk_seasoned"."fo_exp_audit" IS '审计费（元）';
COMMENT ON COLUMN "tushare_norm_stk_seasoned"."fo_exp_legal" IS '律师费（元）';
COMMENT ON COLUMN "tushare_norm_stk_seasoned"."fo_exp_inst" IS '中介机构费（元）';
COMMENT ON COLUMN "tushare_norm_stk_seasoned"."fo_exp_pub" IS '上网发行费（元）';
COMMENT ON COLUMN "tushare_norm_stk_seasoned"."fo_exp_reg" IS '股票登记费（元）';
COMMENT ON COLUMN "tushare_norm_stk_seasoned"."fo_exp_other" IS '其他费用（元）';
COMMENT ON COLUMN "tushare_norm_stk_seasoned"."fo_exp_per_share" IS '每股发行费（元）';
COMMENT ON COLUMN "tushare_norm_stk_seasoned"."issue_obj_type" IS '发行对象类型 全体投资者 大股东及大股东关联方 机构投资者 自然人';
COMMENT ON COLUMN "tushare_norm_stk_seasoned"."pe_issue" IS '增发市盈率（按增发前总股本）';
COMMENT ON COLUMN "tushare_norm_stk_seasoned"."pub_plac_qty" IS '网上发行股数(股）';
COMMENT ON COLUMN "tushare_norm_stk_seasoned"."onl_pch_vol" IS '网上发行有效申购数量（股）';
COMMENT ON COLUMN "tushare_norm_stk_seasoned"."onl_pch_num" IS '网上发行有效申购户数（户）';
COMMENT ON COLUMN "tushare_norm_stk_seasoned"."onl_pch_excess" IS '网上发行超额认购倍数';
COMMENT ON COLUMN "tushare_norm_stk_seasoned"."onl_winning_rate" IS '网上发行中签率（%）';
COMMENT ON COLUMN "tushare_norm_stk_seasoned"."inst_plac_qty" IS '专业机构配售股数（股）';
COMMENT ON COLUMN "tushare_norm_stk_seasoned"."inst_sub_eff_total" IS '专业机构有效申购总量（股）';
COMMENT ON COLUMN "tushare_norm_stk_seasoned"."inst_sub_eff_cnt" IS '专业机构有效申购户数（户）';
COMMENT ON COLUMN "tushare_norm_stk_seasoned"."inst_oversub_times" IS '专业机构超额认购倍数（倍）';
COMMENT ON COLUMN "tushare_norm_stk_seasoned"."a_inv_plac_qty" IS 'A类投资者配售股数（股）';
COMMENT ON COLUMN "tushare_norm_stk_seasoned"."b_inv_plac_qty" IS 'B类投资者配售股数（股）';
COMMENT ON COLUMN "tushare_norm_stk_seasoned"."old_sh_pre_plac_qty" IS '老股东优先配售股数（股）';
COMMENT ON COLUMN "tushare_norm_stk_seasoned"."old_sh_pre_plac_ratio" IS '老股东优先配售比例 %';
COMMENT ON COLUMN "tushare_norm_stk_seasoned"."clw_between_inst_pub" IS '网上网下回拨股数(股)';
COMMENT ON COLUMN "tushare_norm_stk_seasoned"."prospectus_pub_dt" IS '募集说明书对外披露日期';
COMMENT ON COLUMN "tushare_norm_stk_seasoned"."offer_intent_pub_dt" IS '发行意向文件披露日期';
COMMENT ON COLUMN "tushare_norm_stk_seasoned"."apply_date" IS '申购日';
COMMENT ON COLUMN "tushare_norm_stk_seasoned"."old_sh_pre_plac_dt" IS '老股东优先配售日期';
COMMENT ON COLUMN "tushare_norm_stk_seasoned"."onl_issue_date" IS '网上发行日期';
COMMENT ON COLUMN "tushare_norm_stk_seasoned"."uw_start_dt" IS '承销期起始日';
COMMENT ON COLUMN "tushare_norm_stk_seasoned"."uw_end_dt" IS '承销期截止日';
COMMENT ON COLUMN "tushare_norm_stk_seasoned"."uw_mode" IS '承销方式 券商包销 非包销代销 上市公司自销';
COMMENT ON COLUMN "tushare_norm_stk_seasoned"."new_share_list_dt" IS '新增股份上市日期';
COMMENT ON COLUMN "tushare_norm_stk_seasoned"."list_circ_qty" IS '本次上市流通股数（股）';
COMMENT ON COLUMN "tushare_norm_stk_seasoned"."right_reg_dt" IS '股权登记日';
COMMENT ON COLUMN "tushare_norm_stk_seasoned"."ex_right_dt" IS '除权日';
COMMENT ON COLUMN "tushare_norm_stk_seasoned"."update_flag" IS '更新标识 默认为0 有更新时为1';

CREATE TABLE stock_announcements(
 _record_hash CHAR(64) PRIMARY KEY,
 source TEXT NOT NULL,
 announcement_id TEXT NOT NULL,
 ts_code VARCHAR(12) NOT NULL,
 ann_date DATE NOT NULL,
 published_at TIMESTAMPTZ NOT NULL,
 title TEXT NOT NULL,
 document_url TEXT NOT NULL,
 first_observed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 last_seen_at TIMESTAMPTZ NOT NULL DEFAULT now());
CREATE INDEX stock_announcements_symbol_date ON stock_announcements(ts_code,ann_date DESC);
CREATE INDEX stock_announcements_date ON stock_announcements(ann_date);
CREATE TABLE ant_scheduled_checkpoint(
 request_hash CHAR(64) PRIMARY KEY,
 route TEXT NOT NULL,
 period_key TEXT NOT NULL,
 result JSONB NOT NULL,
 observed_at TIMESTAMPTZ NOT NULL DEFAULT now());
CREATE INDEX ant_scheduled_checkpoint_time ON ant_scheduled_checkpoint(observed_at);
