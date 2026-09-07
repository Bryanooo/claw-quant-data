-- Resolve obsolete fan-out plans without rewriting their failure history.
ALTER TABLE sys_collection_fanout_campaign
    ADD COLUMN IF NOT EXISTS superseded_by_campaign_id BIGINT
        REFERENCES sys_collection_fanout_campaign(campaign_id),
    ADD COLUMN IF NOT EXISTS resolution_message TEXT;

ALTER TABLE sys_collection_fanout_campaign
    DROP CONSTRAINT IF EXISTS ck_fanout_campaign_status;

ALTER TABLE sys_collection_fanout_campaign
    ADD CONSTRAINT ck_fanout_campaign_status
    CHECK (status IN ('running', 'paused', 'attention', 'success', 'superseded'));

CREATE INDEX IF NOT EXISTS idx_fanout_campaign_superseded_by
    ON sys_collection_fanout_campaign(superseded_by_campaign_id)
    WHERE superseded_by_campaign_id IS NOT NULL;

COMMENT ON COLUMN sys_collection_fanout_campaign.superseded_by_campaign_id IS
    'Successful replacement campaign that resolves this obsolete plan.';
COMMENT ON COLUMN sys_collection_fanout_campaign.resolution_message IS
    'Immutable operational explanation for a superseded campaign.';
