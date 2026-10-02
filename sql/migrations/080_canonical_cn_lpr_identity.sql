-- Separate the provider transport name (Tushare ``shibor_lpr``) from the
-- provider-neutral business dataset.  The series contains LPR observations,
-- not SHIBOR, so public data, audit and orchestration identities use cn_lpr.

CREATE OR REPLACE VIEW canonical_cn_lpr AS
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

COMMENT ON VIEW canonical_cn_lpr IS
    'Provider-neutral LPR view; official ChinaMoney rows take precedence by publication date';

-- Rename current operational coverage identities.  Historical executions
-- keep their immutable task key, while the obsolete active definition is
-- retired before bootstrap publishes cn_lpr.
UPDATE sys_data_coverage_job
SET dataset_name = 'cn_lpr'
WHERE dataset_name = 'shibor_lpr';

UPDATE sys_data_coverage_audit
SET dataset_name = 'cn_lpr'
WHERE dataset_name = 'shibor_lpr';

UPDATE sys_data_coverage_partition
SET dataset_name = 'cn_lpr'
WHERE dataset_name = 'shibor_lpr';

UPDATE orchestration_v2.dataset_state
SET dataset_name = 'cn_lpr', updated_at = NOW()
WHERE dataset_name = 'shibor_lpr';

UPDATE orchestration_v2.task_definition
SET lifecycle_status = 'retired', retired_at = NOW(), updated_at = NOW()
WHERE task_key = 'shibor_lpr' AND lifecycle_status = 'active';

DELETE FROM orchestration_v2.task_definition
WHERE task_key = 'shibor_lpr' AND lifecycle_status = 'draft';

-- Keep the old SQL view as a rolling-deploy compatibility alias only.  It is
-- not registered as a public dataset or a schedulable task.
CREATE OR REPLACE VIEW canonical_shibor_lpr AS
SELECT * FROM canonical_cn_lpr;

COMMENT ON VIEW canonical_shibor_lpr IS
    'Deprecated internal compatibility alias; use canonical_cn_lpr';
