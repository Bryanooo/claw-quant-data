-- Resolve obsolete fan-out plans and handler-upgrade duplicate policy jobs.

WITH replacements AS (
    SELECT DISTINCT ON (
               current.api_name, current.period_key, current.initialization_id
           )
           current.campaign_id,
           current.api_name,
           current.period_key,
           current.initialization_id
    FROM sys_collection_fanout_campaign AS current
    WHERE current.status='success'
      AND current.completion_status IN ('complete','empty')
    ORDER BY current.api_name, current.period_key, current.initialization_id,
             current.campaign_id DESC
)
UPDATE sys_collection_fanout_campaign AS obsolete
SET status='superseded', completion_status='incomplete',
    superseded_by_campaign_id=replacements.campaign_id,
    resolution_message=(
        'Automatically superseded by verified replacement campaign '
        || replacements.campaign_id
    ),
    error_message=NULL, updated_at=NOW(), finished_at=NOW()
FROM replacements
WHERE obsolete.campaign_id < replacements.campaign_id
  AND obsolete.api_name=replacements.api_name
  AND obsolete.period_key IS NOT DISTINCT FROM replacements.period_key
  AND obsolete.initialization_id IS NOT DISTINCT FROM replacements.initialization_id
  AND obsolete.status IN ('attention','paused');

WITH reusable AS (
    SELECT duplicate.job_id AS duplicate_job_id,
           verified.job_id AS verified_job_id,
           verified.rows_fetched,
           verified.rows_inserted,
           verified.completion_status,
           verified.completion_evidence
    FROM sys_collection_job AS duplicate
    JOIN LATERAL (
        SELECT candidate.*
        FROM sys_collection_job AS candidate
        WHERE candidate.job_id < duplicate.job_id
          AND candidate.task_name=duplicate.task_name
          AND COALESCE(candidate.api_name, candidate.parameters->>'api_name')=
              COALESCE(duplicate.api_name, duplicate.parameters->>'api_name')
          AND candidate.cadence=duplicate.cadence
          AND candidate.expected_for IS NOT DISTINCT FROM duplicate.expected_for
          AND candidate.period_key IS NOT DISTINCT FROM duplicate.period_key
          AND COALESCE(candidate.parameters->'parameters', '{}'::jsonb)=
              COALESCE(duplicate.parameters->'parameters', '{}'::jsonb)
          AND candidate.status='success'
          AND candidate.completion_status IN ('complete','empty')
          AND (
                COALESCE(
                  (candidate.completion_evidence->>'verified')::boolean,
                  FALSE
                )
             OR COALESCE(
                  (candidate.completion_evidence->'verification'->>'verified')::boolean,
                  FALSE
                )
          )
        ORDER BY candidate.finished_at DESC NULLS LAST, candidate.job_id DESC
        LIMIT 1
    ) AS verified ON TRUE
    WHERE duplicate.status='queued'
      AND duplicate.parent_job_id IS NULL
      AND duplicate.cadence IN ('daily','weekly','monthly','quarterly')
)
UPDATE sys_collection_job AS duplicate
SET status='success',
    completion_status=reusable.completion_status,
    rows_fetched=reusable.rows_fetched,
    rows_inserted=reusable.rows_inserted,
    completion_evidence=reusable.completion_evidence || jsonb_build_object(
        'scope_reused', TRUE,
        'reused_job_id', reusable.verified_job_id,
        'resolution', 'verified business scope survived handler upgrade'
    ),
    error_message=NULL,
    finished_at=NOW(),
    worker_id=NULL,
    lease_expires_at=NULL
FROM reusable
WHERE duplicate.job_id=reusable.duplicate_job_id;

-- Migration 045 introduced strict scheduled verification but an incorrect
-- compatibility mapping verified bak_basic_daily against stock_daily_basic.
-- Repair only jobs whose persisted fetch count exactly equals the dedicated
-- bak_basic partition; this retains the fail-closed row-cap check.
WITH exact_bak AS (
    SELECT job.job_id,
           COUNT(data.*)::INTEGER AS stored_rows,
           job.completion_evidence->'verification' AS previous_verification
    FROM sys_collection_job AS job
    JOIN bak_basic AS data
      ON data.trade_date=job.expected_for
    WHERE job.task_name='scheduled_collector'
      AND job.parameters->>'schedule_id'='bak_basic_daily'
      AND job.status='success'
      AND job.completion_status='incomplete'
      AND job.expected_for IS NOT NULL
      AND job.rows_fetched > 0
      AND job.rows_fetched < 10000
    GROUP BY job.job_id
    HAVING COUNT(data.*)=MAX(job.rows_fetched)
)
UPDATE sys_collection_job AS job
SET completion_status='complete',
    completion_evidence=job.completion_evidence || jsonb_build_object(
        'verified', TRUE,
        'verification', jsonb_build_object(
            'verified', TRUE,
            'verification_type', 'exact_persisted_partition',
            'dataset_name', 'bak_basic',
            'stored_rows', exact_bak.stored_rows,
            'expected_for', job.expected_for,
            'row_cap', 10000,
            'repair_migration', '046_scope_reuse_and_campaign_resolution',
            'previous_verification', exact_bak.previous_verification
        )
    ),
    error_message=NULL
FROM exact_bak
WHERE job.job_id=exact_bak.job_id;
