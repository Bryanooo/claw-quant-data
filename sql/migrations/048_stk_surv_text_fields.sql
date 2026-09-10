-- Tushare stk_surv descriptive values are not length bounded by contract.
-- A real 2026-09-09 response contained a 70-character rece_mode value and
-- failed the previous VARCHAR(64) schema. Keep identifiers bounded, but store
-- provider-owned descriptive fields as TEXT so future valid values cannot
-- break an otherwise complete daily partition.

ALTER TABLE stk_surv
    ALTER COLUMN name TYPE TEXT,
    ALTER COLUMN fund_visitors TYPE TEXT,
    ALTER COLUMN rece_place TYPE TEXT,
    ALTER COLUMN rece_mode TYPE TEXT,
    ALTER COLUMN rece_org TYPE TEXT,
    ALTER COLUMN org_type TYPE TEXT,
    ALTER COLUMN comp_rece TYPE TEXT;
