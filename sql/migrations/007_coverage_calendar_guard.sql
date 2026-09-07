ALTER TABLE sys_data_coverage_audit
    DROP CONSTRAINT IF EXISTS ck_data_coverage_audit_status;

ALTER TABLE sys_data_coverage_audit
    ADD CONSTRAINT ck_data_coverage_audit_status
    CHECK (status IN ('complete', 'gaps', 'empty', 'observed_only', 'unverified'));
