-- Reuse one viable fan-out campaign across backfill and routine scheduling.
ALTER TABLE sys_collection_fanout_campaign
    ADD COLUMN IF NOT EXISTS plan_version SMALLINT NOT NULL DEFAULT 1;

UPDATE sys_collection_fanout_campaign
SET plan_version = 2
WHERE api_name = 'factor_value'
  AND (
      idempotency_key LIKE '%:v2'
      OR idempotency_key LIKE '%factor-name-v2%'
  );

ALTER TABLE sys_collection_fanout_campaign
    DROP CONSTRAINT IF EXISTS ck_fanout_campaign_plan_version;

ALTER TABLE sys_collection_fanout_campaign
    ADD CONSTRAINT ck_fanout_campaign_plan_version CHECK (plan_version >= 1);

CREATE INDEX IF NOT EXISTS idx_fanout_campaign_scope
    ON sys_collection_fanout_campaign(
        api_name, period_key, expected_for, plan_version, status
    )
    WHERE period_key IS NOT NULL AND status IN ('running', 'success');

COMMENT ON COLUMN sys_collection_fanout_campaign.plan_version IS
    'Logical collector plan generation used for cross-cadence scope deduplication.';
