-- Remove order-dependent index/board schemas and normalize partition dates.

ALTER TABLE ths_daily
    ADD COLUMN IF NOT EXISTS total_mv NUMERIC(18,2),
    ADD COLUMN IF NOT EXISTS float_mv NUMERIC(18,2);
ALTER TABLE ths_member
    ADD COLUMN IF NOT EXISTS weight NUMERIC(8,3),
    ADD COLUMN IF NOT EXISTS in_date DATE,
    ADD COLUMN IF NOT EXISTS out_date DATE,
    ADD COLUMN IF NOT EXISTS is_new VARCHAR(4);

ALTER TABLE index_daily
    ALTER COLUMN trade_date TYPE DATE
    USING CASE WHEN trade_date::text ~ '^[0-9]{8}$'
        THEN to_date(trade_date::text, 'YYYYMMDD') ELSE trade_date::text::date END;
ALTER TABLE index_weekly
    ALTER COLUMN trade_date TYPE DATE
    USING CASE WHEN trade_date::text ~ '^[0-9]{8}$'
        THEN to_date(trade_date::text, 'YYYYMMDD') ELSE trade_date::text::date END;
ALTER TABLE index_monthly
    ALTER COLUMN trade_date TYPE DATE
    USING CASE WHEN trade_date::text ~ '^[0-9]{8}$'
        THEN to_date(trade_date::text, 'YYYYMMDD') ELSE trade_date::text::date END;
ALTER TABLE index_dailybasic
    ALTER COLUMN trade_date TYPE DATE
    USING CASE WHEN trade_date::text ~ '^[0-9]{8}$'
        THEN to_date(trade_date::text, 'YYYYMMDD') ELSE trade_date::text::date END;
ALTER TABLE index_global
    ALTER COLUMN trade_date TYPE DATE
    USING CASE WHEN trade_date::text ~ '^[0-9]{8}$'
        THEN to_date(trade_date::text, 'YYYYMMDD') ELSE trade_date::text::date END;
ALTER TABLE ths_daily
    ALTER COLUMN trade_date TYPE DATE
    USING CASE WHEN trade_date::text ~ '^[0-9]{8}$'
        THEN to_date(trade_date::text, 'YYYYMMDD') ELSE trade_date::text::date END;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'ths_member' AND column_name = 'in_date'
          AND data_type <> 'date'
    ) THEN
        ALTER TABLE ths_member ALTER COLUMN in_date TYPE DATE
            USING to_date(NULLIF(in_date::text, ''), 'YYYYMMDD');
    END IF;
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'ths_member' AND column_name = 'out_date'
          AND data_type <> 'date'
    ) THEN
        ALTER TABLE ths_member ALTER COLUMN out_date TYPE DATE
            USING to_date(NULLIF(out_date::text, ''), 'YYYYMMDD');
    END IF;
END $$;
