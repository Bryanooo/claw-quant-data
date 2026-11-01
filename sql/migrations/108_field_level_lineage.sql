-- Field-level lineage for the control plane.
--
-- The control plane already answered "which dataset does this task produce"
-- and never answered "which interface column produced this table column".
-- That question is currently answered only by a code-compiled snapshot, so it
-- cannot be queried, diffed or audited.  This table persists the compiled
-- mapping; the code compiler remains the writer, not the reader.

CREATE TABLE IF NOT EXISTS orchestration_v2.field_lineage (
    field_lineage_id BIGSERIAL PRIMARY KEY,
    source_id        VARCHAR(64) NOT NULL
                     REFERENCES public.sys_data_source(source_id),
    table_name       VARCHAR(128) NOT NULL,
    field_name       VARCHAR(128) NOT NULL,
    interface_key    VARCHAR(128) NOT NULL,
    field_type       TEXT,
    description      TEXT,
    synced_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_orchestration_v2_field_lineage
        UNIQUE (source_id, table_name, field_name, interface_key),
    CONSTRAINT ck_orchestration_v2_field_lineage_table CHECK (
        table_name ~ '^[a-z][a-z0-9_.]{0,126}$'
    ),
    CONSTRAINT ck_orchestration_v2_field_lineage_field CHECK (
        field_name ~ '^[a-z][a-z0-9_.]{0,126}$'
    ),
    CONSTRAINT ck_orchestration_v2_field_lineage_interface CHECK (
        interface_key ~ '^[A-Za-z][A-Za-z0-9_.:/-]{0,126}$'
    )
);

CREATE INDEX IF NOT EXISTS idx_orchestration_v2_field_lineage_table
    ON orchestration_v2.field_lineage(table_name, field_name);
CREATE INDEX IF NOT EXISTS idx_orchestration_v2_field_lineage_interface
    ON orchestration_v2.field_lineage(interface_key, table_name);

COMMENT ON TABLE orchestration_v2.field_lineage IS
    'Persisted field-level lineage: one row per physical column and the interface that supplies it. Written by scripts/sync_field_lineage.py; never authoritative over the compiler.';
