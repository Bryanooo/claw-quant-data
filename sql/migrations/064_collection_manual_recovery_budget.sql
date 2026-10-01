-- Automatic submission remains capped at five attempts by the API contract.
-- Operators may reopen the same durable batch child after a code/provider fix;
-- preserve its full attempt ledger while allowing bounded recovery generations.

ALTER TABLE sys_collection_job
    DROP CONSTRAINT IF EXISTS ck_collection_job_attempts;

ALTER TABLE sys_collection_job
    ADD CONSTRAINT ck_collection_job_attempts
    CHECK (attempt >= 0 AND max_attempts BETWEEN 1 AND 20);
