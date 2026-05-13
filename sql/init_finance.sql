-- balancesheet: 上市公司资产负债表
-- 来源: Tushare balancesheet_vip（按季度取全市场）
-- 核心字段（保险/银行专用字段已省略）

CREATE TABLE IF NOT EXISTS balancesheet (
    ts_code                    VARCHAR(32) NOT NULL,
    end_date                   DATE        NOT NULL,
    report_type                INT         NOT NULL DEFAULT 1,
    comp_type                  INT,
    ann_date                   DATE,
    f_ann_date                 DATE,

    -- 资产
    money_cap                  NUMERIC(20, 4),     -- 货币资金
    trad_asset                 NUMERIC(20, 4),     -- 交易性金融资产
    notes_receiv               NUMERIC(20, 4),     -- 应收票据
    accounts_receiv            NUMERIC(20, 4),     -- 应收账款
    oth_receiv                 NUMERIC(20, 4),     -- 其他应收款
    prepayment                 NUMERIC(20, 4),     -- 预付款项
    inventories                NUMERIC(20, 4),     -- 存货
    total_cur_assets           NUMERIC(20, 4),     -- 流动资产合计
    lt_eqt_invest              NUMERIC(20, 4),     -- 长期股权投资
    invest_real_estate         NUMERIC(20, 4),     -- 投资性房地产
    fix_assets                 NUMERIC(20, 4),     -- 固定资产
    cip                        NUMERIC(20, 4),     -- 在建工程
    intan_assets               NUMERIC(20, 4),     -- 无形资产
    r_and_d                    NUMERIC(20, 4),     -- 研发支出
    goodwill                   NUMERIC(20, 4),     -- 商誉
    lt_amor_exp                NUMERIC(20, 4),     -- 长期待摊费用
    defer_tax_assets           NUMERIC(20, 4),     -- 递延所得税资产
    total_nca                  NUMERIC(20, 4),     -- 非流动资产合计
    total_assets               NUMERIC(20, 4),     -- 资产总计

    -- 负债
    st_borr                    NUMERIC(20, 4),     -- 短期借款
    notes_payable              NUMERIC(20, 4),     -- 应付票据
    acct_payable               NUMERIC(20, 4),     -- 应付账款
    adv_receipts               NUMERIC(20, 4),     -- 预收款项
    payroll_payable            NUMERIC(20, 4),     -- 应付职工薪酬
    taxes_payable              NUMERIC(20, 4),     -- 应交税费
    oth_payable                NUMERIC(20, 4),     -- 其他应付款
    total_cur_liab             NUMERIC(20, 4),     -- 流动负债合计
    lt_borr                    NUMERIC(20, 4),     -- 长期借款
    bond_payable               NUMERIC(20, 4),     -- 应付债券
    lt_payable                 NUMERIC(20, 4),     -- 长期应付款
    defer_tax_liab             NUMERIC(20, 4),     -- 递延所得税负债
    total_ncl                  NUMERIC(20, 4),     -- 非流动负债合计
    total_liab                 NUMERIC(20, 4),     -- 负债合计

    -- 权益
    total_hldr_eqy_inc_min_int NUMERIC(20, 4),     -- 股东权益合计(含少数)
    total_share                NUMERIC(20, 4),     -- 期末总股本
    cap_rese                   NUMERIC(20, 4),     -- 资本公积金
    undistr_porfit             NUMERIC(20, 4),     -- 未分配利润
    surplus_rese               NUMERIC(20, 4),     -- 盈余公积金
    treasury_share             NUMERIC(20, 4),     -- 库存股
    minority_int               NUMERIC(20, 4),     -- 少数股东权益
    update_flag                VARCHAR(4),

    created_at                 TIMESTAMP NOT NULL DEFAULT NOW(),
    PRIMARY KEY (ts_code, end_date, report_type)
);

CREATE INDEX IF NOT EXISTS idx_bs_end_date ON balancesheet (end_date);
CREATE INDEX IF NOT EXISTS idx_bs_ts_code ON balancesheet (ts_code);

