-- Align the derived monthly partition with DateStorage.MONTH.  TEXT is used
-- by the other YYYYMM/quarter normalized datasets and keeps range predicates
-- consistent while the primary key continues to enforce one row per month.
ALTER TABLE ggt_monthly
    ALTER COLUMN month TYPE TEXT USING month::TEXT;
