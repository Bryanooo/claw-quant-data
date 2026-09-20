-- Preserve every independent broker report forecast and reports which do not
-- contain a forecast quarter.  The old (ts_code, report_date, quarter) key
-- collapsed rows from different brokers and made a nullable upstream field
-- mandatory.

ALTER TABLE report_rc
    ADD COLUMN IF NOT EXISTS source_key VARCHAR(32);

UPDATE report_rc
SET source_key = md5(concat_ws(
    chr(31),
    coalesce(nullif(btrim(ts_code), ''), '<NULL>'),
    report_date::text,
    coalesce(nullif(btrim(report_title), ''), '<NULL>'),
    coalesce(nullif(btrim(org_name), ''), '<NULL>'),
    coalesce(nullif(btrim(author_name), ''), '<NULL>'),
    coalesce(nullif(btrim(quarter), ''), '<NULL>')
))
WHERE source_key IS NULL;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conrelid = 'report_rc'::regclass
          AND conname = 'report_rc_pkey'
    ) THEN
        ALTER TABLE report_rc DROP CONSTRAINT report_rc_pkey;
    END IF;
END
$$;

ALTER TABLE report_rc
    ALTER COLUMN quarter DROP NOT NULL;

ALTER TABLE report_rc
    ALTER COLUMN source_key SET NOT NULL;

ALTER TABLE report_rc
    ADD CONSTRAINT report_rc_pkey PRIMARY KEY (source_key);

COMMENT ON COLUMN report_rc.source_key IS
    'MD5 identity of stock, report date/title, broker, authors and forecast quarter';
