-- Version the local factor product after separating validation mechanics from
-- formula identity.  Provider comparison is now a deterministic daily sample
-- with explicit evidence about sample size and elapsed time.
SET LOCAL lock_timeout='5s';

DO $$ BEGIN
    IF EXISTS (
        SELECT 1 FROM orchestration_v2.task_execution
        WHERE task_key='local_factor_snapshot'
          AND status IN ('running','validating','publishing')
    ) THEN
        RAISE EXCEPTION 'Wait for factor execution before validation migration';
    END IF;
END $$;

ALTER TABLE local_factor_validation
    ADD COLUMN sample_method TEXT NOT NULL DEFAULT 'legacy_full_cross_section',
    ADD COLUMN sample_seed TEXT,
    ADD COLUMN sample_target_size INTEGER,
    ADD COLUMN sampled_security_count INTEGER,
    ADD COLUMN validation_elapsed_ms INTEGER;

ALTER TABLE local_factor_validation
    ADD CONSTRAINT ck_local_factor_validation_sample_target
        CHECK (sample_target_size IS NULL OR sample_target_size >= 30),
    ADD CONSTRAINT ck_local_factor_validation_sampled_count
        CHECK (sampled_security_count IS NULL OR sampled_security_count >= 0),
    ADD CONSTRAINT ck_local_factor_validation_elapsed
        CHECK (validation_elapsed_ms IS NULL OR validation_elapsed_ms >= 0);

COMMENT ON COLUMN local_factor_validation.sample_method IS
    'Reproducible sampling algorithm; provider values remain validation evidence only';
COMMENT ON COLUMN local_factor_validation.sample_seed IS
    'Seed required to reproduce the exact daily security sample';
COMMENT ON COLUMN local_factor_validation.validation_elapsed_ms IS
    'Observed SQL validation duration; runtime additionally enforces a 15-minute statement timeout';

UPDATE local_factor_schema
SET lifecycle_status='retired', retired_at=NOW()
WHERE lifecycle_status='active';

INSERT INTO local_factor_schema(
    schema_version, factor_count, formula_digest, description, activated_at
)
VALUES(
    'local-272-v4', 272, repeat('0',64),
    'Deterministic daily provider sample plus bounded validation runtime', NOW()
);

DO $$ DECLARE definition TEXT; BEGIN
    SELECT pg_get_viewdef('technical_factor_snapshot'::regclass, true)
    INTO definition;
    definition := replace(definition, '''local-272-v3''', '''local-272-v4''');
    EXECUTE 'CREATE OR REPLACE VIEW technical_factor_snapshot AS ' || definition;
END $$;

CREATE OR REPLACE VIEW local_factor_current AS
    SELECT * FROM local_factor_snapshot
    WHERE schema_version='local-272-v4';

UPDATE orchestration_v2.dataset_state
SET data_status='indeterminate', ready=FALSE, revision=revision+1,
    updated_at=NOW(),
    validation_summary=validation_summary ||
        '{"reason":"bounded_factor_validation_contract_requires_v4_publication"}'::jsonb
WHERE dataset_name IN ('local_factor_snapshot','technical_factor_snapshot');

UPDATE orchestration_v2.task_definition
SET lifecycle_status='retired', retired_at=NOW(), updated_at=NOW()
WHERE task_key='local_factor_snapshot' AND lifecycle_status='active';

UPDATE orchestration_v2.task_execution
SET status='superseded', finished_at=NOW(), updated_at=NOW(),
    final_error_message='Replan using v4 bounded provider validation contract'
WHERE task_key='local_factor_snapshot'
  AND status IN ('created','queued','retrying','waiting_dependency');
