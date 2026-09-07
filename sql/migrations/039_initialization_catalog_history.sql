-- Insert the durable catalog-history phase between finance and latest baselines.
-- Phase numbers are persisted, so upgrades must move existing campaigns and
-- their steps atomically instead of silently routing them to another planner.
UPDATE sys_collection_initialization_step
SET phase = phase + 1
WHERE phase >= 3;

UPDATE sys_collection_initialization
SET current_phase = current_phase + 1,
    updated_at = NOW()
WHERE current_phase >= 3;
