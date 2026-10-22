-- Official ChinaBond (CCDC) yield curve storage for the scheduled pull.
-- One row per (curve_date, curve_name); tenor yields are percent values as
-- published by chinabond.com.cn. Raw acquisition evidence stays in the
-- shared source archive; this table is the provider-neutral business store.

CREATE TABLE IF NOT EXISTS public_norm_chinabond_yield_curve (
    record_hash       CHAR(64) PRIMARY KEY,
    request_hash      CHAR(64) NOT NULL,
    source_request_id BIGINT REFERENCES source_raw_request_store(request_id),
    curve_date        DATE NOT NULL,
    curve_name        TEXT NOT NULL,
    yield_3m          NUMERIC,
    yield_6m          NUMERIC,
    yield_1y          NUMERIC,
    yield_3y          NUMERIC,
    yield_5y          NUMERIC,
    yield_7y          NUMERIC,
    yield_10y         NUMERIC,
    yield_30y         NUMERIC,
    source_url        TEXT NOT NULL,
    raw_payload       JSONB NOT NULL DEFAULT '{}'::jsonb,
    collected_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    first_seen_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (curve_date, curve_name)
);

CREATE INDEX IF NOT EXISTS idx_chinabond_curve_date
    ON public_norm_chinabond_yield_curve(curve_date DESC);

CREATE INDEX IF NOT EXISTS idx_chinabond_curve_collected_at
    ON public_norm_chinabond_yield_curve(collected_at DESC);
