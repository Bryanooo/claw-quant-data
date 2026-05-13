-- income: 上市公司利润表
-- 来源: Tushare income_vip（按季度取全市场）
-- 报告频率: 每年4次（年报1231、一季报0331、半年报0630、三季报0930）
-- 调度: 财报季后次月5日（如Q1在5月、半年报在9月、Q3在11月、年报在5月）

CREATE TABLE IF NOT EXISTS income (
    ts_code              VARCHAR(32) NOT NULL,
    end_date             DATE        NOT NULL,   -- 报告期（季度末日期）
    report_type          INT         NOT NULL DEFAULT 1,  -- 1=合并 2=单季
    comp_type            INT,                    -- 1=一般工商业 2=银行 3=保险 4=证券
    ann_date             DATE,                   -- 公告日期
    f_ann_date           DATE,                   -- 实际公告日期
    basic_eps            NUMERIC(12, 4),         -- 基本每股收益
    diluted_eps          NUMERIC(12, 4),         -- 稀释每股收益
    revenue              NUMERIC(20, 4),         -- 营业收入
    total_revenue        NUMERIC(20, 4),         -- 营业总收入
    oper_cost            NUMERIC(20, 4),         -- 营业成本
    sell_exp             NUMERIC(20, 4),         -- 销售费用
    admin_exp            NUMERIC(20, 4),         -- 管理费用
    fin_exp              NUMERIC(20, 4),         -- 财务费用
    rd_exp               NUMERIC(20, 4),         -- 研发费用
    biz_tax_surchg       NUMERIC(20, 4),         -- 营业税金及附加
    assets_impair_loss   NUMERIC(20, 4),         -- 资产减值损失
    invest_income        NUMERIC(20, 4),         -- 投资收益
    fv_value_chg_gain    NUMERIC(20, 4),         -- 公允价值变动收益
    operate_profit       NUMERIC(20, 4),         -- 营业利润
    non_oper_income      NUMERIC(20, 4),         -- 营业外收入
    non_oper_exp         NUMERIC(20, 4),         -- 营业外支出
    total_profit         NUMERIC(20, 4),         -- 利润总额
    income_tax           NUMERIC(20, 4),         -- 所得税
    n_income             NUMERIC(20, 4),         -- 净利润（含少数）
    n_income_attr_p      NUMERIC(20, 4),         -- 归母净利润
    minority_gain        NUMERIC(20, 4),         -- 少数股东损益
    ebit                 NUMERIC(20, 4),         -- 息税前利润
    ebitda               NUMERIC(20, 4),         -- 息税折旧摊销前利润
    oth_compr_income     NUMERIC(20, 4),         -- 其他综合收益
    t_compr_income       NUMERIC(20, 4),         -- 综合收益总额
    compr_inc_attr_p     NUMERIC(20, 4),         -- 归属母公司综合收益
    update_flag          VARCHAR(4),             -- 更新标识
    created_at           TIMESTAMP   NOT NULL DEFAULT NOW(),
    PRIMARY KEY (ts_code, end_date, report_type)
);

CREATE INDEX IF NOT EXISTS idx_income_end_date ON income (end_date);
CREATE INDEX IF NOT EXISTS idx_income_ts_code ON income (ts_code);
