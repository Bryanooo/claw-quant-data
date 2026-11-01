-- A failed coverage attempt can be retired after a later audit proves the
-- same dataset/scope.  The service contract has always exposed
-- ``superseded``; keep the database state machine consistent with it.
ALTER TABLE sys_data_coverage_job
    DROP CONSTRAINT ck_data_coverage_job_status;

ALTER TABLE sys_data_coverage_job
    ADD CONSTRAINT ck_data_coverage_job_status
    CHECK (status IN ('queued', 'running', 'success', 'failed', 'superseded'));
