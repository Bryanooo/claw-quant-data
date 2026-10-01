-- Provider-neutral source jobs are routed through connector handlers.  The
-- multi-source foundation introduced that handler type in application code,
-- so the durable job contract must accept it as well.

ALTER TABLE sys_collection_job
    DROP CONSTRAINT IF EXISTS ck_collection_job_handler_type;

ALTER TABLE sys_collection_job
    ADD CONSTRAINT ck_collection_job_handler_type CHECK (
        handler_type IS NULL
        OR handler_type IN ('generic', 'dedicated', 'specialized', 'connector')
    );
