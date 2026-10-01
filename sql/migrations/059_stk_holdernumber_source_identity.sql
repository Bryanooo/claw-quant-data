-- Preserve shareholder-count announcements whose upstream effective date is
-- NULL. The prior (ts_code, end_date) primary key rejected legitimate rows and
-- collapsed separately announced revisions for the same effective period.

ALTER TABLE stk_holdernumber
    ADD COLUMN IF NOT EXISTS source_key VARCHAR(32);

UPDATE stk_holdernumber
SET source_key = md5(concat_ws(
    chr(31),
    coalesce(nullif(btrim(ts_code), ''), '<NULL>'),
    coalesce(ann_date::text, '<NULL>'),
    coalesce(end_date::text, '<NULL>')
))
WHERE source_key IS NULL;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conrelid = 'stk_holdernumber'::regclass
          AND conname = 'stk_holdernumber_pkey'
    ) THEN
        ALTER TABLE stk_holdernumber DROP CONSTRAINT stk_holdernumber_pkey;
    END IF;
END
$$;

ALTER TABLE stk_holdernumber
    ALTER COLUMN end_date DROP NOT NULL;

ALTER TABLE stk_holdernumber
    ALTER COLUMN source_key SET NOT NULL;

ALTER TABLE stk_holdernumber
    ADD CONSTRAINT stk_holdernumber_pkey PRIMARY KEY (source_key);

CREATE INDEX IF NOT EXISTS idx_stk_holdernumber_effective_identity
    ON stk_holdernumber(ts_code, end_date DESC, ann_date DESC);

COMMENT ON COLUMN stk_holdernumber.source_key IS
    'MD5 identity of stock, announcement date and nullable effective date';
