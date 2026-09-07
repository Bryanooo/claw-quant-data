-- Link successful normalized collection jobs to targeted completeness audits.

ALTER TABLE sys_data_coverage_job
    ADD COLUMN IF NOT EXISTS collection_job_id BIGINT
        REFERENCES sys_collection_job(job_id);

CREATE UNIQUE INDEX IF NOT EXISTS uq_data_coverage_job_collection
    ON sys_data_coverage_job(collection_job_id)
    WHERE collection_job_id IS NOT NULL;

COMMENT ON COLUMN sys_data_coverage_job.collection_job_id IS
    'Collection job whose final completeness status is resolved by this audit';

ALTER TABLE sys_collection_job
    DROP CONSTRAINT IF EXISTS ck_collection_job_completion_status;
ALTER TABLE sys_collection_job
    ADD CONSTRAINT ck_collection_job_completion_status CHECK (
        completion_status IN (
            'pending', 'running', 'retrying', 'complete', 'empty',
            'verifying', 'unverified', 'incomplete', 'failed'
        )
    );
