-- Interface registry for the control plane.
--
-- The "data dependencies" console compiles its interface inventory from
-- docs/tushare/contracts.json plus the in-code SOURCE_REGISTRY and blueprint
-- catalogs.  That makes the authoritative interface list (title, category,
-- asset class, cadence, status, associated tasks/datasets/tables) impossible to
-- query, diff, or audit from the database.  This table persists the compiled
-- static contract; the code compiler remains the writer, never the reader, so
-- the console can read one truthful view straight from the control plane.
--
-- ``payload`` holds the compiler's full per-interface row verbatim (including
-- source-specific columns such as financial_data equivalence routes and public
-- endpoint capabilities); the typed columns mirror the fields the console
-- filters and sorts on, so reads stay indexable without denormalising the
-- whole compiler output.

CREATE TABLE IF NOT EXISTS orchestration_v2.interface_registry (
    interface_registry_id BIGSERIAL PRIMARY KEY,
    source_id             VARCHAR(64) NOT NULL
                          REFERENCES public.sys_data_source(source_id),
    interface_key         VARCHAR(128) NOT NULL,
    title                 TEXT,
    category              TEXT,
    asset_class           VARCHAR(32),
    status                VARCHAR(32) NOT NULL,
    cadence               VARCHAR(32),
    field_count           INTEGER,
    payload               JSONB NOT NULL DEFAULT '{}'::jsonb,
    synced_at             TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_orchestration_v2_interface_registry
        UNIQUE (source_id, interface_key),
    CONSTRAINT ck_orchestration_v2_interface_registry_key CHECK (
        interface_key ~ '^[A-Za-z][A-Za-z0-9_.:/-]{0,126}$'
    )
);

CREATE INDEX IF NOT EXISTS idx_orchestration_v2_interface_registry_class
    ON orchestration_v2.interface_registry(asset_class, status);
CREATE INDEX IF NOT EXISTS idx_orchestration_v2_interface_registry_source
    ON orchestration_v2.interface_registry(source_id, interface_key);

COMMENT ON TABLE orchestration_v2.interface_registry IS
    'Persisted interface inventory (static contract): title, category, asset class, cadence, status, and the compiler''s full per-interface payload. Written by scripts/sync_interface_registry.py; never authoritative over the compiler.';
