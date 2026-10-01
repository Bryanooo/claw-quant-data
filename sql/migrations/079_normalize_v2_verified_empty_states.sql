-- Normalize V2 states emitted before authoritative zero-row acquisitions were
-- represented explicitly as ``empty_verified``.  The predicate is deliberately
-- strict: an execution must have a persisted verified-empty audit certificate,
-- at least one zero-row acquire event, and no acquire event that fetched rows.
-- Business tables are not modified.

UPDATE orchestration_v2.dataset_state AS state
SET data_status = 'empty_verified',
    actual_count = 0,
    validation_summary = jsonb_set(
        jsonb_set(
            state.validation_summary,
            '{audit_status}',
            '"empty"'::jsonb,
            true
        ),
        '{evidence,verified_empty_persisted}',
        'true'::jsonb,
        true
    ),
    revision = state.revision + 1,
    updated_at = NOW()
WHERE state.data_status = 'complete'
  AND state.ready
  AND state.source_execution_id IS NOT NULL
  AND jsonb_typeof(
        state.validation_summary->'evidence'->'v2_verified_empty_transport_dates'
      ) = 'array'
  AND jsonb_array_length(
        state.validation_summary->'evidence'->'v2_verified_empty_transport_dates'
      ) > 0
  AND EXISTS (
      SELECT 1
      FROM orchestration_v2.task_execution_event AS event
      WHERE event.task_execution_id = state.source_execution_id
        AND event.event_type = 'node.acquire.request_completed'
        AND COALESCE((event.payload->>'rows_fetched')::BIGINT, 0) = 0
        AND event.payload->>'completion_status' = 'empty'
        AND event.payload->'completion_evidence'->>'verified' = 'true'
  )
  AND NOT EXISTS (
      SELECT 1
      FROM orchestration_v2.task_execution_event AS event
      WHERE event.task_execution_id = state.source_execution_id
        AND event.event_type = 'node.acquire.request_completed'
        AND COALESCE((event.payload->>'rows_fetched')::BIGINT, 0) > 0
  );
