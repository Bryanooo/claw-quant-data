-- Reliability fixes for existing PostgreSQL volumes.

ALTER TABLE stock_basic
    ALTER COLUMN industry TYPE TEXT,
    ALTER COLUMN fullname TYPE TEXT,
    ALTER COLUMN enname TYPE TEXT,
    ALTER COLUMN act_name TYPE TEXT,
    ALTER COLUMN act_ent_type TYPE TEXT;

ALTER TABLE stock_company
    ALTER COLUMN chairman TYPE TEXT,
    ALTER COLUMN manager TYPE TEXT,
    ALTER COLUMN secretary TYPE TEXT,
    ALTER COLUMN province TYPE TEXT,
    ALTER COLUMN city TYPE TEXT;

ALTER TABLE stock_st ADD COLUMN IF NOT EXISTS pub_date DATE;
ALTER TABLE stock_st ADD COLUMN IF NOT EXISTS imp_date DATE;
ALTER TABLE stock_st ADD COLUMN IF NOT EXISTS st_type VARCHAR(32);
ALTER TABLE stock_st ADD COLUMN IF NOT EXISTS st_reason TEXT;
ALTER TABLE stock_st ADD COLUMN IF NOT EXISTS st_explain TEXT;

DO $$
DECLARE
    current_columns TEXT[];
BEGIN
    SELECT array_agg(att.attname ORDER BY key_col.ordinality)
      INTO current_columns
      FROM pg_constraint con
      CROSS JOIN LATERAL unnest(con.conkey) WITH ORDINALITY AS key_col(attnum, ordinality)
      JOIN pg_attribute att
        ON att.attrelid = con.conrelid AND att.attnum = key_col.attnum
     WHERE con.conrelid = 'stk_holdertrade'::regclass
       AND con.contype = 'p';

    IF current_columns IS DISTINCT FROM ARRAY['ts_code', 'ann_date', 'holder_name'] THEN
        DELETE FROM stk_holdertrade old_row
         USING stk_holdertrade keep_row
         WHERE old_row.ctid < keep_row.ctid
           AND old_row.ts_code = keep_row.ts_code
           AND old_row.ann_date = keep_row.ann_date
           AND old_row.holder_name = keep_row.holder_name;

        ALTER TABLE stk_holdertrade DROP CONSTRAINT IF EXISTS stk_holdertrade_pkey;
        ALTER TABLE stk_holdertrade ALTER COLUMN begin_date DROP NOT NULL;
        ALTER TABLE stk_holdertrade
            ADD CONSTRAINT stk_holdertrade_pkey
            PRIMARY KEY (ts_code, ann_date, holder_name);
    ELSE
        ALTER TABLE stk_holdertrade ALTER COLUMN begin_date DROP NOT NULL;
    END IF;
END $$;
