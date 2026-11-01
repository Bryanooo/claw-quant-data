-- Independent validation evidence for locally calculated factors.  Provider
-- values are comparison evidence only and never overwrite local snapshots.

CREATE TABLE IF NOT EXISTS local_factor_validation (
    schema_version          VARCHAR(64) NOT NULL,
    trade_date              DATE NOT NULL,
    factor_position         SMALLINT NOT NULL,
    sample_size             INTEGER NOT NULL DEFAULT 0,
    pearson_correlation     DOUBLE PRECISION,
    mean_absolute_error     DOUBLE PRECISION,
    normalized_mae          DOUBLE PRECISION,
    validation_status       VARCHAR(24) NOT NULL,
    validation_reason       TEXT NOT NULL,
    computed_at             TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (schema_version, trade_date, factor_position),
    FOREIGN KEY (schema_version, factor_position)
        REFERENCES local_factor_catalog(schema_version, factor_position),
    CONSTRAINT ck_local_factor_validation_position CHECK (
        factor_position BETWEEN 1 AND 272
    ),
    CONSTRAINT ck_local_factor_validation_sample CHECK (sample_size >= 0),
    CONSTRAINT ck_local_factor_validation_status CHECK (
        validation_status IN ('matched', 'review_required', 'not_comparable')
    )
);

CREATE INDEX IF NOT EXISTS idx_local_factor_validation_status
    ON local_factor_validation(
        trade_date DESC, validation_status, schema_version, factor_position
    );

COMMENT ON TABLE local_factor_validation IS
    'Per-factor, per-session reproducibility evidence; provider values never replace local values';
COMMENT ON COLUMN local_factor_validation.validation_status IS
    'matched requires >=30 paired observations and Pearson correlation >=0.90';
