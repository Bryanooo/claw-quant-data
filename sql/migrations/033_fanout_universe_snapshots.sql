-- Freeze the exact ordered dependency universe used by a long fan-out run.
CREATE TABLE IF NOT EXISTS sys_collection_fanout_campaign_entity (
    campaign_id BIGINT NOT NULL
        REFERENCES sys_collection_fanout_campaign(campaign_id) ON DELETE CASCADE,
    entity_index INTEGER NOT NULL,
    entity_value TEXT NOT NULL,
    PRIMARY KEY (campaign_id, entity_index),
    UNIQUE (campaign_id, entity_value),
    CONSTRAINT ck_fanout_campaign_entity_index CHECK (entity_index >= 0),
    CONSTRAINT ck_fanout_campaign_entity_value CHECK (entity_value <> '')
);

CREATE INDEX IF NOT EXISTS idx_fanout_campaign_entity_value
    ON sys_collection_fanout_campaign_entity(campaign_id, entity_value);

ALTER TABLE sys_collection_fanout_campaign
    ADD COLUMN IF NOT EXISTS cadence VARCHAR(16) NOT NULL DEFAULT 'backfill',
    ADD COLUMN IF NOT EXISTS period_key VARCHAR(32),
    ADD COLUMN IF NOT EXISTS expected_for DATE;

ALTER TABLE sys_collection_fanout_campaign
    ADD CONSTRAINT ck_fanout_campaign_cadence CHECK (
        cadence IN (
            'backfill', 'initialization', 'daily', 'weekly',
            'monthly', 'quarterly'
        )
    );

CREATE INDEX IF NOT EXISTS idx_fanout_campaign_period
    ON sys_collection_fanout_campaign(api_name, cadence, period_key, created_at DESC);

COMMENT ON TABLE sys_collection_fanout_campaign_entity IS
    'Immutable ordered dependency-universe snapshot for one fan-out campaign';
COMMENT ON COLUMN sys_collection_fanout_campaign.completed_offset IS
    'Exclusive entity cursor verified complete against the frozen campaign universe';
