"""Read-optimized access to the position-stable local factor product."""

from __future__ import annotations

from datetime import date
from typing import Any, Iterable

import psycopg2.extras

from service.db import get_conn

from .catalog import FACTOR_BY_NAME, FACTOR_SCHEMA_VERSION, FACTOR_SPECS
from .issue import issue_category
from .ownership import (
    SHARED_TECHNICAL_FIELDS, TECHNICAL_ALIASES, TECHNICAL_FEATURES,
    canonical_position, resolve_feature,
)


def _comparison_reason(reason):
    return {
        "provider_date_not_published_yet": "no_reference_values_in_local_date_sample",
        "provider_factor_not_published_yet": "no_reference_values_for_factor_in_local_sample",
    }.get(reason, reason)


def factor_catalog_payload(*, family: str | None = None) -> dict[str, Any]:
    """Return the immutable factor ABI, optionally filtered by family."""

    selected = [
        item for item in FACTOR_SPECS
        if family is None or item.family.casefold() == family.casefold()
    ]
    return {
        "schema_version": FACTOR_SCHEMA_VERSION,
        "factor_count": len(selected),
        "total_factor_count": len(FACTOR_SPECS),
        "factors": [
            {
                "position": item.position,
                "name": item.name,
                "family": item.family,
                "formula": item.formula,
                "overlap": {
                    "kind": item.overlap_kind,
                    "dataset": item.overlap_dataset,
                    "field": item.overlap_field,
                    "note": item.convention_note,
                },
            }
            for item in selected
        ],
    }


def normalize_factor_names(names: Iterable[str]) -> tuple[str, ...]:
    """Validate and de-duplicate requested names while preserving order."""

    selected = tuple(dict.fromkeys(name.strip() for name in names if name.strip()))
    unknown = sorted(set(selected) - set(FACTOR_BY_NAME) - set(TECHNICAL_FEATURES)
                     - set(SHARED_TECHNICAL_FIELDS) - set(TECHNICAL_ALIASES))
    if unknown:
        raise ValueError(f"unknown local factors: {unknown}")
    if len(selected) > 64:
        raise ValueError("at most 64 factors may be queried at once")
    return selected


