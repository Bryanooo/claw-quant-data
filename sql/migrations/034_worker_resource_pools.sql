-- Allow independent worker pools to publish separately observable heartbeats.
ALTER TABLE sys_service_heartbeat
    DROP CONSTRAINT IF EXISTS ck_service_heartbeat_component;

ALTER TABLE sys_service_heartbeat
    ADD CONSTRAINT ck_service_heartbeat_component CHECK (
        component IN (
            'scheduler', 'worker', 'worker-fanout', 'worker-backfill', 'auditor'
        )
    );

COMMENT ON COLUMN sys_collection_job.resource_class IS
    'Closed worker-pool routing key; priority only orders work inside an eligible pool';
