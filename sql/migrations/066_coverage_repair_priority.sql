-- Confirmed coverage gaps must run before opportunistic history once the
-- market-hours gate opens. They remain isolated in the backfill pool.

UPDATE sys_collection_job
SET priority = GREATEST(priority, 95)
WHERE status = 'queued'
  AND job_kind = 'leaf'
  AND cadence = 'repair';
