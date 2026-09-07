-- Allow tushare_interface jobs to persist their resolved specialized collector route.
-- The snapshot prevents an existing queued job from silently changing collector type.

ALTER TABLE sys_collection_job
    DROP CONSTRAINT IF EXISTS ck_collection_job_handler_type;

ALTER TABLE sys_collection_job
    ADD CONSTRAINT ck_collection_job_handler_type CHECK (
        handler_type IS NULL OR handler_type IN ('generic', 'dedicated', 'specialized')
    );
