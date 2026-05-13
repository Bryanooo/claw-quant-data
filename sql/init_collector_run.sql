-- ============================================================
-- sys_collector_run 任务运行记录表
-- ============================================================
-- 用途：记录每次定时调度任务的执行状态，用于：
--   1. 任务失败或超时检测
--   2. 运行历史追溯
--   3. 报警/告警判定
-- ============================================================
-- 用法: psql -h 127.0.0.1 -U tushare -d tushare_db -f init_collector_run.sql
-- ============================================================

CREATE TABLE IF NOT EXISTS sys_collector_run (
    run_id          BIGSERIAL PRIMARY KEY,
    task_id         VARCHAR(64) NOT NULL,         -- scheduler 中的任务 ID，如 "daily_daily"
    task_name       VARCHAR(128) NOT NULL,        -- 任务名称，如 "A股日线行情-盘后全量"
    trigger_type    VARCHAR(16) NOT NULL,          -- cron / manual / bootstrap
    trade_date      DATE,                         -- 关联的交易日
    status          VARCHAR(16) NOT NULL DEFAULT 'running',
                                                  -- running / success / failed / timeout / skipped
    started_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    finished_at     TIMESTAMP WITH TIME ZONE,
    duration_sec    INTEGER,                      -- 执行耗时（秒）
    rows_inserted   INTEGER DEFAULT 0,            -- 入库行数
    retry_count     INTEGER DEFAULT 0,            -- 重试次数
    error_message   TEXT,                         -- 失败/超时时的错误信息
    extra_info      JSONB                         -- 扩展信息（如采集参数等）
);

-- 索引：按任务 + 状态查询最新记录
CREATE INDEX IF NOT EXISTS idx_collector_run_task_status ON sys_collector_run(task_id, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_collector_run_status ON sys_collector_run(status);
CREATE INDEX IF NOT EXISTS idx_collector_run_started ON sys_collector_run(started_at DESC);
