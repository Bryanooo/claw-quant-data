-- No business rows are copied or overwritten. A code mapping is accepted
-- only for a day with a matching OHLC bar and no competing identity.
SET LOCAL lock_timeout='3s';
CREATE VIEW stk_factor_pro_verified_alias AS
 SELECT f.trade_date, m.o_code AS provider_code, m.n_code AS canonical_code
 FROM bse_mapping m
 JOIN stk_factor_pro f ON f.ts_code=m.o_code
 JOIN daily d ON d.ts_code=m.n_code AND d.trade_date=f.trade_date
             AND (d.open,d.high,d.low,d.close)=(f.open,f.high,f.low,f.close)
 WHERE m.n_code LIKE '%.BJ' AND m.o_code LIKE '%.BJ' AND m.n_code<>m.o_code
   AND m.list_date<=f.trade_date
   AND NOT EXISTS(SELECT 1 FROM bse_mapping other WHERE other.n_code=m.n_code AND other.o_code<>m.o_code)
   AND NOT EXISTS(SELECT 1 FROM daily old WHERE old.ts_code=m.o_code AND old.trade_date=f.trade_date)
   AND NOT EXISTS(SELECT 1 FROM stk_factor_pro direct WHERE direct.ts_code=m.n_code AND direct.trade_date=f.trade_date);

-- Keep raw rows addressable in stk_factor_pro; the canonical read has exactly
-- one row per raw row and exposes the original provider code for lineage.
DO $$
DECLARE columns_sql text;
BEGIN
 SELECT string_agg(CASE WHEN attname='ts_code' THEN 'a.canonical_code AS ts_code'
                       ELSE format('f.%I',attname) END,', ' ORDER BY attnum)
 INTO columns_sql FROM pg_attribute WHERE attrelid='stk_factor_pro'::regclass
 AND attnum>0 AND NOT attisdropped;
 EXECUTE format('CREATE VIEW canonical_stk_factor_pro AS
   SELECT f.*,f.ts_code AS provider_ts_code FROM stk_factor_pro f
   WHERE NOT EXISTS (SELECT 1 FROM stk_factor_pro_verified_alias a WHERE
     a.provider_code=f.ts_code AND a.trade_date=f.trade_date)
   UNION ALL SELECT %s,f.ts_code FROM stk_factor_pro_verified_alias a JOIN stk_factor_pro f
     ON f.ts_code=a.provider_code AND f.trade_date=a.trade_date',columns_sql);
END $$;
