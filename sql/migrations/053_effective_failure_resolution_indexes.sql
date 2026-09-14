-- Keep effective failure/recovery projections fast as the immutable execution
-- ledger grows. These indexes match the shared resolution predicate used by
-- the health centre and the execution-record API.
CREATE INDEX IF NOT EXISTS idx_collection_job_success_expected_scope
    ON sys_collection_job(
        (COALESCE(api_name, parameters->>'api_name')),
        expected_for,
        job_id
    )
    WHERE status='success' AND job_kind='leaf'
      AND expected_for IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_collection_job_success_period_scope
    ON sys_collection_job(
        (COALESCE(api_name, parameters->>'api_name')),
        period_key,
        job_id
    )
    WHERE status='success' AND job_kind='leaf'
      AND period_key IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_collection_job_failure_history
    ON sys_collection_job(job_id DESC)
    WHERE status='failed'
       OR completion_status IN ('failed','incomplete');

CREATE INDEX IF NOT EXISTS idx_fanout_campaign_completed_request
    ON sys_collection_fanout_campaign
    USING GIN(request jsonb_path_ops)
    WHERE status='success' AND completion_status='complete';
