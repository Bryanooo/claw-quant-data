-- V2 is the only orchestration owner from the 2026-09-29 cutover onward.
-- Business tables, strict coverage evidence, raw request evidence and provider
-- checkpoints are deliberately retained; only the V1 task-control plane and
-- its execution ledger are removed.

ALTER TABLE sys_data_coverage_job
    DROP CONSTRAINT IF EXISTS sys_data_coverage_job_collection_job_id_fkey;
ALTER TABLE sys_data_coverage_job
    DROP COLUMN IF EXISTS collection_job_id;

DROP TABLE IF EXISTS sys_collection_initialization_step;
DROP TABLE IF EXISTS sys_collection_runtime_state;
DROP TABLE IF EXISTS sys_collection_schedule_cursor;
DROP TABLE IF EXISTS sys_collection_fanout_campaign_batch;
DROP TABLE IF EXISTS sys_collection_fanout_campaign_entity;
DROP TABLE IF EXISTS sys_collection_delivery_plan;
DROP TABLE IF EXISTS sys_collection_job_attempt;
DROP TABLE IF EXISTS sys_collection_job;
DROP TABLE IF EXISTS sys_collection_fanout_campaign;
DROP TABLE IF EXISTS sys_collection_initialization;
DROP TABLE IF EXISTS sys_collector_run;
