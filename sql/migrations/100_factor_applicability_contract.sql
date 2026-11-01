-- Separate genuine technical-input gaps from proven formula inapplicability.
-- Existing v2 values remain immutable audit evidence; v3 republishes the
-- same 272 positions under the stricter applicability/evidence contract.
SET LOCAL lock_timeout='5s';

DO $$ BEGIN
    IF EXISTS (
        SELECT 1 FROM orchestration_v2.task_execution
        WHERE task_key='local_factor_snapshot'
          AND status IN ('running','validating','publishing')
    ) THEN
        RAISE EXCEPTION 'Wait for factor execution before applicability migration';
    END IF;
END $$;

UPDATE local_factor_schema
SET lifecycle_status='retired', retired_at=NOW()
WHERE lifecycle_status='active';

INSERT INTO local_factor_schema(
    schema_version, factor_count, formula_digest, description, activated_at
)
VALUES(
    'local-272-v3', 272, repeat('0',64),
    'Per-feature applicability: trading-bar warmup and proven undefined domains',
    NOW()
);

DO $$ DECLARE definition TEXT; BEGIN
    SELECT pg_get_viewdef('technical_factor_snapshot'::regclass, true)
    INTO definition;
    definition := replace(
        definition, '''local-272-v2''', '''local-272-v3'''
    );
    EXECUTE 'CREATE OR REPLACE VIEW technical_factor_snapshot AS ' || definition;
END $$;

CREATE OR REPLACE VIEW local_factor_current AS
    SELECT * FROM local_factor_snapshot
    WHERE schema_version='local-272-v3';

UPDATE orchestration_v2.dataset_state
SET data_status='indeterminate', ready=FALSE, revision=revision+1,
    updated_at=NOW(),
    validation_summary=validation_summary ||
        '{"reason":"factor_applicability_contract_changed_requires_reaudit"}'::jsonb
WHERE dataset_name IN ('local_factor_snapshot','technical_factor_snapshot');

UPDATE orchestration_v2.task_definition
SET lifecycle_status='retired', retired_at=NOW(), updated_at=NOW()
WHERE task_key='local_factor_snapshot' AND lifecycle_status='active';

UPDATE orchestration_v2.task_execution
SET status='superseded', finished_at=NOW(), updated_at=NOW(),
    final_error_message='Replan using v3 factor applicability contract'
WHERE task_key='local_factor_snapshot'
  AND status IN ('created','queued','retrying','waiting_dependency');

