ALTER TABLE sys_service_heartbeat
    DROP CONSTRAINT IF EXISTS ck_service_heartbeat_component;

ALTER TABLE sys_service_heartbeat
    ADD CONSTRAINT ck_service_heartbeat_component CHECK (
        component IN (
            'scheduler',
            'worker-v2-routine',
            'worker-v2-backfill',
            'worker-v2-derived',
            'auditor',
            'backup'
        )
    );
