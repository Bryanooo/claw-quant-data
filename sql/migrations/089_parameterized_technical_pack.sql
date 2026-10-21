-- Frequency-aware common technical families and objective descriptive
-- structure metrics.  These are data products, not predictive factor claims.

ALTER TABLE technical_factor_snapshot
    ADD COLUMN IF NOT EXISTS sma_30 NUMERIC,
    ADD COLUMN IF NOT EXISTS ema_5 NUMERIC,
    ADD COLUMN IF NOT EXISTS ema_10 NUMERIC,
    ADD COLUMN IF NOT EXISTS ema_12 NUMERIC,
    ADD COLUMN IF NOT EXISTS ema_26 NUMERIC,
    ADD COLUMN IF NOT EXISTS ema_100 NUMERIC,
    ADD COLUMN IF NOT EXISTS rsi_6 NUMERIC,
    ADD COLUMN IF NOT EXISTS rsi_12 NUMERIC,
    ADD COLUMN IF NOT EXISTS rsi_14 NUMERIC,
    ADD COLUMN IF NOT EXISTS rsi_24 NUMERIC,
    ADD COLUMN IF NOT EXISTS roc_5 NUMERIC,
    ADD COLUMN IF NOT EXISTS roc_10 NUMERIC,
    ADD COLUMN IF NOT EXISTS roc_20 NUMERIC,
    ADD COLUMN IF NOT EXISTS roc_60 NUMERIC,
    ADD COLUMN IF NOT EXISTS roc_120 NUMERIC,
    ADD COLUMN IF NOT EXISTS cci_14 NUMERIC,
    ADD COLUMN IF NOT EXISTS cci_20 NUMERIC,
    ADD COLUMN IF NOT EXISTS atr_14 NUMERIC,
    ADD COLUMN IF NOT EXISTS atr_20 NUMERIC,
    ADD COLUMN IF NOT EXISTS natr_20 NUMERIC,
    ADD COLUMN IF NOT EXISTS tsi_25_13 NUMERIC,
    ADD COLUMN IF NOT EXISTS bollinger_percent_b_20_2 NUMERIC,
    ADD COLUMN IF NOT EXISTS bollinger_bandwidth_20_2_pct NUMERIC,
    ADD COLUMN IF NOT EXISTS body_return NUMERIC,
    ADD COLUMN IF NOT EXISTS range_to_open NUMERIC,
    ADD COLUMN IF NOT EXISTS body_to_range NUMERIC,
    ADD COLUMN IF NOT EXISTS upper_shadow_to_open NUMERIC,
    ADD COLUMN IF NOT EXISTS upper_shadow_to_range NUMERIC,
    ADD COLUMN IF NOT EXISTS lower_shadow_to_open NUMERIC,
    ADD COLUMN IF NOT EXISTS lower_shadow_to_range NUMERIC,
    ADD COLUMN IF NOT EXISTS close_location_to_open NUMERIC,
    ADD COLUMN IF NOT EXISTS close_location_to_range NUMERIC,
    ADD COLUMN IF NOT EXISTS range_position_60 NUMERIC,
    ADD COLUMN IF NOT EXISTS atr_5_to_20_ratio NUMERIC,
    ADD COLUMN IF NOT EXISTS retracement_depth_20 NUMERIC,
    ADD COLUMN IF NOT EXISTS retracement_depth_120 NUMERIC,
    ADD COLUMN IF NOT EXISTS regression_slope_20_pct NUMERIC,
    ADD COLUMN IF NOT EXISTS regression_r_squared_20 NUMERIC,
    ADD COLUMN IF NOT EXISTS regression_slope_60_pct NUMERIC,
    ADD COLUMN IF NOT EXISTS regression_r_squared_60 NUMERIC,
    ADD COLUMN IF NOT EXISTS breakout_over_prior_high_60_atr NUMERIC,
    ADD COLUMN IF NOT EXISTS high_touch_count_60_1pct INTEGER,
    ADD COLUMN IF NOT EXISTS low_touch_count_60_1pct INTEGER,
    ADD COLUMN IF NOT EXISTS parameterized_indicator_status VARCHAR(32)
        NOT NULL DEFAULT 'not_computed';

ALTER TABLE technical_factor_snapshot
    ADD CONSTRAINT ck_technical_factor_snapshot_parameterized_status CHECK (
        parameterized_indicator_status IN (
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
            'indicator', 'parameterized_technical_pack',
            'reason', 'not_computed_for_legacy_snapshot'
        )
    )
WHERE parameterized_indicator_status = 'not_computed'
  AND NOT EXISTS (
      SELECT 1
      FROM jsonb_array_elements(unavailable_reasons) AS reason
      WHERE reason->>'indicator' = 'parameterized_technical_pack'
  );

CREATE INDEX IF NOT EXISTS idx_technical_factor_snapshot_rsi14
    ON technical_factor_snapshot(snapshot_date DESC, rsi_14)
    WHERE parameterized_indicator_status = 'ready';

CREATE INDEX IF NOT EXISTS idx_technical_factor_snapshot_structure
    ON technical_factor_snapshot(
        snapshot_date DESC,
        range_position_60,
        atr_5_to_20_ratio
    )
    WHERE parameterized_indicator_status = 'ready';

COMMENT ON COLUMN technical_factor_snapshot.parameterized_indicator_status IS
    'Readiness of frequency-aware deterministic indicator pack; no predictive factor claim';
COMMENT ON COLUMN technical_factor_snapshot.body_to_range IS
    'Signed candle body divided by high-low range; deterministic OHLC geometry';
COMMENT ON COLUMN technical_factor_snapshot.regression_r_squared_60 IS
    'R-squared of close on bar index over 60 completed daily bars';
