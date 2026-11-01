-- Preserve old values as retired audit evidence; never silently rewrite their
-- formula version. New production values use the corrected v2 contract.
SET LOCAL lock_timeout='5s';
DO $$ BEGIN
    IF EXISTS (SELECT 1 FROM orchestration_v2.task_execution
        WHERE task_key='local_factor_snapshot' AND status IN ('running','validating','publishing')) THEN
        RAISE EXCEPTION 'Wait for factor execution before quality migration';
    END IF;
END $$;
ALTER TABLE balancesheet ADD COLUMN IF NOT EXISTS lt_rec NUMERIC;
ALTER TABLE local_factor_snapshot
    ADD COLUMN audit_status TEXT NOT NULL DEFAULT 'not_audited',
    ADD COLUMN audit_evidence JSONB NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN technical_audit_status TEXT NOT NULL DEFAULT 'not_audited',
    ADD CONSTRAINT ck_factor_audit_status CHECK(audit_status IN ('not_audited','ready','partial','not_expected'));
ALTER TABLE local_factor_validation ADD COLUMN value_match_ratio DOUBLE PRECISION;
ALTER TABLE local_factor_validation DROP CONSTRAINT ck_local_factor_validation_status;
ALTER TABLE local_factor_validation ADD CONSTRAINT ck_local_factor_validation_status
    CHECK(validation_status IN ('matched','correlated','review_required','not_comparable'));
UPDATE local_factor_validation SET validation_status='correlated',
    validation_reason='legacy correlation-only evidence; not value equivalence'
    WHERE validation_status='matched';
COMMENT ON COLUMN local_factor_validation.validation_status IS
    'matched: >=30 samples and >=99% values within atol=1e-5+rtol=1e-3; correlated is not matched';
UPDATE local_factor_schema SET lifecycle_status='retired',retired_at=NOW()
    WHERE lifecycle_status='active';
INSERT INTO local_factor_schema(schema_version,factor_count,formula_digest,description,activated_at)
    VALUES('local-272-v2',272,repeat('0',64),'Value-level validation and per-feature input readiness',NOW());
DO $$ DECLARE definition TEXT; BEGIN
    SELECT pg_get_viewdef('technical_factor_snapshot'::regclass,true) INTO definition;
    definition := replace(definition, '''local-272-v1''', '''local-272-v2''');
    definition := replace(definition, 'FROM local_factor_snapshot', ', local_factor_snapshot.technical_audit_status AS audit_status FROM local_factor_snapshot');
    EXECUTE 'CREATE OR REPLACE VIEW technical_factor_snapshot AS '||definition;
END $$;
CREATE OR REPLACE VIEW local_factor_current AS
    SELECT * FROM local_factor_snapshot WHERE schema_version='local-272-v2';
UPDATE orchestration_v2.dataset_state
    SET data_status='indeterminate',ready=FALSE,revision=revision+1,updated_at=NOW(),
        validation_summary=validation_summary||'{"reason":"factor_quality_contract_changed_requires_reaudit"}'::jsonb
    WHERE dataset_name IN ('local_factor_snapshot','technical_factor_snapshot');
UPDATE orchestration_v2.task_definition SET lifecycle_status='retired',retired_at=NOW(),updated_at=NOW()
    WHERE task_key='local_factor_snapshot' AND lifecycle_status='active';
UPDATE orchestration_v2.task_execution SET status='superseded',finished_at=NOW(),updated_at=NOW(),
    final_error_message='Replan using corrected per-feature quality contract'
    WHERE task_key='local_factor_snapshot' AND status IN ('created','queued','retrying','waiting_dependency');
