-- Extend the all-market technical snapshot with common trend, momentum,
-- volatility and volume/price factors. Existing rows are explicitly marked
-- partial until the corresponding observation date is rematerialized.

ALTER TABLE technical_factor_snapshot
    ALTER COLUMN formula_version TYPE VARCHAR(128),
    ADD COLUMN IF NOT EXISTS ema_20 NUMERIC,
    ADD COLUMN IF NOT EXISTS ema_50 NUMERIC,
    ADD COLUMN IF NOT EXISTS ema_200 NUMERIC,
    ADD COLUMN IF NOT EXISTS ema_20_distance_pct NUMERIC,
    ADD COLUMN IF NOT EXISTS ema_50_distance_pct NUMERIC,
    ADD COLUMN IF NOT EXISTS ema_200_distance_pct NUMERIC,
    ADD COLUMN IF NOT EXISTS bias_6 NUMERIC,
    ADD COLUMN IF NOT EXISTS bias_12 NUMERIC,
    ADD COLUMN IF NOT EXISTS bias_24 NUMERIC,
    ADD COLUMN IF NOT EXISTS bbi NUMERIC,
    ADD COLUMN IF NOT EXISTS bbi_distance_pct NUMERIC,
    ADD COLUMN IF NOT EXISTS ppo_12_26 NUMERIC,
    ADD COLUMN IF NOT EXISTS ppo_signal_9 NUMERIC,
    ADD COLUMN IF NOT EXISTS ppo_histogram NUMERIC,
    ADD COLUMN IF NOT EXISTS natr_14 NUMERIC,
    ADD COLUMN IF NOT EXISTS keltner_middle_20 NUMERIC,
    ADD COLUMN IF NOT EXISTS keltner_upper_20_2 NUMERIC,
    ADD COLUMN IF NOT EXISTS keltner_lower_20_2 NUMERIC,
    ADD COLUMN IF NOT EXISTS ttm_squeeze_on BOOLEAN,
    ADD COLUMN IF NOT EXISTS ttm_squeeze_momentum NUMERIC,
    ADD COLUMN IF NOT EXISTS trix_12 NUMERIC,
    ADD COLUMN IF NOT EXISTS trix_signal_9 NUMERIC,
    ADD COLUMN IF NOT EXISTS trix_histogram NUMERIC,
    ADD COLUMN IF NOT EXISTS pvt_20_change NUMERIC,
    ADD COLUMN IF NOT EXISTS vroc_12 NUMERIC,
    ADD COLUMN IF NOT EXISTS vroc_20 NUMERIC,
    ADD COLUMN IF NOT EXISTS force_index_13 NUMERIC,
    ADD COLUMN IF NOT EXISTS force_index_13_normalized NUMERIC,
    ADD COLUMN IF NOT EXISTS common_indicator_status VARCHAR(32)
        NOT NULL DEFAULT 'not_computed';

ALTER TABLE technical_factor_snapshot
    DROP CONSTRAINT IF EXISTS ck_technical_factor_snapshot_common_status;
ALTER TABLE technical_factor_snapshot
    ADD CONSTRAINT ck_technical_factor_snapshot_common_status CHECK (
        common_indicator_status IN (
            'ready', 'limited_history', 'insufficient_history',
            'missing_input', 'not_computed'
        )
    );

UPDATE technical_factor_snapshot
SET calculation_status = CASE
        WHEN calculation_status = 'ready' THEN 'partial'
        ELSE calculation_status
    END,
    unavailable_reasons = unavailable_reasons || jsonb_build_array(
        jsonb_build_object(
            'indicator', 'common_technical_pack',
            'reason', 'not_computed_for_legacy_snapshot'
        )
    )
WHERE common_indicator_status = 'not_computed'
  AND NOT EXISTS (
      SELECT 1
      FROM jsonb_array_elements(unavailable_reasons) AS reason
      WHERE reason->>'indicator' = 'common_technical_pack'
  );

CREATE INDEX IF NOT EXISTS idx_technical_factor_snapshot_squeeze
    ON technical_factor_snapshot(snapshot_date DESC, ttm_squeeze_on)
    WHERE common_indicator_status = 'ready';

CREATE INDEX IF NOT EXISTS idx_technical_factor_snapshot_ppo
    ON technical_factor_snapshot(snapshot_date DESC, ppo_histogram)
    WHERE common_indicator_status = 'ready';

COMMENT ON COLUMN technical_factor_snapshot.common_indicator_status IS
    'Readiness of common-technicals-v1; ready requires at least 200 adjusted bars';
COMMENT ON COLUMN technical_factor_snapshot.force_index_13_normalized IS
    'EMA13 Force Index divided by close times 20-period average volume, percent';
COMMENT ON COLUMN technical_factor_snapshot.pvt_20_change IS
    'Twenty-period change of path-dependent Price Volume Trend';
