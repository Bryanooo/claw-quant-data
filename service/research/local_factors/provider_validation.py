"""Bounded, reproducible comparison of local factors with provider evidence.

Provider values are never used as production values.  The daily comparison is
deliberately a deterministic sample: validation must be cheap enough to run on
every trading day, while the seed and sampled codes make every result
reproducible during an incident review.
"""

from __future__ import annotations

from datetime import date
from time import monotonic
from typing import Any

from service.db import get_conn
from .reference_sampling import SAMPLE_CODES_SQL, SAMPLE_SIZE, SAMPLE_METHOD


DEFAULT_SAMPLE_SIZE = SAMPLE_SIZE
VALIDATION_TIMEOUT_MS = 15 * 60 * 1000


VALIDATION_SQL = """
WITH sample_codes AS MATERIALIZED (
    __REFERENCE_SAMPLE_SQL__
), provider AS MATERIALIZED (
    SELECT DISTINCT ON (source.factor_name, source.ts_code)
           source.factor_name, source.ts_code,
           source.factor_value::DOUBLE PRECISION AS provider_value
    FROM tushare_norm_factor_value AS source
    JOIN sample_codes USING (ts_code)
    WHERE source.trade_date=%s
      AND source.factor_value IS NOT NULL
    ORDER BY source.factor_name, source.ts_code, source._last_seen_at DESC,
             source._record_hash DESC
), provider_counts AS (
    SELECT factor_name, count(*) AS available FROM provider GROUP BY factor_name
), provider_total AS MATERIALIZED (
    SELECT count(*)::INTEGER AS available FROM provider
), pairs AS (
    SELECT catalog.factor_position,
           snapshot.factor_values[catalog.factor_position] AS local_value,
           provider.provider_value
    FROM local_factor_catalog AS catalog
    JOIN local_factor_snapshot AS snapshot
      ON snapshot.schema_version=catalog.schema_version
     AND snapshot.trade_date=%s
    JOIN sample_codes USING (ts_code)
    JOIN provider
      ON provider.factor_name=catalog.factor_name
     AND provider.ts_code=snapshot.ts_code
    WHERE catalog.schema_version=%s
      AND snapshot.factor_values[catalog.factor_position] IS NOT NULL
      AND abs(snapshot.factor_values[catalog.factor_position]) <= 1e100
      AND abs(provider.provider_value) <= 1e100
), metrics AS MATERIALIZED (
    SELECT factor_position, count(*)::INTEGER AS sample_size,
           corr(local_value, provider_value) AS pearson_correlation,
           avg(abs(local_value-provider_value)) AS mean_absolute_error,
           avg(abs(local_value-provider_value))
               / NULLIF(avg(abs(provider_value)), 0) AS normalized_mae,
           avg((abs(local_value-provider_value) <=
               1e-5 + 1e-3 * abs(provider_value))::int)::double precision AS value_match_ratio
    FROM pairs
    GROUP BY factor_position
), sampled AS (
    SELECT count(*)::INTEGER AS sampled_security_count FROM sample_codes
)
INSERT INTO local_factor_validation (
    schema_version, trade_date, factor_position, sample_size,
    pearson_correlation, mean_absolute_error, normalized_mae,
    validation_status, validation_reason, value_match_ratio,
    sample_method, sample_seed, sample_target_size,
    sampled_security_count, validation_elapsed_ms
)
SELECT catalog.schema_version, %s, catalog.factor_position,
       coalesce(metrics.sample_size, 0), metrics.pearson_correlation,
       metrics.mean_absolute_error, metrics.normalized_mae,
       CASE
           WHEN provider_total.available=0 THEN 'provider_pending'
           WHEN coalesce(provider_counts.available,0)=0 THEN 'provider_pending'
           WHEN coalesce(metrics.sample_size, 0) < 30 THEN 'not_comparable'
           WHEN metrics.value_match_ratio >= 0.99 THEN 'matched'
           WHEN metrics.pearson_correlation >= 0.90 THEN 'correlated'
           ELSE 'review_required'
       END,
       CASE
           WHEN provider_total.available=0
               THEN 'no_reference_values_in_local_date_sample'
           WHEN coalesce(provider_counts.available,0)=0
               THEN 'no_reference_values_for_factor_in_local_sample'
           WHEN coalesce(metrics.sample_size, 0)=0
               THEN 'local_values_missing_or_no_security_overlap'
           WHEN metrics.sample_size < 30
               THEN 'fewer than 30 paired observations in daily sample'
           WHEN metrics.value_match_ratio >= 0.99
               THEN 'paired match ratio >=0.99 within atol=1e-5 rtol=1e-3; >=30 samples'
           WHEN metrics.pearson_correlation >= 0.90
               THEN 'correlation_only_not_value_equivalence'
           ELSE 'formula, unit, point-in-time, price basis, universe or sign convention requires review'
       END, metrics.value_match_ratio, %s, %s, %s,
       sampled.sampled_security_count, 0
FROM local_factor_catalog AS catalog
CROSS JOIN sampled
CROSS JOIN provider_total
LEFT JOIN metrics USING (factor_position)
LEFT JOIN provider_counts USING (factor_name)
WHERE catalog.schema_version=%s
ON CONFLICT (schema_version, trade_date, factor_position) DO UPDATE SET
    sample_size=EXCLUDED.sample_size,
    pearson_correlation=EXCLUDED.pearson_correlation,
    mean_absolute_error=EXCLUDED.mean_absolute_error,
    normalized_mae=EXCLUDED.normalized_mae,
    value_match_ratio=EXCLUDED.value_match_ratio,
    validation_status=EXCLUDED.validation_status,
    validation_reason=EXCLUDED.validation_reason,
    sample_method=EXCLUDED.sample_method,
    sample_seed=EXCLUDED.sample_seed,
    sample_target_size=EXCLUDED.sample_target_size,
    sampled_security_count=EXCLUDED.sampled_security_count,
    validation_elapsed_ms=EXCLUDED.validation_elapsed_ms,
    computed_at=NOW()
""".replace('__REFERENCE_SAMPLE_SQL__', SAMPLE_CODES_SQL)


