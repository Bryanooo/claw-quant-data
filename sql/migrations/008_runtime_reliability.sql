-- Process heartbeats and query paths used by operational health checks.

CREATE TABLE IF NOT EXISTS sys_service_heartbeat (
    component       VARCHAR(32) NOT NULL,
    instance_id     VARCHAR(128) NOT NULL,
    process_id      INTEGER,
    last_seen_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    details         JSONB NOT NULL DEFAULT '{}'::jsonb,
    PRIMARY KEY (component, instance_id),
    CONSTRAINT ck_service_heartbeat_component
        CHECK (component IN ('scheduler', 'worker', 'auditor'))
);

CREATE INDEX IF NOT EXISTS idx_service_heartbeat_latest
    ON sys_service_heartbeat(component, last_seen_at DESC);

CREATE INDEX IF NOT EXISTS idx_tushare_raw_record_api_last_seen
    ON tushare_raw_record(api_name, last_seen_at DESC);

COMMENT ON TABLE sys_service_heartbeat IS
    'Last database-backed liveness signal emitted by each non-HTTP service instance';
