-- Give retired V1 backlog an explicit non-runnable state.  A far-future
-- available_at timestamp alone still appeared as an active queue in APIs and
-- dashboards, which made a stopped legacy plan look like ongoing collection.

ALTER TABLE sys_collection_job
    DROP CONSTRAINT IF EXISTS ck_collection_job_status;

ALTER TABLE sys_collection_job
    ADD CONSTRAINT ck_collection_job_status
    CHECK (status IN (
        'queued', 'running', 'paused', 'success', 'failed', 'superseded'
    ));

UPDATE sys_collection_job
SET status='paused',
    available_at='infinity'::timestamptz,
    worker_id=NULL,
    heartbeat_at=NULL,
    lease_expires_at=NULL,
    finished_at=NULL
WHERE status IN ('queued','running')
  AND COALESCE((completion_evidence->>'legacy_paused')::boolean,false)=true;

-- Leaf updates invoke the batch aggregation trigger.  Re-assert the explicit
-- pause on parent rows after that aggregation has finished.
UPDATE sys_collection_job
SET status='paused',
    available_at='infinity'::timestamptz,
    worker_id=NULL,
    heartbeat_at=NULL,
    lease_expires_at=NULL,
    finished_at=NULL
WHERE job_kind='batch'
  AND COALESCE((completion_evidence->>'legacy_paused')::boolean,false)=true;
