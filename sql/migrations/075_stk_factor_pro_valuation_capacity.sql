-- Tushare uses large finite valuation values (for example
-- 999999999.99999) when a ratio denominator is close to zero.  These are
-- provider values, not transport corruption, and NUMERIC(12,4) both
-- overflowed and discarded precision during historical repair.

ALTER TABLE stk_factor_pro
    ALTER COLUMN pe TYPE NUMERIC(20,6),
    ALTER COLUMN pe_ttm TYPE NUMERIC(20,6),
    ALTER COLUMN pb TYPE NUMERIC(20,6),
    ALTER COLUMN ps TYPE NUMERIC(20,6),
    ALTER COLUMN ps_ttm TYPE NUMERIC(20,6),
    ALTER COLUMN dv_ratio TYPE NUMERIC(20,6),
    ALTER COLUMN dv_ttm TYPE NUMERIC(20,6);
