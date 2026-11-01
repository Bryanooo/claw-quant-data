-- Keep formula-version metadata, but retain only one official value vector
-- per security and trade date once local-272-v4 exists for that date.
-- Older values were temporary migration outputs and are not public supply.

DELETE FROM local_factor_validation AS legacy
WHERE legacy.schema_version <> 'local-272-v4'
  AND EXISTS (
      SELECT 1
      FROM local_factor_validation AS current
      WHERE current.schema_version = 'local-272-v4'
        AND current.trade_date = legacy.trade_date
  );

DELETE FROM local_factor_snapshot AS legacy
WHERE legacy.schema_version <> 'local-272-v4'
  AND EXISTS (
      SELECT 1
      FROM local_factor_snapshot AS current
      WHERE current.schema_version = 'local-272-v4'
        AND current.trade_date = legacy.trade_date
  );