-- cashflow: 现金流量表
CREATE TABLE IF NOT EXISTS cashflow (
    ts_code                    VARCHAR(32) NOT NULL,
    end_date                   DATE        NOT NULL,
    report_type                INT         NOT NULL DEFAULT 1,
    comp_type                  INT,
    ann_date                   DATE,
    f_ann_date                 DATE,

    -- 经营活动现金流
    c_fr_sale_sg               NUMERIC(20, 4),     -- 销售商品收到的现金
    c_inf_fr_operate_a         NUMERIC(20, 4),     -- 经营活动现金流入小计
    c_paid_goods_s             NUMERIC(20, 4),     -- 购买商品支付的现金
    c_paid_to_for_empl         NUMERIC(20, 4),     -- 支付给职工
    c_paid_for_taxes           NUMERIC(20, 4),     -- 支付的各项税费
    st_cash_out_act            NUMERIC(20, 4),     -- 经营活动现金流出小计
    n_cashflow_act             NUMERIC(20, 4),     -- 经营活动现金流量净额

    -- 投资活动现金流
    c_disp_withdrwl_invest     NUMERIC(20, 4),     -- 收回投资
    c_recp_return_invest       NUMERIC(20, 4),     -- 取得投资收益
    n_recp_disp_fiolta         NUMERIC(20, 4),     -- 处置固定资产
    stot_inflows_inv_act       NUMERIC(20, 4),     -- 投资活动现金流入
    c_pay_acq_const_fiolta     NUMERIC(20, 4),     -- 购建固定资产
    c_paid_invest              NUMERIC(20, 4),     -- 投资支付
    stot_out_inv_act           NUMERIC(20, 4),     -- 投资活动现金流出
    n_cashflow_inv_act         NUMERIC(20, 4),     -- 投资活动现金流量净额

    -- 筹资活动现金流
    c_recp_borrow              NUMERIC(20, 4),     -- 取得借款
    stot_cash_in_fnc_act       NUMERIC(20, 4),     -- 筹资活动现金流入
    c_prepay_amt_borr          NUMERIC(20, 4),     -- 偿还债务
    c_pay_dist_dpcp_int_exp    NUMERIC(20, 4),     -- 分配股利
    stot_cashout_fnc_act       NUMERIC(20, 4),     -- 筹资活动现金流出
    n_cash_flows_fnc_act       NUMERIC(20, 4),     -- 筹资活动现金流量净额

    free_cashflow              NUMERIC(20, 4),     -- 企业自由现金流
    n_incr_cash_cash_equ       NUMERIC(20, 4),     -- 现金净增加额
    c_cash_equ_beg_period      NUMERIC(20, 4),     -- 期初现金
    c_cash_equ_end_period      NUMERIC(20, 4),     -- 期末现金
    net_profit                 NUMERIC(20, 4),     -- 净利润
    financian_exp              NUMERIC(20, 4),     -- 财务费用
    depr_fa_coga_dpba          NUMERIC(20, 4),     -- 折旧与摊销
    oth_cash_pay_oper_act      NUMERIC(20, 4),     -- 支付其他经营相关
    update_flag                VARCHAR(4),

    created_at                 TIMESTAMP NOT NULL DEFAULT NOW(),
    PRIMARY KEY (ts_code, end_date, report_type)
);

CREATE INDEX IF NOT EXISTS idx_cf_end_date ON cashflow (end_date);
CREATE INDEX IF NOT EXISTS idx_cf_ts_code ON cashflow (ts_code);

