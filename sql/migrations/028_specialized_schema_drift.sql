-- Align specialized board tables with fields observed from their authorized
-- upstream contracts. Widening is non-destructive and existing rows remain.

ALTER TABLE dc_daily
    ADD COLUMN IF NOT EXISTS category TEXT;

ALTER TABLE dc_hot
    ADD COLUMN IF NOT EXISTS hot NUMERIC(18,4),
    ADD COLUMN IF NOT EXISTS concept TEXT;

ALTER TABLE limit_list_d
    ALTER COLUMN up_stat TYPE VARCHAR(16);

COMMENT ON COLUMN dc_daily.category IS '分类板块';
COMMENT ON COLUMN dc_hot.hot IS '热度值（上游扩展字段）';
COMMENT ON COLUMN dc_hot.concept IS '关联概念（上游扩展字段）';
