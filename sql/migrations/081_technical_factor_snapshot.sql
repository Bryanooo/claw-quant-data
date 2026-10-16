-- Materialized all-market technical snapshot.  One row is written for every
-- stock that was listed on the observation date, including rows whose inputs
-- are not yet sufficient.  This makes absence explicit and auditable instead
-- of silently dropping newly listed or input-incomplete securities.

CREATE TABLE IF NOT EXISTS technical_factor_snapshot (
    snapshot_date              DATE NOT NULL,
    ts_code                    VARCHAR(16) NOT NULL,
    source_trade_date          DATE,
    source_bar_count           INTEGER NOT NULL DEFAULT 0,
    adjustment_status          VARCHAR(32) NOT NULL,
    adjustment_matched_count   INTEGER NOT NULL DEFAULT 0,
    price_basis                VARCHAR(32) NOT NULL,
    close                      NUMERIC,
    prior_high_20              NUMERIC,
    atrv_sma_14                NUMERIC,
    niumen_line                NUMERIC,
    confirmation_line          NUMERIC,
    signal_ma_10               NUMERIC,
    niumen_state               VARCHAR(48) NOT NULL,
    crossed_niumen             BOOLEAN NOT NULL DEFAULT FALSE,
    crossed_confirmation       BOOLEAN NOT NULL DEFAULT FALSE,
    cost_20                    NUMERIC,
    cost_20_status             VARCHAR(32) NOT NULL,
    cost_60                    NUMERIC,
    cost_60_status             VARCHAR(32) NOT NULL,
    calculation_status         VARCHAR(32) NOT NULL,
    unavailable_reasons        JSONB NOT NULL DEFAULT '[]'::jsonb,
    formula_version            VARCHAR(64) NOT NULL,
    source_execution_id        BIGINT,
    computed_at                TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (snapshot_date, ts_code),
    CONSTRAINT ck_technical_factor_snapshot_counts CHECK (
        source_bar_count >= 0 AND adjustment_matched_count >= 0
    ),
    CONSTRAINT ck_technical_factor_snapshot_status CHECK (
        calculation_status IN (
            'ready', 'partial', 'insufficient_history', 'missing_input'
        )
    ),
    CONSTRAINT ck_technical_factor_snapshot_reasons CHECK (
        jsonb_typeof(unavailable_reasons) = 'array'
        AND (
            calculation_status = 'ready'
            OR jsonb_array_length(unavailable_reasons) > 0
        )
    ),
    CONSTRAINT ck_technical_factor_snapshot_ready_values CHECK (
        calculation_status <> 'ready'
        OR (
            niumen_line IS NOT NULL
            AND confirmation_line IS NOT NULL
            AND cost_20 IS NOT NULL
            AND cost_60 IS NOT NULL
        )
    )
);

CREATE INDEX IF NOT EXISTS idx_technical_factor_snapshot_code_date
    ON technical_factor_snapshot(ts_code, snapshot_date DESC);
CREATE INDEX IF NOT EXISTS idx_technical_factor_snapshot_date_status
    ON technical_factor_snapshot(snapshot_date, calculation_status, niumen_state);

COMMENT ON TABLE technical_factor_snapshot IS
    'V2 derived daily all-market snapshot: TongdaXin Niumen/confirmation lines and strict 20/60 trading-day transaction-cost lines';
COMMENT ON COLUMN technical_factor_snapshot.snapshot_date IS
    'Logical data date of the derived snapshot, distinct from execution/computation time';
COMMENT ON COLUMN technical_factor_snapshot.source_trade_date IS
    'Latest actual daily bar used; can precede snapshot_date for a suspended stock';
COMMENT ON COLUMN technical_factor_snapshot.unavailable_reasons IS
    'Machine-readable reasons for each indicator that could not be calculated';
