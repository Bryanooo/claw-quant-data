-- Preserve every delayed empty-result recheck as a separate auditable job.

ALTER TABLE sys_collection_job
    ADD COLUMN IF NOT EXISTS recheck_of_job_id BIGINT
        REFERENCES sys_collection_job(job_id),
    ADD COLUMN IF NOT EXISTS recheck_root_job_id BIGINT
        REFERENCES sys_collection_job(job_id),
    ADD COLUMN IF NOT EXISTS recheck_generation SMALLINT NOT NULL DEFAULT 0;

ALTER TABLE sys_collection_job
    DROP CONSTRAINT IF EXISTS ck_collection_job_recheck_generation;
ALTER TABLE sys_collection_job
    ADD CONSTRAINT ck_collection_job_recheck_generation
        CHECK (recheck_generation BETWEEN 0 AND 20);

CREATE UNIQUE INDEX IF NOT EXISTS uq_collection_job_recheck_source
    ON sys_collection_job(recheck_of_job_id)
    WHERE recheck_of_job_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_collection_job_recheck_root
    ON sys_collection_job(recheck_root_job_id, recheck_generation DESC)
    WHERE recheck_root_job_id IS NOT NULL;

COMMENT ON COLUMN sys_collection_job.recheck_of_job_id IS
    'Previous empty successful job that caused this delayed recheck';
COMMENT ON COLUMN sys_collection_job.recheck_root_job_id IS
    'First logical job in an empty-result recheck chain';
COMMENT ON COLUMN sys_collection_job.recheck_generation IS
    'Zero for the original task, then one per separately audited recheck';
