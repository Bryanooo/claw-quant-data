-- Finish separating legacy retry lineage from structural batch topology.
-- Migration 050 records the former parent link before this migration clears it.
UPDATE sys_collection_job
SET parent_job_id = NULL
WHERE retry_of_job_id IS NOT NULL
  AND parent_job_id = retry_of_job_id;
