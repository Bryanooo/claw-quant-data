-- Add an authoritative, provider-neutral LPR source without mutating or
-- disguising Tushare rows. Raw acquisition evidence remains in the shared
-- source archive; the canonical view prefers official records by date.

CREATE TABLE IF NOT EXISTS official_lpr (
    record_hash       CHAR(64) PRIMARY KEY,
    request_hash      CHAR(64) NOT NULL,
    source_request_id BIGINT REFERENCES source_raw_request_store(request_id),
    publication_date  DATE NOT NULL UNIQUE,
    one_year          NUMERIC NOT NULL,
    five_year         NUMERIC NOT NULL,
    source_url        TEXT NOT NULL,
    raw_payload       JSONB NOT NULL DEFAULT '{}'::jsonb,
    collected_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    first_seen_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_official_lpr_collected_at
    ON official_lpr(collected_at DESC);

CREATE OR REPLACE VIEW canonical_shibor_lpr AS
WITH candidates AS (
    SELECT
        record_hash AS _record_hash,
        request_hash AS _request_hash,
        NULL::INTEGER AS _source_doc_id,
        collected_at AS _source_collected_at,
        first_seen_at AS _first_seen_at,
        last_seen_at AS _last_seen_at,
        1::INTEGER AS _schema_version,
        jsonb_build_object(
            'source_id', 'chinamoney',
            'source_request_id', source_request_id,
            'source_url', source_url,
            'authoritative', TRUE
        ) || raw_payload AS _extra_payload,
        publication_date AS date,
        one_year AS "1y",
        five_year AS "5y",
        0 AS source_priority
    FROM official_lpr
    UNION ALL
    SELECT
        _record_hash,
        _request_hash,
        _source_doc_id,
        _source_collected_at,
        _first_seen_at,
        _last_seen_at,
        _schema_version,
        jsonb_build_object('source_id', 'tushare') || _extra_payload,
        date,
        "1y",
        "5y",
        1 AS source_priority
    FROM tushare_norm_shibor_lpr
), ranked AS (
    SELECT candidates.*,
           ROW_NUMBER() OVER (
               PARTITION BY date
               ORDER BY source_priority, _source_collected_at DESC, _record_hash
           ) AS row_number
    FROM candidates
)
SELECT
    _record_hash,
    _request_hash,
    _source_doc_id,
    _source_collected_at,
    _first_seen_at,
    _last_seen_at,
    _schema_version,
    _extra_payload,
    date,
    "1y",
    "5y"
FROM ranked
WHERE row_number = 1;

COMMENT ON VIEW canonical_shibor_lpr IS
    'Provider-neutral current LPR view; official ChinaMoney rows take precedence by date';
