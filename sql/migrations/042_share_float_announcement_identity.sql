-- One holder can have multiple announcements for the same release date and
-- share type.  ``ann_date`` distinguishes those upstream rows; the previous
-- key silently merged them during upsert.
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM share_float WHERE ann_date IS NULL) THEN
        RAISE EXCEPTION
            'share_float contains NULL ann_date values; refusing lossy identity migration';
    END IF;
END $$;

ALTER TABLE share_float
    ALTER COLUMN ann_date SET NOT NULL;

ALTER TABLE share_float
    DROP CONSTRAINT share_float_pkey;

ALTER TABLE share_float
    ADD CONSTRAINT share_float_pkey
    PRIMARY KEY (ts_code, ann_date, float_date, holder_name, share_type);

COMMENT ON CONSTRAINT share_float_pkey ON share_float IS
    'Upstream release-lot identity; ann_date prevents separate announcements from merging';