def write_provider_validation(
    cursor: Any,
    target_date: date,
    schema_version: str,
    *,
    sample_size: int = DEFAULT_SAMPLE_SIZE,
    timeout_ms: int = VALIDATION_TIMEOUT_MS,
) -> dict[str, int | str]:
    """Write one bounded daily validation sample and return its summary."""

    if sample_size < 30:
        raise ValueError("provider validation sample_size must be at least 30")
    seed = target_date.isoformat()
    cursor.execute("SET LOCAL statement_timeout=%s", (timeout_ms,))
    started = monotonic()
    # Once a reference execution is accepted, compare exactly its frozen
    # securities and returned keys. Older full-market rows must not fill holes.
    # A windowed execution covers several dates, so the lookup accepts any
    # successful execution whose observation range contains the target.
    cursor.execute("""SELECT task_execution_id,frozen_scope->'reference_securities'
        FROM orchestration_v2.task_execution WHERE task_key='factor_reference_sample'
          AND observation_start <= %s AND observation_end >= %s AND status='success'
        ORDER BY task_execution_id DESC LIMIT 1""", (target_date, target_date))
    reference = cursor.fetchone()
    sql = VALIDATION_SQL
    if reference:
        execution_id, codes = reference
        cursor.execute('CREATE TEMP TABLE factor_reference_codes(ts_code text PRIMARY KEY) ON COMMIT DROP')
        cursor.execute('INSERT INTO factor_reference_codes SELECT unnest(%s::text[])', (codes,))
        cursor.execute('CREATE TEMP TABLE factor_reference_keys(ts_code text, factor_name text, PRIMARY KEY(ts_code,factor_name)) ON COMMIT DROP')
        # Keys are session-scoped: a windowed request carries one manifest per
        # session, and only the target session's keys may join the comparison.
        # The flat branch serves pre-window events only; an event with
        # day_manifests must be read session by session instead of as a
        # whole-window union.
        cursor.execute("""INSERT INTO factor_reference_keys
            SELECT code, key FROM (
                SELECT DISTINCT payload->'completion_evidence'->>'ts_code' AS code, k.key
                FROM orchestration_v2.task_execution_event
                CROSS JOIN LATERAL jsonb_array_elements_text(
                    payload->'completion_evidence'->'returned_keys') k(key)
                WHERE task_execution_id=%s AND event_type='node.acquire.request_completed'
                  AND payload->'completion_evidence'->>'reference_response_manifest'='true'
                  AND NOT (payload->'completion_evidence' ? 'day_manifests')
                  AND payload->'completion_evidence'->>'trade_date'=%s
                  AND NOT (payload->'completion_evidence'->'explicit_null_keys' ? k.key)
                UNION
                SELECT DISTINCT m->>'ts_code', k.key
                FROM orchestration_v2.task_execution_event
                CROSS JOIN LATERAL jsonb_array_elements(
                    payload->'completion_evidence'->'day_manifests') m
                CROSS JOIN LATERAL jsonb_array_elements_text(m->'returned_keys') k(key)
                WHERE task_execution_id=%s AND event_type='node.acquire.request_completed'
                  AND m->>'trade_date'=%s
                  AND NOT (m->'explicit_null_keys' ? k.key)
            ) keys(code, key)
            """, (execution_id, target_date.strftime('%Y%m%d'),
                  execution_id, target_date.strftime('%Y%m%d')))
        cursor.execute('ANALYZE factor_reference_codes')
        cursor.execute('ANALYZE factor_reference_keys')
        sql = sql.replace(SAMPLE_CODES_SQL, '''SELECT ts_code FROM factor_reference_codes
            CROSS JOIN (SELECT %s::text, %s::date, %s::text, %s::int) configuration''')
        sql = sql.replace('AND source.factor_value IS NOT NULL', '''AND source.factor_value IS NOT NULL
            AND EXISTS(SELECT 1 FROM factor_reference_keys k
                WHERE k.ts_code=source.ts_code AND k.factor_name=source.factor_name)''')
        sql = sql.replace("THEN 'provider_pending'", "THEN 'not_comparable'")
        for reason in ('no_reference_values_in_local_date_sample', 'no_reference_values_for_factor_in_local_sample'):
            sql = sql.replace(f"'{reason}'", "'supplier_missing_or_null_in_frozen_sample'")
        sample_size = len(codes)
    cursor.execute(
        sql,
        (
            schema_version, target_date, seed, sample_size,
            target_date, target_date, schema_version, target_date,
            SAMPLE_METHOD, seed, sample_size, schema_version,
        ),
    )
    elapsed_ms = max(0, int((monotonic() - started) * 1000))
    cursor.execute(
        """
        UPDATE local_factor_validation
        SET validation_elapsed_ms=%s
        WHERE schema_version=%s AND trade_date=%s
        """,
        (elapsed_ms, schema_version, target_date),
    )
    cursor.execute(
        """
        SELECT validation_status, count(*)
        FROM local_factor_validation
        WHERE schema_version=%s AND trade_date=%s
        GROUP BY validation_status
        """,
        (schema_version, target_date),
    )
    counts = {str(status): int(count) for status, count in cursor.fetchall()}
    cursor.execute(
        """
        SELECT coalesce(max(sampled_security_count),0)
        FROM local_factor_validation
        WHERE schema_version=%s AND trade_date=%s
        """,
        (schema_version, target_date),
    )
    sampled = int(cursor.fetchone()[0])
    return {
        "validation_matched": counts.get("matched", 0),
        "validation_correlated_only": counts.get("correlated", 0),
        "validation_review_required": counts.get("review_required", 0),
        "validation_not_comparable": counts.get("not_comparable", 0),
        "validation_provider_pending": counts.get("provider_pending", 0),
        "validation_sample_method": SAMPLE_METHOD,
        "validation_sample_target": sample_size,
        "validation_sampled_securities": sampled,
        "validation_elapsed_ms": elapsed_ms,
    }


