-- A successful page of a fan-out universe is not proof that the whole
-- universe was collected. Keep execution status successful, but report the
-- parent as incomplete until one batch covers offset 0 through the end.
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
    IF batch_id IS NULL THEN
        RETURN;
    END IF;

    SELECT parameters INTO batch_parameters
    FROM sys_collection_job
    WHERE job_id = batch_id AND job_kind = 'batch';

    IF batch_parameters IS NULL THEN
        RETURN;
    END IF;

    universe_complete := CASE
        WHEN batch_parameters ? 'plan' THEN
            COALESCE((batch_parameters->'plan'->>'entity_offset')::INTEGER, 0) = 0
            AND NOT COALESCE(
                (batch_parameters->'plan'->>'has_more')::BOOLEAN,
                TRUE
            )
            AND COALESCE(
                (batch_parameters->'plan'->>'entities_selected')::INTEGER,
                0
            ) = COALESCE(
                (batch_parameters->'plan'->>'universe_total')::INTEGER,
                -1
            )
        ELSE TRUE
    END;

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
        BOOL_AND(completion_status = 'empty') FILTER (WHERE status = 'success') AS all_empty,
        BOOL_AND(
            COALESCE((completion_evidence->>'verified')::BOOLEAN, FALSE)
        ) FILTER (WHERE status = 'success') AS all_verified
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
            WHEN NOT universe_complete THEN 'incomplete'
            WHEN totals.has_incomplete THEN 'incomplete'
            WHEN totals.has_unverified THEN 'unverified'
            WHEN totals.all_empty THEN 'empty'
            ELSE 'complete'
        END;
    END IF;

    final_verified := (
        final_status = 'success'
        AND final_completion IN ('complete', 'empty')
        AND universe_complete
        AND COALESCE(totals.all_verified, FALSE)
    );

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
            'verified', final_verified,
            'universe_complete', universe_complete,
            'batch_state', jsonb_build_object(
                'total', totals.total,
                'queued', totals.queued,
                'running', totals.running,
                'succeeded', totals.succeeded,
                'failed', totals.failed,
                'verified', final_verified,
                'universe_complete', universe_complete,
                'updated_at', NOW()
            )
        )
    WHERE job_id = batch_id AND job_kind = 'batch';
END;
$$;

DO $$
DECLARE
    batch_row RECORD;
BEGIN
    FOR batch_row IN
        SELECT job_id FROM sys_collection_job WHERE job_kind = 'batch'
    LOOP
        PERFORM refresh_collection_job_batch(batch_row.job_id);
    END LOOP;
END;
$$;
