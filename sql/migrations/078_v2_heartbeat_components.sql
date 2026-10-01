-- V2 is the only orchestration runtime.  Keep heartbeat identities explicit
-- so health checks and the dashboard cannot confuse them with retired V1
-- worker pools.
DELETE FROM sys_service_heartbeat
WHERE component IN ('worker', 'worker-fanout', 'worker-backfill');

ALTER TABLE sys_service_heartbeat
    DROP CONSTRAINT IF EXISTS ck_service_heartbeat_component;

ALTER TABLE sys_service_heartbeat
    ADD CONSTRAINT ck_service_heartbeat_component CHECK (
        component IN (
            'scheduler',
            'worker-v2-routine',
            'worker-v2-backfill',
            'auditor',
            'backup'
        )
    );
