-- Some THS indices legitimately use very large absolute levels and change
-- values. Preserve the upstream numeric values instead of failing a complete
-- date partition on narrow equity-price precision assumptions.
ALTER TABLE ths_daily
    ALTER COLUMN close TYPE NUMERIC(24,6),
    ALTER COLUMN open TYPE NUMERIC(24,6),
    ALTER COLUMN high TYPE NUMERIC(24,6),
    ALTER COLUMN low TYPE NUMERIC(24,6),
    ALTER COLUMN pre_close TYPE NUMERIC(24,6),
    ALTER COLUMN avg_price TYPE NUMERIC(24,6),
    ALTER COLUMN change TYPE NUMERIC(24,6),
    ALTER COLUMN pct_change TYPE NUMERIC(24,6),
    ALTER COLUMN vol TYPE NUMERIC(24,6),
    ALTER COLUMN turnover_rate TYPE NUMERIC(24,6),
    ALTER COLUMN total_mv TYPE NUMERIC(24,6),
    ALTER COLUMN float_mv TYPE NUMERIC(24,6);

COMMENT ON COLUMN ths_daily.close IS
    'Upstream THS index level; widened for indices with multi-billion absolute values.';
COMMENT ON COLUMN ths_daily.change IS
    'Upstream THS index change; widened together with index levels.';
COMMENT ON COLUMN ths_daily.pct_change IS
    'Upstream percentage change; widened to preserve documented outlier values.';