-- forecast: 业绩预告
CREATE TABLE IF NOT EXISTS forecast (
    ts_code                    VARCHAR(32) NOT NULL,
    end_date                   DATE        NOT NULL,
    ann_date                   DATE        NOT NULL,
    type                       VARCHAR(16),         -- 预告类型
    p_change_min               NUMERIC(10, 2),      -- 净利润变动下限(%)
    p_change_max               NUMERIC(10, 2),      -- 净利润变动上限(%)
    net_profit_min             NUMERIC(20, 4),      -- 净利润下限(万元)
    net_profit_max             NUMERIC(20, 4),      -- 净利润上限(万元)
    last_parent_net            NUMERIC(20, 4),      -- 上年同期归母净利润
    first_ann_date             DATE,                -- 首次公告日
    summary                    TEXT,                -- 预告摘要
    change_reason              TEXT,                -- 变动原因

    created_at                 TIMESTAMP NOT NULL DEFAULT NOW(),
    PRIMARY KEY (ts_code, end_date, ann_date)
);

CREATE INDEX IF NOT EXISTS idx_forecast_end_date ON forecast (end_date);
CREATE INDEX IF NOT EXISTS idx_forecast_type ON forecast (type);

-- express: 业绩快报
CREATE TABLE IF NOT EXISTS express (
    ts_code                    VARCHAR(32) NOT NULL,
    end_date                   DATE        NOT NULL,
    ann_date                   DATE        NOT NULL,
    revenue                    NUMERIC(20, 4),      -- 营业收入
    operate_profit             NUMERIC(20, 4),      -- 营业利润
    total_profit               NUMERIC(20, 4),      -- 利润总额
    n_income                   NUMERIC(20, 4),      -- 净利润
    total_assets               NUMERIC(20, 4),      -- 总资产
    total_hldr_eqy_exc_min_int NUMERIC(20, 4),      -- 股东权益(不含少数)
    diluted_eps                NUMERIC(12, 4),      -- 每股收益(摊薄)
    diluted_roe                NUMERIC(16, 4),      -- 净资产收益率(摊薄)
    yoy_net_profit             NUMERIC(16, 4),      -- 去年同期净利润
    bps                        NUMERIC(12, 4),      -- 每股净资产
    yoy_sales                  NUMERIC(16, 4),      -- 营收同比增长
    yoy_dedu_np                NUMERIC(16, 4),      -- 归母净利润同比增长
    is_audit                   INT,                 -- 是否审计
    perf_summary               TEXT,                -- 简要说明
    update_flag                VARCHAR(4),

    created_at                 TIMESTAMP NOT NULL DEFAULT NOW(),
    PRIMARY KEY (ts_code, end_date, ann_date)
);

CREATE INDEX IF NOT EXISTS idx_express_end_date ON express (end_date);

-- fina_indicator: 财务指标
CREATE TABLE IF NOT EXISTS fina_indicator (
    ts_code                    VARCHAR(32) NOT NULL,
    end_date                   DATE        NOT NULL,
    ann_date                   DATE,
    report_type                INT,
    comp_type                  INT,

    -- 每股指标
    eps                        NUMERIC(16, 4),      -- 基本每股收益
    dt_eps                     NUMERIC(16, 4),      -- 稀释每股收益
    bps                        NUMERIC(16, 4),      -- 每股净资产
    ocfps                      NUMERIC(16, 4),      -- 每股经营现金流
    revenue_ps                 NUMERIC(16, 4),      -- 每股营业收入

    -- 盈利能力
    roe                        NUMERIC(16, 4),      -- 净资产收益率
    roe_waa                    NUMERIC(16, 4),      -- 加权平均ROE
    roe_dt                     NUMERIC(16, 4),      -- 扣非ROE
    roa                        NUMERIC(16, 4),      -- 总资产报酬率
    roic                       NUMERIC(16, 4),      -- 投入资本回报率
    grossprofit_margin         NUMERIC(16, 4),      -- 销售毛利率(%)
    netprofit_margin           NUMERIC(16, 4),      -- 销售净利率(%)

    -- 偿债能力
    current_ratio              NUMERIC(16, 4),      -- 流动比率
    quick_ratio                NUMERIC(16, 4),      -- 速动比率
    debt_to_assets             NUMERIC(16, 4),      -- 资产负债率(%)
    debt_to_eqt                NUMERIC(16, 4),      -- 产权比率
    ebit_to_interest           NUMERIC(16, 4),      -- 已获利息倍数

    -- 营运能力
    ar_turn                    NUMERIC(16, 4),      -- 应收账款周转率
    inv_turn                   NUMERIC(16, 4),      -- 存货周转率
    assets_turn                NUMERIC(16, 4),      -- 总资产周转率
    turn_days                  NUMERIC(16, 4),      -- 营业周期(天)

    -- 现金流
    fcff                       NUMERIC(20, 4),      -- 企业自由现金流
    fcfe                       NUMERIC(20, 4),      -- 股权自由现金流
    salescash_to_or            NUMERIC(16, 4),      -- 销售收现比

    -- 收益质量
    profit_dedt               NUMERIC(20, 4),      -- 扣非净利润
    extra_item                 NUMERIC(20, 4),      -- 非经常性损益
    update_flag                VARCHAR(4),

    created_at                 TIMESTAMP NOT NULL DEFAULT NOW(),
    PRIMARY KEY (ts_code, end_date)
);

