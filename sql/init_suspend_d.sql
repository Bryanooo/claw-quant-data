-- suspend_d: 每日停复牌信息
-- Tushare 接口: suspend_d
-- 更新时间: 不定期（停复牌随时可能发生）

CREATE TABLE IF NOT EXISTS suspend_d (
    ts_code         VARCHAR(16)  NOT NULL,   -- TS代码
    trade_date      DATE         NOT NULL,   -- 日期
    suspend_timing  VARCHAR(32),             -- 日内停牌时间段
    suspend_type    VARCHAR(4)   NOT NULL,   -- S-停牌 R-复牌
    created_at      TIMESTAMP    NOT NULL DEFAULT NOW(),
    PRIMARY KEY (ts_code, trade_date, suspend_type)
);

CREATE INDEX IF NOT EXISTS idx_suspend_d_date ON suspend_d (trade_date);
CREATE INDEX IF NOT EXISTS idx_suspend_d_code ON suspend_d (ts_code);
