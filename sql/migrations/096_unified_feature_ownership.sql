-- One physical publication for locally computed daily features. The legacy
-- technical dataset becomes a projection, not a second store or producer.
SET LOCAL lock_timeout = '5s';

DO $$ BEGIN
    IF EXISTS (SELECT 1 FROM orchestration_v2.task_execution
               WHERE task_key IN ('technical_factor_snapshot','local_factor_snapshot')
                 AND status IN ('running','validating','publishing')) THEN
        RAISE EXCEPTION 'Wait for active factor executions before migrating';
    END IF;
END $$;

ALTER TABLE local_factor_snapshot
    ADD COLUMN technical_values JSONB NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE local_factor_snapshot ADD CONSTRAINT ck_feature_no_duplicate_slots
    CHECK (NOT technical_values ?| ARRAY[
        'rsi_14','macd_dif_12_26','macd_dea_9','macd_histogram_12_26_9',
        'sma_20','return_5d','alpha101_101','roc_5'
    ]);

-- A new installation has no rows yet. The runtime registers the full catalog.
INSERT INTO local_factor_schema(schema_version,factor_count,formula_digest,description)
VALUES ('local-272-v1',272,repeat('0',64),'Unified local daily research features')
ON CONFLICT (schema_version) DO NOTHING;

CREATE TEMP TABLE feature_slot_mapping(field TEXT PRIMARY KEY, position INTEGER);
INSERT INTO feature_slot_mapping VALUES
    ('rsi_14',232),('macd_dif_12_26',169),('macd_dea_9',170),
    ('macd_histogram_12_26_9',168),('sma_20',153),('return_5d',152),
    ('alpha101_101',101);

-- Refuse ambiguous migration: never silently choose between disagreeing copies.
DO $$ BEGIN
    IF EXISTS (
        SELECT 1 FROM technical_factor_snapshot t
        JOIN local_factor_snapshot s ON s.trade_date=t.snapshot_date
          AND s.ts_code=t.ts_code AND s.schema_version='local-272-v1'
        CROSS JOIN feature_slot_mapping m
        WHERE s.factor_values[m.position] IS NOT NULL
          AND (to_jsonb(t)->>m.field)::double precision IS NOT NULL
          AND abs(s.factor_values[m.position]-(to_jsonb(t)->>m.field)::double precision)
              > 1e-9 * greatest(1,abs(s.factor_values[m.position]))
    ) THEN RAISE EXCEPTION 'Conflicting canonical feature copies; review required'; END IF;
END $$;

WITH source AS MATERIALIZED (
    SELECT t.*,to_jsonb(t) AS payload FROM technical_factor_snapshot t
), prepared AS MATERIALIZED (
    SELECT source.*, ARRAY(SELECT CASE WHEN m.field='return_5d'
        THEN coalesce((payload->>'return_5d')::double precision,
                      (payload->>'roc_5')::double precision/100.0)
        ELSE (payload->>m.field)::double precision END
        FROM generate_series(1,272) i
        LEFT JOIN feature_slot_mapping m ON m.position=i ORDER BY i) AS vals
    FROM source
)
INSERT INTO local_factor_snapshot (
    schema_version,trade_date,ts_code,factor_values,ready_mask,ready_count,
    unavailable_positions,calculation_status,input_revision_digest,formula_digest,
    source_execution_id,computed_at,technical_values
)
SELECT 'local-272-v1',t.snapshot_date,t.ts_code,t.vals,
    (SELECT string_agg(CASE WHEN x IS NULL THEN '0' ELSE '1' END,'') FROM unnest(t.vals) x)::bit(272),
    (SELECT count(*) FROM unnest(t.vals) x WHERE x IS NOT NULL),
    ARRAY(SELECT i::smallint FROM generate_series(1,272) i WHERE t.vals[i] IS NULL),
    CASE WHEN (SELECT count(*) FROM unnest(t.vals) x WHERE x IS NOT NULL)=0
        THEN 'missing_input' ELSE 'partial' END,
    repeat('0',64),s.formula_digest,t.source_execution_id,t.computed_at,
    t.payload-ARRAY['snapshot_date','ts_code','source_execution_id','computed_at',
        'rsi_14','macd_dif_12_26','macd_dea_9','macd_histogram_12_26_9',
        'sma_20','return_5d','alpha101_101','roc_5']
FROM prepared t
JOIN local_factor_schema s ON s.schema_version='local-272-v1'
ON CONFLICT (schema_version,trade_date,ts_code) DO UPDATE SET
    technical_values=EXCLUDED.technical_values;

-- Build a typed, read-only compatibility projection using the original types.
-- All 104 original columns remain addressable without another stored copy.
DO $$
DECLARE projections TEXT; old_count BIGINT; new_count BIGINT;
BEGIN
    SELECT count(*) INTO old_count FROM technical_factor_snapshot;
    SELECT count(*) INTO new_count FROM local_factor_snapshot
      WHERE schema_version='local-272-v1' AND technical_values <> '{}'::jsonb;
    IF old_count <> new_count THEN RAISE EXCEPTION 'Technical migration count mismatch'; END IF;
    SELECT string_agg(
        CASE
          WHEN a.attname='snapshot_date' THEN 'trade_date AS snapshot_date'
          WHEN a.attname IN ('ts_code','source_execution_id','computed_at') THEN quote_ident(a.attname)
          WHEN m.position IS NOT NULL THEN format('factor_values[%s]::%s AS %I',m.position,format_type(a.atttypid,a.atttypmod),a.attname)
          WHEN a.attname='roc_5' THEN 'factor_values[152] * 100 AS roc_5'
          WHEN a.atttypid='jsonb'::regtype THEN format('technical_values->%L AS %I',a.attname,a.attname)
          ELSE format('(technical_values->>%L)::%s AS %I',a.attname,format_type(a.atttypid,a.atttypmod),a.attname)
        END, ', ' ORDER BY a.attnum) INTO projections
    FROM pg_attribute a LEFT JOIN feature_slot_mapping m ON m.field=a.attname
    WHERE a.attrelid='technical_factor_snapshot'::regclass AND a.attnum>0 AND NOT a.attisdropped;
    DROP TABLE technical_factor_snapshot;
    EXECUTE 'CREATE VIEW technical_factor_snapshot AS SELECT '||projections||
        ' FROM local_factor_snapshot WHERE schema_version=''local-272-v1'' AND technical_values <> ''{}''::jsonb';
END $$;

COMMENT ON VIEW technical_factor_snapshot IS
    'Read-only projection of unified local_factor_snapshot; no duplicate value storage or independent task';
COMMENT ON COLUMN local_factor_snapshot.technical_values IS
    'Additional daily technical features; shared 272 slots and aliases forbidden by CHECK constraint';

UPDATE orchestration_v2.task_definition
SET lifecycle_status='retired',retired_at=NOW(),updated_at=NOW()
WHERE task_key IN ('technical_factor_snapshot','local_factor_snapshot')
  AND lifecycle_status='active';
UPDATE orchestration_v2.task_execution
SET status='superseded',finished_at=NOW(),updated_at=NOW(),
    final_error_message='Replaced by unified feature publication; replan against current definition'
WHERE task_key IN ('technical_factor_snapshot','local_factor_snapshot')
  AND status IN ('created','queued','retrying','waiting_dependency');
