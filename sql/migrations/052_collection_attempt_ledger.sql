-- Preserve every automatic execution attempt and distinguish a completed
-- fan-out page from an incomplete logical collection.
ALTER TABLE sys_collection_job
    DROP CONSTRAINT IF EXISTS ck_collection_job_completion_status;
ALTER TABLE sys_collection_job
    ADD CONSTRAINT ck_collection_job_completion_status CHECK (
        completion_status IN (
            'pending', 'running', 'retrying', 'complete', 'empty',
            'verifying', 'unverified', 'page_complete', 'incomplete', 'failed'
        )
    );

CREATE TABLE IF NOT EXISTS sys_collection_job_attempt (
    attempt_id          BIGSERIAL PRIMARY KEY,
    job_id              BIGINT NOT NULL REFERENCES sys_collection_job(job_id)
                        ON DELETE CASCADE,
    attempt_number      SMALLINT NOT NULL,
    worker_id           VARCHAR(128),
    status              VARCHAR(24) NOT NULL,
    retryable           BOOLEAN,
    retry_after_seconds INTEGER,
    rows_fetched        INTEGER,
    rows_inserted       INTEGER NOT NULL DEFAULT 0,
    error_message       TEXT,
    evidence            JSONB NOT NULL DEFAULT '{}'::jsonb,
    started_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at         TIMESTAMPTZ,
    CONSTRAINT ck_collection_job_attempt_number CHECK (attempt_number >= 0),
    CONSTRAINT ck_collection_job_attempt_status CHECK (
        status IN (
            'running', 'success', 'retrying', 'failed', 'deferred',
            'lease_expired'
        )
    )
);
CREATE INDEX IF NOT EXISTS idx_collection_job_attempt_job
    ON sys_collection_job_attempt(job_id, attempt_id DESC);
CREATE INDEX IF NOT EXISTS idx_collection_job_attempt_running
    ON sys_collection_job_attempt(job_id, attempt_number, worker_id)
    WHERE status='running';

-- Old rows cannot reconstruct attempts that were overwritten in place. Keep
-- one explicitly marked snapshot so the API never invents missing history.
INSERT INTO sys_collection_job_attempt (
    job_id, attempt_number, worker_id, status, retryable, rows_fetched,
    rows_inserted, error_message, evidence, started_at, finished_at
)
SELECT job_id, attempt, worker_id,
       CASE status WHEN 'success' THEN 'success' WHEN 'failed' THEN 'failed'
            WHEN 'running' THEN 'running' ELSE 'deferred' END,
       CASE WHEN status='failed' THEN FALSE ELSE NULL END,
       rows_fetched, rows_inserted, error_message,
       jsonb_build_object('historical_snapshot', TRUE),
       COALESCE(started_at, created_at), finished_at
FROM sys_collection_job AS job
WHERE attempt > 0
  AND NOT EXISTS (
      SELECT 1 FROM sys_collection_job_attempt AS existing
      WHERE existing.job_id=job.job_id
  );

CREATE OR REPLACE FUNCTION refresh_collection_job_batch(batch_id BIGINT)
RETURNS VOID
LANGUAGE plpgsql
AS $$
DECLARE
    totals RECORD;
    batch_parameters JSONB;
    universe_complete BOOLEAN;
    final_status VARCHAR(16);
    final_completion VARCHAR(16);
    final_verified BOOLEAN;
BEGIN
    IF batch_id IS NULL THEN RETURN; END IF;

    SELECT parameters INTO batch_parameters
    FROM sys_collection_job
    WHERE job_id=batch_id AND job_kind='batch';
    IF batch_parameters IS NULL THEN RETURN; END IF;

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
        finished_at=CASE WHEN final_status IN ('success','failed')
                         THEN NOW() ELSE NULL END,
        completion_evidence=completion_evidence || jsonb_build_object(
            'verified',final_verified,
            'universe_complete',universe_complete,
            'batch_state',jsonb_build_object(
                'total',totals.total,'queued',totals.queued,
                'running',totals.running,'succeeded',totals.succeeded,
                'failed',totals.failed,'verified',final_verified,
                'universe_complete',universe_complete,'updated_at',NOW()
            )
        )
    WHERE job_id=batch_id AND job_kind='batch';
END;
$$;

UPDATE sys_collection_job
SET completion_status='page_complete'
WHERE job_kind='batch' AND status='success'
  AND completion_status='incomplete'
  AND child_failed=0 AND child_queued=0 AND child_running=0
  AND COALESCE(
      (completion_evidence->>'universe_complete')::BOOLEAN,FALSE
  )=FALSE;

-- Before delivery-plan generation became exchange-calendar aware, dedicated
-- cron jobs were materialized on weekends and holidays and later surfaced as
-- false overdue incidents.  Reconcile those persisted expectations against
-- the SSE calendar.  Reference snapshots still intentionally run every
-- calendar day and therefore remain in the plan.
DELETE FROM sys_collection_delivery_plan AS plan
USING trade_cal AS calendar
WHERE calendar.exchange='SSE'
  AND calendar.cal_date=plan.business_date
  AND calendar.is_open=0
  AND plan.source_type='dedicated'
  AND plan.cadence='daily'
  AND plan.source_key NOT IN ('stock_basic_daily', 'trade_cal_daily');
