-- Do not materialize all historical BSE matches in the anti-join when a
-- caller asks for a small date range. Keep the lookup tied to the outer row.
SET LOCAL lock_timeout='3s';
DO $$
DECLARE cols text;
BEGIN
 SELECT string_agg(CASE WHEN attname='ts_code' THEN 'a.canonical_code AS ts_code'
                       ELSE format('f.%I',attname) END,', ' ORDER BY attnum)
 INTO cols FROM pg_attribute WHERE attrelid='stk_factor_pro'::regclass AND attnum>0 AND NOT attisdropped;
 EXECUTE 'CREATE OR REPLACE VIEW canonical_stk_factor_pro AS
 SELECT f.*,f.ts_code AS provider_ts_code FROM stk_factor_pro f
 WHERE CASE WHEN f.ts_code LIKE ''%.BJ'' THEN NOT EXISTS (
 SELECT 1 FROM stk_factor_pro_verified_alias a WHERE a.provider_code=f.ts_code
 AND a.trade_date=f.trade_date OFFSET 0) ELSE true END
 UNION ALL SELECT ' || cols || ',f.ts_code FROM stk_factor_pro_verified_alias a
 JOIN stk_factor_pro f ON f.ts_code=a.provider_code AND f.trade_date=a.trade_date';
END $$;
