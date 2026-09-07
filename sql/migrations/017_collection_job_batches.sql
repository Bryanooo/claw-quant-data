-- Durable parent/child batches for bounded fan-out collection.
ALTER TABLE sys_collection_job
    ADD COLUMN IF NOT EXISTS job_kind VARCHAR(16) NOT NULL DEFAULT 'leaf',
    ADD COLUMN IF NOT EXISTS child_total INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS child_queued INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS child_running INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS child_succeeded INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS child_failed INTEGER NOT NULL DEFAULT 0;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'ck_collection_job_kind'
    ) THEN
        ALTER TABLE sys_collection_job
            ADD CONSTRAINT ck_collection_job_kind
            CHECK (job_kind IN ('leaf', 'batch'));
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_collection_job_parent
    ON sys_collection_job(parent_job_id, status, job_id)
    WHERE parent_job_id IS NOT NULL;

CREATE OR REPLACE FUNCTION refresh_collection_job_batch(batch_id BIGINT)
RETURNS VOID
LANGUAGE plpgsql
AS $$
DECLARE
    totals RECORD;
    final_status VARCHAR(16);
    final_completion VARCHAR(16);
BEGIN
    IF batch_id IS NULL THEN
        RETURN;
    END IF;

    SELECT
        COUNT(*)::INTEGER AS total,
        COUNT(*) FILTER (WHERE status = 'queued')::INTEGER AS queued,
        COUNT(*) FILTER (
            WHERE status = 'running'
               OR (status = 'success' AND completion_status = 'verifying')
        )::INTEGER AS running,
        COUNT(*) FILTER (WHERE status = 'success')::INTEGER AS succeeded,
        COUNT(*) FILTER (WHERE status = 'failed')::INTEGER AS failed,
        COALESCE(SUM(rows_inserted), 0)::INTEGER AS rows_inserted,
        COALESCE(SUM(rows_fetched), 0)::INTEGER AS rows_fetched,
        BOOL_OR(completion_status = 'incomplete') AS has_incomplete,
        BOOL_OR(completion_status = 'unverified') AS has_unverified,
        BOOL_AND(completion_status = 'empty') FILTER (WHERE status = 'success') AS all_empty
    INTO totals
    FROM sys_collection_job
    WHERE parent_job_id = batch_id;

    IF totals.total = 0 OR totals.queued > 0 OR totals.running > 0 THEN
        final_status := 'running';
        final_completion := 'running';
    ELSIF totals.failed > 0 THEN
        final_status := 'failed';
        final_completion := 'incomplete';
    ELSE
        final_status := 'success';
        final_completion := CASE
            WHEN totals.has_incomplete THEN 'incomplete'
            WHEN totals.has_unverified THEN 'unverified'
            WHEN totals.all_empty THEN 'empty'
            ELSE 'complete'
        END;
    END IF;

    UPDATE sys_collection_job
    SET status = final_status,
        completion_status = final_completion,
        child_total = totals.total,
        child_queued = totals.queued,
        child_running = totals.running,
        child_succeeded = totals.succeeded,
        child_failed = totals.failed,
        rows_inserted = totals.rows_inserted,
        rows_fetched = totals.rows_fetched,
        finished_at = CASE
            WHEN final_status IN ('success', 'failed') THEN NOW()
            ELSE NULL
        END,
        completion_evidence = completion_evidence || jsonb_build_object(
            'batch_state', jsonb_build_object(
                'total', totals.total,
                'queued', totals.queued,
                'running', totals.running,
                'succeeded', totals.succeeded,
                'failed', totals.failed,
                'updated_at', NOW()
            )
        )
    WHERE job_id = batch_id AND job_kind = 'batch';
END;
$$;

CREATE OR REPLACE FUNCTION trigger_refresh_collection_job_batch()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP IN ('UPDATE', 'DELETE') AND OLD.parent_job_id IS NOT NULL THEN
        PERFORM refresh_collection_job_batch(OLD.parent_job_id);
    END IF;
    IF TG_OP IN ('INSERT', 'UPDATE') AND NEW.parent_job_id IS NOT NULL
       AND (TG_OP <> 'UPDATE' OR NEW.parent_job_id IS DISTINCT FROM OLD.parent_job_id) THEN
        PERFORM refresh_collection_job_batch(NEW.parent_job_id);
    END IF;
    RETURN COALESCE(NEW, OLD);
END;
$$;

DROP TRIGGER IF EXISTS trg_refresh_collection_job_batch ON sys_collection_job;
CREATE TRIGGER trg_refresh_collection_job_batch
AFTER INSERT OR UPDATE OR DELETE ON sys_collection_job
FOR EACH ROW EXECUTE FUNCTION trigger_refresh_collection_job_batch();

