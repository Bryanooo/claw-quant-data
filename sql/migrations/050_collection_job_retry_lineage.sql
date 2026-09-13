-- Separate batch parent/child topology from manual execution-instance retries.
ALTER TABLE sys_collection_job
    ADD COLUMN IF NOT EXISTS retry_of_job_id BIGINT
        REFERENCES sys_collection_job(job_id),
    ADD COLUMN IF NOT EXISTS retry_root_job_id BIGINT
        REFERENCES sys_collection_job(job_id),
    ADD COLUMN IF NOT EXISTS retry_generation SMALLINT NOT NULL DEFAULT 0;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'ck_collection_job_retry_generation'
    ) THEN
        ALTER TABLE sys_collection_job
            ADD CONSTRAINT ck_collection_job_retry_generation
            CHECK (retry_generation BETWEEN 0 AND 20);
    END IF;
END $$;

-- Older manual retries used parent_job_id. A leaf parent identifies those
-- rows unambiguously because real batch children always point to a batch.
WITH RECURSIVE legacy_retry AS (
    SELECT child.job_id,
           parent.job_id AS retry_of_job_id,
           parent.job_id AS retry_root_job_id,
           1 AS retry_generation
    FROM sys_collection_job AS child
    JOIN sys_collection_job AS parent ON parent.job_id = child.parent_job_id
    WHERE parent.job_kind = 'leaf'
      AND parent.parent_job_id IS NULL
    UNION ALL
    SELECT child.job_id,
           parent.job_id AS retry_of_job_id,
           chain.retry_root_job_id,
           chain.retry_generation + 1
    FROM sys_collection_job AS child
    JOIN legacy_retry AS chain ON chain.job_id = child.parent_job_id
    JOIN sys_collection_job AS parent ON parent.job_id = child.parent_job_id
    WHERE chain.retry_generation < 20
)
UPDATE sys_collection_job AS child
SET retry_of_job_id = chain.retry_of_job_id,
    retry_root_job_id = chain.retry_root_job_id,
    retry_generation = chain.retry_generation
FROM legacy_retry AS chain
WHERE child.job_id = chain.job_id
  AND child.retry_of_job_id IS NULL;

CREATE INDEX IF NOT EXISTS idx_collection_job_retry_root
    ON sys_collection_job(retry_root_job_id, retry_generation, job_id)
    WHERE retry_root_job_id IS NOT NULL;

COMMENT ON COLUMN sys_collection_job.parent_job_id IS
    'Structural parent for a batch leaf; never the source of a new retry.';
COMMENT ON COLUMN sys_collection_job.retry_of_job_id IS
    'Immediately preceding execution instance explicitly retried by an operator.';
COMMENT ON COLUMN sys_collection_job.retry_root_job_id IS
    'First failed execution instance in the manual retry lineage.';
COMMENT ON COLUMN sys_collection_job.retry_generation IS
    'Zero for the original instance; increments for each explicit retry instance.';
