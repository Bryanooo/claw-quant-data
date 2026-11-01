-- Field lineage identifiers are not all letter-initial.  Provider column
-- names such as ``3day`` are legitimate, and rejecting them silently drops
-- real lineage rows from the persisted mapping.

ALTER TABLE orchestration_v2.field_lineage
    DROP CONSTRAINT IF EXISTS ck_orchestration_v2_field_lineage_table,
    DROP CONSTRAINT IF EXISTS ck_orchestration_v2_field_lineage_field,
    DROP CONSTRAINT IF EXISTS ck_orchestration_v2_field_lineage_interface;

ALTER TABLE orchestration_v2.field_lineage
    ADD CONSTRAINT ck_orchestration_v2_field_lineage_table
        CHECK (table_name ~ '^[a-z0-9][a-z0-9_.]{0,126}$'),
    ADD CONSTRAINT ck_orchestration_v2_field_lineage_field
        CHECK (field_name ~ '^[a-z0-9][a-z0-9_.]{0,126}$'),
    ADD CONSTRAINT ck_orchestration_v2_field_lineage_interface
        CHECK (interface_key ~ '^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,126}$');
