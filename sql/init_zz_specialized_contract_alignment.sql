-- Keep a brand-new database at the same final contract as an upgraded one.
-- The migration is idempotent: scripts/migrate.py will execute it once more to
-- register its checksum in sys_schema_migration.
\ir migrations/029_specialized_contract_alignment.sql