def query_local_factor_values(
    ts_code: str,
    *,
    names: Iterable[str],
    start_date: date | None = None,
    end_date: date | None = None,
    limit: int = 500,
) -> dict[str, Any]:
    """Read selected array positions without unnesting all 272 values.

    Positions and aliases come only from the code-owned catalog.  This keeps
    the primary query on ``(ts_code, trade_date)`` and avoids the billions of
    rows and expensive pivots of a long-form EAV factor table.
    """

    selected = normalize_factor_names(names)
    if not selected:
        selected = tuple(item.name for item in FACTOR_SPECS[:20])
    def projection(name: str) -> str:
        canonical, multiplier = resolve_feature(name)
        if canonical in FACTOR_BY_NAME:
            expression = f'factor_values[{FACTOR_BY_NAME[canonical].position}]'
        else:
            expression = f"(technical_values->>'{canonical}')::double precision"
        return f'({expression} * {multiplier}) AS "{name}"'

    projections = ", ".join(projection(name) for name in selected)
    clauses = ["schema_version=%s", "ts_code=%s"]
    parameters: list[Any] = [FACTOR_SCHEMA_VERSION, ts_code.upper()]
    if start_date is not None:
        clauses.append("trade_date >= %s")
        parameters.append(start_date)
    if end_date is not None:
        clauses.append("trade_date <= %s")
        parameters.append(end_date)
    parameters.append(limit)
    connection = get_conn()
    try:
        with connection.cursor(
            cursor_factory=psycopg2.extras.RealDictCursor
        ) as cursor:
            cursor.execute(
                f"""
                SELECT trade_date, ts_code, calculation_status, ready_count, audit_status, audit_evidence,
                       computed_at, {projections}
                FROM local_factor_snapshot
                WHERE {' AND '.join(clauses)}
                ORDER BY trade_date DESC
                LIMIT %s
                """,
                tuple(parameters),
            )
            rows = [dict(row) for row in cursor.fetchall()]
            positions = {
                name: position for name in selected
                if (position := canonical_position(name)) is not None
            }
            evidence = {}
            if rows and positions:
                cursor.execute("""
                    SELECT trade_date,factor_position,validation_status,validation_reason,value_match_ratio
                    FROM local_factor_validation WHERE schema_version=%s
                      AND trade_date=ANY(%s) AND factor_position=ANY(%s)
                """, (FACTOR_SCHEMA_VERSION, [row["trade_date"] for row in rows], list(set(positions.values()))))
                evidence = {(item["trade_date"], item["factor_position"]): item for item in cursor.fetchall()}
            for row in rows:
                row["verification"] = {
                    name: {
                        "availability": "has_value" if row[name] is not None else "missing",
                        "calculation_evidence": issue_category(resolve_feature(name)[0], row[name] is not None, row["audit_evidence"]),
                        "comparison_status": evidence.get((row["trade_date"], positions.get(name)), {}).get("validation_status", "not_compared"),
                        "comparison_reason": _comparison_reason(evidence.get((row["trade_date"], positions.get(name)), {}).get("validation_reason")),
                        "input_issue": row["audit_evidence"].get("unresolved", {}).get(resolve_feature(name)[0]),
                        "exclusion": row["audit_evidence"].get("excluded", {}).get(resolve_feature(name)[0]),
                    }
                    for name in selected
                }
                for name, check in row["verification"].items():
                    if check["calculation_evidence"] == "incorrect_short_window_value":
                        row[name] = None
                        check["availability"] = "blocked"

    finally:
        connection.close()
    return {
        "schema_version": FACTOR_SCHEMA_VERSION,
        "official_source": "claw_local",
        "provider_fallback": False,
        "frequency": "daily",
        "readiness_note": "Non-null means calculated, not independently validated; null is never filled from provider data.",
        "ts_code": ts_code.upper(),
        "factor_names": list(selected),
        "count": len(rows),
        "rows": rows,
    }


def factor_validation_payload(*, trade_date: date | None = None) -> dict[str, Any]:
    """Expose persisted comparison evidence, never an inferred pass."""

    connection = get_conn()
    try:
        with connection.cursor(
            cursor_factory=psycopg2.extras.RealDictCursor
        ) as cursor:
            if trade_date is None:
                cursor.execute(
                    """
                    SELECT max(trade_date)
                    FROM local_factor_validation
                    WHERE schema_version=%s
                    """,
                    (FACTOR_SCHEMA_VERSION,),
                )
                trade_date = cursor.fetchone()["max"]
            if trade_date is None:
                return {
                    "schema_version": FACTOR_SCHEMA_VERSION,
                    "trade_date": None, "summary": {}, "factors": [],
                }
            cursor.execute(
                """
                SELECT catalog.factor_name, catalog.factor_family,
                       validation.factor_position, validation.sample_size,
                       validation.pearson_correlation,
                       validation.mean_absolute_error,
                       validation.normalized_mae,
                       validation.value_match_ratio,
                       validation.validation_status,
                       validation.validation_reason,
                       validation.computed_at, validation.sample_method,
                       validation.sample_seed, validation.sample_target_size,
                       validation.sampled_security_count, validation.validation_elapsed_ms
                FROM local_factor_validation AS validation
                JOIN local_factor_catalog AS catalog
                  ON catalog.schema_version=validation.schema_version
                 AND catalog.factor_position=validation.factor_position
                WHERE validation.schema_version=%s
                  AND validation.trade_date=%s
                ORDER BY validation.factor_position
                """,
                (FACTOR_SCHEMA_VERSION, trade_date),
            )
            rows = [dict(row) for row in cursor.fetchall()]
    finally:
        connection.close()
    summary: dict[str, int] = {}
    for row in rows:
        row["validation_reason"] = _comparison_reason(row["validation_reason"])
        status = str(row["validation_status"])
        summary[status] = summary.get(status, 0) + 1
    return {
        "schema_version": FACTOR_SCHEMA_VERSION,
        "trade_date": trade_date,
        "summary": summary,
        "factors": rows,
    }
