-- Retrying an auditor job must update its evidence instead of duplicating it.

CREATE UNIQUE INDEX IF NOT EXISTS uq_data_coverage_audit_job
    ON sys_data_coverage_audit(job_id)
    WHERE job_id IS NOT NULL;
