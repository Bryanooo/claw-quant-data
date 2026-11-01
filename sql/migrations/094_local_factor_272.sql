-- Local 272-factor product.  Provider-owned tushare_norm_factor_value remains
-- immutable and is used only as validation evidence; locally calculated
-- values live in a versioned, position-stable array snapshot.

-- Canonical technical primitives shared by both the chart/research snapshot
-- and the 272-factor snapshot.  They are calculated once by the upstream
-- technical transformation and reused by local_factor_snapshot.
ALTER TABLE technical_factor_snapshot
    ADD COLUMN IF NOT EXISTS macd_dif_12_26 NUMERIC,
    ADD COLUMN IF NOT EXISTS macd_dea_9 NUMERIC,
    ADD COLUMN IF NOT EXISTS macd_histogram_12_26_9 NUMERIC,
    ADD COLUMN IF NOT EXISTS sma_20 NUMERIC,
    ADD COLUMN IF NOT EXISTS return_5d NUMERIC,
    ADD COLUMN IF NOT EXISTS alpha101_101 NUMERIC;

CREATE TABLE IF NOT EXISTS local_factor_schema (
    schema_version          VARCHAR(64) PRIMARY KEY,
    factor_count            SMALLINT NOT NULL,
    formula_digest          CHAR(64) NOT NULL,
    lifecycle_status        VARCHAR(16) NOT NULL DEFAULT 'active',
    description             TEXT NOT NULL,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    activated_at            TIMESTAMPTZ,
    retired_at              TIMESTAMPTZ,
    CONSTRAINT ck_local_factor_schema_count CHECK (factor_count > 0),
    CONSTRAINT ck_local_factor_schema_digest CHECK (
        formula_digest ~ '^[0-9a-f]{64}$'
    ),
    CONSTRAINT ck_local_factor_schema_status CHECK (
        lifecycle_status IN ('active', 'retired')
    )
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_local_factor_schema_active
    ON local_factor_schema((lifecycle_status))
    WHERE lifecycle_status='active';

CREATE TABLE IF NOT EXISTS local_factor_catalog (
    schema_version          VARCHAR(64) NOT NULL
                            REFERENCES local_factor_schema(schema_version),
    factor_position         SMALLINT NOT NULL,
    factor_name             VARCHAR(128) NOT NULL,
    factor_family           VARCHAR(32) NOT NULL,
    formula                 TEXT NOT NULL,
    computation_group       VARCHAR(32) NOT NULL,
    overlap_kind            VARCHAR(24) NOT NULL DEFAULT 'none',
    overlap_dataset         VARCHAR(128),
    overlap_field           TEXT,
    convention_note         TEXT,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (schema_version, factor_position),
    UNIQUE (schema_version, factor_name),
    CONSTRAINT ck_local_factor_catalog_position CHECK (
        factor_position BETWEEN 1 AND 272
    ),
    CONSTRAINT ck_local_factor_catalog_group CHECK (
        computation_group IN ('alpha101', 'market', 'financial')
    ),
    CONSTRAINT ck_local_factor_catalog_overlap CHECK (
        overlap_kind IN ('none', 'primitive', 'exact_value')
        AND (
            overlap_kind='none'
            OR (overlap_dataset IS NOT NULL AND overlap_field IS NOT NULL)
        )
    )
);

CREATE INDEX IF NOT EXISTS idx_local_factor_catalog_name
    ON local_factor_catalog(factor_name, schema_version);
CREATE INDEX IF NOT EXISTS idx_local_factor_catalog_family
    ON local_factor_catalog(schema_version, factor_family, factor_position);

CREATE TABLE IF NOT EXISTS local_factor_snapshot (
    schema_version          VARCHAR(64) NOT NULL
                            REFERENCES local_factor_schema(schema_version),
    trade_date              DATE NOT NULL,
    ts_code                 VARCHAR(16) NOT NULL,
    factor_values           DOUBLE PRECISION[] NOT NULL,
    ready_mask              BIT(272) NOT NULL,
    ready_count             SMALLINT NOT NULL,
    unavailable_positions   SMALLINT[] NOT NULL DEFAULT '{}'::SMALLINT[],
    calculation_status      VARCHAR(32) NOT NULL,
    input_revision_digest   CHAR(64) NOT NULL,
    formula_digest          CHAR(64) NOT NULL,
    source_execution_id     BIGINT,
    computed_at             TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (schema_version, trade_date, ts_code),
    CONSTRAINT ck_local_factor_snapshot_values CHECK (
        cardinality(factor_values)=272
        AND array_lower(factor_values, 1)=1
    ),
    CONSTRAINT ck_local_factor_snapshot_count CHECK (
        ready_count BETWEEN 0 AND 272
        AND ready_count = length(replace(ready_mask::TEXT, '0', ''))
        AND cardinality(unavailable_positions)=272-ready_count
    ),
    CONSTRAINT ck_local_factor_snapshot_status CHECK (
        calculation_status IN ('ready', 'partial', 'missing_input')
        AND (calculation_status='ready')=(ready_count=272)
        AND (calculation_status='missing_input')=(ready_count=0)
    ),
    CONSTRAINT ck_local_factor_snapshot_digest CHECK (
        input_revision_digest ~ '^[0-9a-f]{64}$'
        AND formula_digest ~ '^[0-9a-f]{64}$'
    )
) PARTITION BY RANGE (trade_date);

DO $$
DECLARE
    y INTEGER;
BEGIN
    FOR y IN 1990..2040 LOOP
        EXECUTE format(
            'CREATE TABLE IF NOT EXISTS local_factor_snapshot_y%s '
            'PARTITION OF local_factor_snapshot FOR VALUES FROM (%L) TO (%L)',
            y, make_date(y, 1, 1), make_date(y + 1, 1, 1)
        );
    END LOOP;
END $$;

CREATE TABLE IF NOT EXISTS local_factor_snapshot_default
    PARTITION OF local_factor_snapshot DEFAULT;

CREATE INDEX IF NOT EXISTS idx_local_factor_snapshot_code_date
    ON local_factor_snapshot(ts_code, trade_date DESC, schema_version);
CREATE INDEX IF NOT EXISTS idx_local_factor_snapshot_date_status
    ON local_factor_snapshot(trade_date DESC, calculation_status, schema_version);

COMMENT ON TABLE local_factor_schema IS
    'Immutable local factor-array schema versions; position changes require a new version';
COMMENT ON TABLE local_factor_catalog IS
    'Stable mapping from factor position to formula, family and existing-product overlap';
COMMENT ON TABLE local_factor_snapshot IS
    'One row per stock/session containing the position-stable 272 locally calculated factor values';
COMMENT ON COLUMN local_factor_snapshot.factor_values IS
    'FLOAT8 array; position n is defined by local_factor_catalog.factor_position=n';
COMMENT ON COLUMN local_factor_snapshot.ready_mask IS
    '272-bit availability mask aligned with factor_values; NULL values are never silently certified';
COMMENT ON COLUMN local_factor_snapshot.trade_date IS
    'Logical data date, distinct from task execution and computed_at timestamps';
