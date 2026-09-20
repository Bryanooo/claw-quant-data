-- Replace the source/day news plan with a resumable adaptive source/window plan.
-- Superseded is a neutral terminal state: it is neither a successful data
-- proof nor an operational failure.

ALTER TABLE sys_collection_job
    DROP CONSTRAINT IF EXISTS ck_collection_job_status;
ALTER TABLE sys_collection_job
    ADD CONSTRAINT ck_collection_job_status
    CHECK (status IN ('queued', 'running', 'success', 'failed', 'superseded'));

ALTER TABLE sys_collection_job
    DROP CONSTRAINT IF EXISTS ck_collection_job_completion_status;
ALTER TABLE sys_collection_job
    ADD CONSTRAINT ck_collection_job_completion_status CHECK (
        completion_status IN (
            'pending', 'running', 'retrying', 'complete', 'empty',
            'verifying', 'unverified', 'page_complete', 'incomplete', 'failed',
            'superseded'
        )
    );

CREATE TABLE IF NOT EXISTS sys_major_news_window_checkpoint (
    source          VARCHAR(64) NOT NULL,
    window_start    TIMESTAMP NOT NULL,
    window_end      TIMESTAMP NOT NULL,
    status          VARCHAR(16) NOT NULL,
    rows_fetched    INTEGER NOT NULL DEFAULT 0,
    rows_stored     INTEGER NOT NULL DEFAULT 0,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (source, window_start, window_end),
    CONSTRAINT ck_major_news_checkpoint_window CHECK (window_start <= window_end),
    CONSTRAINT ck_major_news_checkpoint_status CHECK (status IN ('split', 'complete')),
    CONSTRAINT ck_major_news_checkpoint_rows CHECK (
        rows_fetched >= 0 AND rows_stored >= 0
    )
);

CREATE INDEX IF NOT EXISTS idx_major_news_checkpoint_status
    ON sys_major_news_window_checkpoint(status, updated_at);

CREATE OR REPLACE FUNCTION refresh_collection_job_batch(batch_id BIGINT)
RETURNS VOID
LANGUAGE plpgsql
AS $$
DECLARE
    totals RECORD;
    final_status VARCHAR(16);
    final_completion VARCHAR(16);
    batch_parameters JSONB;
    universe_complete BOOLEAN;
    final_verified BOOLEAN;
BEGIN
    IF batch_id IS NULL THEN
        RETURN;
    END IF;

    SELECT parameters INTO batch_parameters
    FROM sys_collection_job
    WHERE job_id=batch_id AND job_kind='batch';
    IF NOT FOUND THEN
        RETURN;
    END IF;

    universe_complete := CASE
        WHEN batch_parameters ? 'plan' THEN
            COALESCE((batch_parameters->'plan'->>'entity_offset')::INTEGER,0)=0
            AND NOT COALESCE(
                (batch_parameters->'plan'->>'has_more')::BOOLEAN,TRUE
            )
            AND COALESCE(
                (batch_parameters->'plan'->>'entities_selected')::INTEGER,0
            ) = COALESCE(
                (batch_parameters->'plan'->>'universe_total')::INTEGER,-1
            )
        ELSE TRUE
    END;

    SELECT COUNT(*)::INTEGER AS total,
           COUNT(*) FILTER (WHERE status='queued')::INTEGER AS queued,
           COUNT(*) FILTER (
               WHERE status='running'
                  OR (status='success' AND completion_status='verifying')
           )::INTEGER AS running,
           COUNT(*) FILTER (WHERE status='success')::INTEGER AS succeeded,
           COUNT(*) FILTER (WHERE status='failed')::INTEGER AS failed,
           COUNT(*) FILTER (WHERE status='superseded')::INTEGER AS superseded,
           COALESCE(SUM(rows_inserted),0)::INTEGER AS rows_inserted,
           COALESCE(SUM(rows_fetched),0)::INTEGER AS rows_fetched,
           BOOL_OR(completion_status='incomplete') AS has_incomplete,
           BOOL_OR(completion_status='unverified') AS has_unverified,
           BOOL_AND(completion_status='empty')
               FILTER (WHERE status='success') AS all_empty,
           BOOL_AND(COALESCE(
               (completion_evidence->>'verified')::BOOLEAN,FALSE
           )) FILTER (WHERE status='success') AS all_verified
    INTO totals
    FROM sys_collection_job
    WHERE parent_job_id=batch_id;

    IF totals.total=0 OR totals.queued>0 OR totals.running>0 THEN
        final_status := 'running';
        final_completion := 'running';
    ELSIF totals.superseded>0 THEN
        final_status := 'superseded';
        final_completion := 'superseded';
    ELSIF totals.failed>0 THEN
        final_status := 'failed';
        final_completion := 'incomplete';
    ELSE
        final_status := 'success';
        final_completion := CASE
            WHEN totals.has_incomplete THEN 'incomplete'
            WHEN totals.has_unverified THEN 'unverified'
            WHEN NOT universe_complete THEN 'page_complete'
            WHEN totals.all_empty THEN 'empty'
            ELSE 'complete'
        END;
    END IF;

    final_verified := final_status='success'
        AND final_completion IN ('complete','empty')
        AND universe_complete
        AND COALESCE(totals.all_verified,FALSE);

    UPDATE sys_collection_job
    SET status=final_status, completion_status=final_completion,
        child_total=totals.total, child_queued=totals.queued,
        child_running=totals.running, child_succeeded=totals.succeeded,
        child_failed=totals.failed, rows_inserted=totals.rows_inserted,
        rows_fetched=totals.rows_fetched,
        finished_at=CASE
            WHEN final_status IN ('success','failed','superseded') THEN NOW()
            ELSE NULL
        END,
        completion_evidence=completion_evidence || jsonb_build_object(
            'verified',final_verified,
            'universe_complete',universe_complete,
            'batch_state',jsonb_build_object(
                'total',totals.total,'queued',totals.queued,
                'running',totals.running,'succeeded',totals.succeeded,
                'failed',totals.failed,'superseded',totals.superseded,
                'verified',final_verified,
                'universe_complete',universe_complete,'updated_at',NOW()
            )
        )
    WHERE job_id=batch_id AND job_kind='batch';
END;
$$;
CREATE OR REPLACE FUNCTION trigger_refresh_collection_job_batch()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    old_parent_superseded BOOLEAN := FALSE;
    new_parent_superseded BOOLEAN := FALSE;
BEGIN
    IF TG_OP IN ('UPDATE', 'DELETE') AND OLD.parent_job_id IS NOT NULL THEN
        SELECT status='superseded' INTO old_parent_superseded
        FROM sys_collection_job WHERE job_id=OLD.parent_job_id;
        IF NOT COALESCE(old_parent_superseded,FALSE) THEN
            PERFORM refresh_collection_job_batch(OLD.parent_job_id);
        END IF;
    END IF;
    IF TG_OP IN ('INSERT', 'UPDATE') AND NEW.parent_job_id IS NOT NULL
       AND (TG_OP <> 'UPDATE' OR NEW.parent_job_id IS DISTINCT FROM OLD.parent_job_id) THEN
        SELECT status='superseded' INTO new_parent_superseded
        FROM sys_collection_job WHERE job_id=NEW.parent_job_id;
        IF NOT COALESCE(new_parent_superseded,FALSE) THEN
            PERFORM refresh_collection_job_batch(NEW.parent_job_id);
        END IF;
    END IF;
    RETURN COALESCE(NEW, OLD);
END;
$$;
