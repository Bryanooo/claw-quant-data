-- Make the automatic PostgreSQL backup sidecar visible in the same operational
-- heartbeat stream as Scheduler, Workers and Auditor.

ALTER TABLE sys_service_heartbeat
    DROP CONSTRAINT IF EXISTS ck_service_heartbeat_component;

ALTER TABLE sys_service_heartbeat
    ADD CONSTRAINT ck_service_heartbeat_component CHECK (
        component IN (
            'scheduler', 'worker', 'worker-fanout', 'worker-backfill',
            'auditor', 'backup'
        )
    );
