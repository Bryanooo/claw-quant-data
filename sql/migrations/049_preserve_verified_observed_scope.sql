-- Observed-only coverage describes the absence of a trustworthy global
-- expected-date calendar. It must not downgrade an independently verified,
-- exact collection scope to unverified.
UPDATE sys_collection_job
SET completion_status = 'complete'
WHERE status = 'success'
  AND completion_status = 'unverified'
  AND COALESCE((completion_evidence->>'verified')::boolean, false)
  AND completion_evidence->'verification'->>'status' = 'observed_only';