CREATE INDEX IF NOT EXISTS idx_fi_end_date ON fina_indicator (end_date);

-- dividend: 分红送股
CREATE TABLE IF NOT EXISTS dividend (
    ts_code                    VARCHAR(32) NOT NULL,
    end_date                   DATE        NOT NULL,
    ann_date                   DATE,
    div_proc                   VARCHAR(16),         -- 实施进度
    stk_div                    NUMERIC(10, 4),      -- 每股送转
    stk_bo_rate                NUMERIC(10, 4),      -- 每股送股
    stk_co_rate                NUMERIC(10, 4),      -- 每股转增
    cash_div                   NUMERIC(12, 4),      -- 每股分红(税后)
    cash_div_tax               NUMERIC(12, 4),      -- 每股分红(税前)
    record_date                DATE,                -- 股权登记日
    ex_date                    DATE,                -- 除权除息日
    pay_date                   DATE,                -- 派息日
    div_listdate               DATE,                -- 红股上市日
    imp_ann_date               DATE,                -- 实施公告日
    base_share                 NUMERIC(20, 4),      -- 基准股本(万)

    created_at                 TIMESTAMP NOT NULL DEFAULT NOW(),
    PRIMARY KEY (ts_code, end_date, div_proc)
);

CREATE INDEX IF NOT EXISTS idx_dividend_ex_date ON dividend (ex_date);

-- fina_mainbz: 主营业务构成
CREATE TABLE IF NOT EXISTS fina_mainbz (
    ts_code                    VARCHAR(32) NOT NULL,
    end_date                   DATE        NOT NULL,
    bz_item                    VARCHAR(256),        -- 业务来源
    bz_code                    VARCHAR(4),          -- P产品 D地区 I行业
    bz_sales                   NUMERIC(20, 4),      -- 主营业务收入
    bz_profit                  NUMERIC(20, 4),      -- 主营业务利润
    bz_cost                    NUMERIC(20, 4),      -- 主营业务成本

    created_at                 TIMESTAMP NOT NULL DEFAULT NOW(),
    PRIMARY KEY (ts_code, end_date, bz_item, bz_code)
);

CREATE INDEX IF NOT EXISTS idx_mainbz_end_date ON fina_mainbz (end_date);
CREATE INDEX IF NOT EXISTS idx_mainbz_code ON fina_mainbz (bz_code);

-- disclosure_date: 财报披露计划
CREATE TABLE IF NOT EXISTS disclosure_date (
    ts_code                    VARCHAR(32) NOT NULL,
    end_date                   DATE        NOT NULL,
    ann_date                   DATE,
    pre_date                   DATE,                -- 预计披露日期
    actual_date                DATE,                -- 实际披露日期
    modify_date                VARCHAR(1024),       -- 修正记录

    created_at                 TIMESTAMP NOT NULL DEFAULT NOW(),
    PRIMARY KEY (ts_code, end_date)
);

CREATE INDEX IF NOT EXISTS idx_disc_date_end_date ON disclosure_date (end_date);
CREATE INDEX IF NOT EXISTS idx_disc_date_actual ON disclosure_date (actual_date);
