-- Historical leaves are durable and resumable, but three attempts can be
-- exhausted by a short DNS/provider outage. Keep routine jobs unchanged while
-- giving active historical work enough bounded retry budget to self-heal.

UPDATE sys_collection_job
SET max_attempts = GREATEST(max_attempts, 8)
WHERE status IN ('queued', 'running')
  AND job_kind = 'leaf'
  AND cadence IN ('backfill', 'initialization', 'repair');
