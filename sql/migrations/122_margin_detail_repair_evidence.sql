-- Exact-key, source-attributed corrections; never infer a missing balance.
CREATE TABLE IF NOT EXISTS margin_detail_repair_evidence (
    trade_date text NOT NULL,
    ts_code text NOT NULL,
    source text NOT NULL CHECK (source IN ('tushare','eastmoney','quarantine_header')),
    before_row jsonb NOT NULL,
    replacement jsonb NOT NULL,
    provider_evidence jsonb NOT NULL,
    recorded_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (trade_date,ts_code)
);

-- Replays of the exact attested bad payload must not undo a correction.
-- A changed upstream row is *not* patched from stale evidence. In particular
-- a newly valid upstream revision wins normally. This lookup is only needed
-- for defective incoming balances, and uses the evidence primary key.
CREATE OR REPLACE FUNCTION preserve_verified_margin_detail_repair()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE certificate public.margin_detail_repair_evidence%ROWTYPE;
BEGIN
    SELECT * INTO certificate FROM public.margin_detail_repair_evidence
     WHERE trade_date = NEW.trade_date AND ts_code = NEW.ts_code;
    IF NOT FOUND OR (to_jsonb(NEW) - 'name') IS DISTINCT FROM (certificate.before_row - 'name') THEN
        RETURN NEW;
    END IF;
    IF certificate.source='quarantine_header' THEN
        RETURN NULL;
    END IF;
    -- An exact replay cannot supersede a newer, coherent source revision.
    IF EXISTS (SELECT 1 FROM public.margin_detail d WHERE d.ts_code=NEW.ts_code
        AND d.trade_date=NEW.trade_date AND d.rzye>=0 AND d.rqye>=0
        AND d.rzrqye<'Infinity'::numeric AND abs(d.rzrqye-d.rzye-d.rqye)<=0.01
        AND (d.rzye,d.rqye,d.rzrqye) IS DISTINCT FROM
            ((certificate.replacement->>'rzye')::numeric,(certificate.replacement->>'rqye')::numeric,
             (certificate.replacement->>'rzrqye')::numeric)) THEN
        RETURN NULL;
    END IF;
    NEW.rzye := (certificate.replacement->>'rzye')::numeric;
    NEW.rqye := (certificate.replacement->>'rqye')::numeric;
    NEW.rzrqye := (certificate.replacement->>'rzrqye')::numeric;
    RETURN NEW;
END $$;
CREATE TRIGGER margin_detail_exact_repair BEFORE INSERT OR UPDATE ON margin_detail
FOR EACH ROW WHEN (NEW.rzye IS NULL OR NEW.rqye IS NULL OR NEW.rzrqye IS NULL
                   OR abs(NEW.rzrqye-NEW.rzye-NEW.rqye)>0.01)
EXECUTE FUNCTION preserve_verified_margin_detail_repair();
