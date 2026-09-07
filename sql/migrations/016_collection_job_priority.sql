-- Prevent long manual/backfill jobs from delaying time-sensitive market data.
ALTER TABLE sys_collection_job
    ADD COLUMN IF NOT EXISTS priority SMALLINT NOT NULL DEFAULT 50,
    ADD COLUMN IF NOT EXISTS resource_class VARCHAR(32) NOT NULL DEFAULT 'default';

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'ck_collection_job_priority'
    ) THEN
        ALTER TABLE sys_collection_job
            ADD CONSTRAINT ck_collection_job_priority
            CHECK (priority BETWEEN 0 AND 100);
    END IF;
END $$;

DROP INDEX IF EXISTS idx_collection_job_queue;
CREATE INDEX idx_collection_job_queue
    ON sys_collection_job(status, available_at, priority DESC, created_at);
