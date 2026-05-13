-- stk_weekly_monthly: 周线/月线行情（合并存储）
-- 数据来源：
--   周线: stk_weekly_monthly（每日更新，非周五）/ weekly（每周五收盘后）
--   月线: stk_weekly_monthly（每日更新）/ monthly（月最后一个交易日后）
-- 统一单位: vol=万手, amount=万元（来自 stk_weekly_monthly 接口的原始值）

CREATE TABLE IF NOT EXISTS stk_weekly_monthly (
    ts_code       VARCHAR(32)  NOT NULL,
    trade_date    DATE         NOT NULL,
    freq          VARCHAR(8)   NOT NULL,   -- 'week' 或 'month'
    open          NUMERIC(10, 2),
    high          NUMERIC(10, 2),
    low           NUMERIC(10, 2),
    close         NUMERIC(10, 2),
    pre_close     NUMERIC(10, 2),
    change        NUMERIC(10, 2),
    pct_chg       NUMERIC(8, 2),
    vol           NUMERIC(16, 2),          -- 万手
    amount        NUMERIC(16, 2),          -- 万元
    source        VARCHAR(32)  NOT NULL,   -- 'stk_weekly_monthly', 'weekly', 'monthly'
    created_at    TIMESTAMP    NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMP    NOT NULL DEFAULT NOW(),
    PRIMARY KEY (ts_code, trade_date, freq)
);

CREATE INDEX IF NOT EXISTS idx_stk_wm_date ON stk_weekly_monthly (trade_date);
CREATE INDEX IF NOT EXISTS idx_stk_wm_freq ON stk_weekly_monthly (freq);
