-- Scheduled-pull standard layer for 蚂蚁数据源 (financial_data) routes.
-- Scope: P0 daily alt-data rankings + P1 weekly/monthly whole-market reference
-- snapshots approved for periodic collection (see ant_scheduled.py).
-- Convention: _record_hash is the content hash of the full business row, so
-- re-collection of identical payloads is idempotent and history accumulates
-- only when upstream facts actually change.

CREATE TABLE IF NOT EXISTS "ant_norm_hot_stock_rank" (
    _record_hash CHAR(64) PRIMARY KEY,
    _source_collected_at TIMESTAMPTZ NOT NULL,
    _first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    "trade_date" DATE NOT NULL,
    "rank" INTEGER,
    "symbol" TEXT,
    "sec_name" TEXT,
    "score" NUMERIC,
    "rank_raise" INTEGER,
    "begin_date" DATE,
    "payload" JSONB NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS "idx_ant_norm_hot_stock_rank_date" ON "ant_norm_hot_stock_rank" ("trade_date" DESC, "rank");
COMMENT ON TABLE "ant_norm_hot_stock_rank" IS '支付宝热门股票榜；每日定采（路由 /api/v1/altdata/hot-stock-rank）';

CREATE TABLE IF NOT EXISTS "ant_norm_hot_plate_rank" (
    _record_hash CHAR(64) PRIMARY KEY,
    _source_collected_at TIMESTAMPTZ NOT NULL,
    _first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    "trade_date" DATE NOT NULL,
    "rank" INTEGER,
    "symbol" TEXT,
    "plate_name" TEXT,
    "pct_chg" NUMERIC,
    "pct_chg_abs" NUMERIC,
    "pct_chg_1m" NUMERIC,
    "pct_chg_3m" NUMERIC,
    "main_net_inflow" NUMERIC,
    "main_net_inflow_1w" NUMERIC,
    "payload" JSONB NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS "idx_ant_norm_hot_plate_rank_date" ON "ant_norm_hot_plate_rank" ("trade_date" DESC, "rank");
COMMENT ON TABLE "ant_norm_hot_plate_rank" IS '支付宝热门板块榜；每日定采（路由 /api/v1/altdata/hot-plate-rank）';

CREATE TABLE IF NOT EXISTS "ant_norm_equity_structure" (
    _record_hash CHAR(64) PRIMARY KEY,
    _source_collected_at TIMESTAMPTZ NOT NULL,
    _first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    "symbol" TEXT NOT NULL,
    "end_date" DATE,
    "payload" JSONB NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS "idx_ant_norm_equity_structure_symbol" ON "ant_norm_equity_structure" ("symbol", "end_date" DESC);
COMMENT ON TABLE "ant_norm_equity_structure" IS '股本结构（全市场快照）；每周定采（路由 /api/v1/stock_fnd/equity-structure）';

CREATE TABLE IF NOT EXISTS "ant_norm_free_float" (
    _record_hash CHAR(64) PRIMARY KEY,
    _source_collected_at TIMESTAMPTZ NOT NULL,
    _first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    "symbol" TEXT NOT NULL,
    "adjustment_date" DATE,
    "free_float_shares" NUMERIC,
    "free_float_share_ratio" NUMERIC,
    "non_free_float_shares" NUMERIC,
    "free_float_share_change_type" TEXT,
    "is_share_change_corporate_action" TEXT,
    "payload" JSONB NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS "idx_ant_norm_free_float_symbol" ON "ant_norm_free_float" ("symbol", "adjustment_date" DESC);
COMMENT ON TABLE "ant_norm_free_float" IS '自由流通股本（全市场事件史）；每周定采（路由 /api/v1/stock_fnd/free-float）';

CREATE TABLE IF NOT EXISTS "ant_norm_actual_controller" (
    _record_hash CHAR(64) PRIMARY KEY,
    _source_collected_at TIMESTAMPTZ NOT NULL,
    _first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    "symbol" TEXT NOT NULL,
    "end_date" DATE,
    "actual_controller_name" TEXT,
    "actual_controller_type" TEXT,
    "actual_controller_total_hold_ratio" NUMERIC,
    "payload" JSONB NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS "idx_ant_norm_actual_controller_symbol" ON "ant_norm_actual_controller" ("symbol", "end_date" DESC);
COMMENT ON TABLE "ant_norm_actual_controller" IS '实际控制人；每月定采（路由 /api/v1/stock_fnd/actual-controller）';

CREATE TABLE IF NOT EXISTS "ant_norm_controlling_shareholder" (
    _record_hash CHAR(64) PRIMARY KEY,
    _source_collected_at TIMESTAMPTZ NOT NULL,
    _first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    "symbol" TEXT NOT NULL,
    "end_date" DATE,
    "controlling_shareholder_name" TEXT,
    "controlling_shareholder_type" TEXT,
    "controlling_shareholder_total_hold_ratio" NUMERIC,
    "payload" JSONB NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS "idx_ant_norm_controlling_shareholder_symbol" ON "ant_norm_controlling_shareholder" ("symbol", "end_date" DESC);
COMMENT ON TABLE "ant_norm_controlling_shareholder" IS '控股股东；每月定采（路由 /api/v1/stock_fnd/controlling-shareholder）';

CREATE TABLE IF NOT EXISTS "ant_norm_style_classification" (
    _record_hash CHAR(64) PRIMARY KEY,
    _source_collected_at TIMESTAMPTZ NOT NULL,
    _first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    "symbol" TEXT NOT NULL,
    "end_date" DATE,
    "stock_size_classification" TEXT,
    "stock_style_classification" TEXT,
    "stock_size_value" NUMERIC,
    "stock_style_value" NUMERIC,
    "payload" JSONB NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS "idx_ant_norm_style_classification_symbol" ON "ant_norm_style_classification" ("symbol", "end_date" DESC);
COMMENT ON TABLE "ant_norm_style_classification" IS '股票风格规模分类；每月定采（路由 /api/v1/stock_fnd/style-classification）';