def revalidate_provider_pending_dates(*, limit: int = 8) -> dict[str, Any]:
    """Re-run bounded samples after the provider publishes a pending date.

    Local values remain immutable.  This only refreshes comparison evidence,
    one transaction per date, so a bad date cannot roll back successful dates.
    """

    if limit < 1:
        raise ValueError("provider validation recheck limit must be positive")
    connection = get_conn()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT DISTINCT pending.trade_date
                FROM local_factor_validation AS pending
                JOIN local_factor_catalog AS catalog
                  ON catalog.schema_version=pending.schema_version
                 AND catalog.factor_position=pending.factor_position
                WHERE pending.schema_version=%s
                  AND pending.validation_status='provider_pending'
                  AND EXISTS (
                      SELECT 1 FROM tushare_norm_factor_value AS provider
                      WHERE provider.trade_date=pending.trade_date
                        AND provider.factor_name=catalog.factor_name
                        AND provider.factor_value IS NOT NULL
                  )
                UNION
                SELECT DISTINCT snapshot.trade_date
                FROM local_factor_snapshot snapshot
                WHERE snapshot.schema_version='local-272-v4'
                  AND NOT EXISTS (
                      SELECT 1 FROM local_factor_validation v
                      WHERE v.schema_version=snapshot.schema_version
                        AND v.trade_date=snapshot.trade_date
                        AND v.computed_at >= snapshot.computed_at
                  )
                UNION
                SELECT session.day::date
                FROM orchestration_v2.task_execution reference
                CROSS JOIN LATERAL jsonb_array_elements_text(
                    coalesce(reference.frozen_scope->'reference_trade_dates',
                             to_jsonb(ARRAY[reference.observation_end]))) session(day)
                WHERE reference.task_key='factor_reference_sample'
                  AND reference.status='success'
                  AND NOT EXISTS (
                      SELECT 1 FROM local_factor_validation v
                      WHERE v.schema_version='local-272-v4'
                        AND v.trade_date=session.day::date
                        AND v.computed_at >= reference.finished_at
                  )
                ORDER BY trade_date
                LIMIT %s
                """,
                ("local-272-v4", limit),
            )
            dates = [row[0] for row in cursor.fetchall()]
    finally:
        connection.close()

    completed: list[str] = []
    failed: dict[str, str] = {}
    for target_date in dates:
        connection = get_conn()
        try:
            with connection.cursor() as cursor:
                write_provider_validation(
                    cursor, target_date, "local-272-v4"
                )
            connection.commit()
            completed.append(target_date.isoformat())
        except Exception as exc:
            connection.rollback()
            failed[target_date.isoformat()] = f"{type(exc).__name__}: {exc}"
        finally:
            connection.close()
    return {
        "eligible": len(dates),
        "completed": completed,
        "failed": failed,
    }
