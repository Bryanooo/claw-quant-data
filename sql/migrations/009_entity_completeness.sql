-- Add cross-sectional completeness evidence to date-partition audits.

ALTER TABLE sys_data_coverage_audit
    ADD COLUMN IF NOT EXISTS partial_partitions INTEGER NOT NULL DEFAULT 0;

ALTER TABLE sys_data_coverage_partition
    ADD COLUMN IF NOT EXISTS expected_entity_count BIGINT,
    ADD COLUMN IF NOT EXISTS entity_coverage_ratio NUMERIC(10, 6);

ALTER TABLE sys_data_coverage_partition
    DROP CONSTRAINT IF EXISTS ck_data_coverage_partition_status;
ALTER TABLE sys_data_coverage_partition
    ADD CONSTRAINT ck_data_coverage_partition_status
    CHECK (status IN ('present', 'partial', 'missing', 'pending', 'observed_only'));
