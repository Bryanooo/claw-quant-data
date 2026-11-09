"""Resumable, bounded historical publication of local factor sessions."""

from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import date
import os
from typing import Any, Callable, Iterable

from service.config import APP_REVISION
from service.db import get_conn

from .catalog import FACTOR_COUNT, FACTOR_SCHEMA_VERSION
from .materializer import FORMULA_DIGEST, IMPLEMENTATION_DIGEST, sync_factor_catalog


def trading_dates(start_date: date, end_date: date) -> list[date]:
    if end_date < start_date:
        raise ValueError("end_date must not precede start_date")
    connection = get_conn()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT cal_date
                FROM trade_cal
                WHERE exchange='SSE' AND is_open=1
                  AND cal_date BETWEEN %s AND %s
                  AND cal_date <= CURRENT_DATE
                ORDER BY cal_date
                """,
                (start_date, end_date),
            )
            return [row[0] for row in cursor.fetchall()]
    finally:
        connection.close()


def published_dates(dates: Iterable[date]) -> set[date]:
    selected = list(dates)
    if not selected:
        return set()
    connection = get_conn()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                WITH expected AS (
                    SELECT trade_date, count(*)::INTEGER AS expected_count
                    FROM daily WHERE trade_date=ANY(%s) GROUP BY trade_date
                ), snapshots AS (
                    SELECT trade_date, count(*)::INTEGER AS row_count,
                           bool_and(formula_digest=%s AND
                                    COALESCE(audit_evidence->>'implementation_digest','')=%s) AS current_formula,
                           bool_and(audit_status IN ('ready', 'not_expected')
                                    AND technical_audit_status IN ('ready', 'not_expected')) AS quality_ready
                    FROM local_factor_snapshot
                    WHERE schema_version=%s AND trade_date=ANY(%s)
                    GROUP BY trade_date
                ), validation AS (
                    SELECT trade_date, count(*)::INTEGER AS factor_count
                    FROM local_factor_validation
                    WHERE schema_version=%s AND trade_date=ANY(%s)
                    GROUP BY trade_date
                )
                SELECT expected.trade_date
                FROM expected
                JOIN snapshots USING(trade_date)
                JOIN validation USING(trade_date)
                WHERE snapshots.row_count >= expected.expected_count
                  AND snapshots.current_formula
                  AND snapshots.quality_ready
                  AND NOT EXISTS (
                      SELECT 1 FROM daily d
                      WHERE d.trade_date=expected.trade_date
                        AND NOT EXISTS (
                            SELECT 1 FROM local_factor_snapshot s
                            WHERE s.trade_date=d.trade_date AND s.ts_code=d.ts_code
                              AND s.schema_version=%s
                        )
                  )
                  AND validation.factor_count=%s
                """,
                (
                    selected, FORMULA_DIGEST, IMPLEMENTATION_DIGEST, FACTOR_SCHEMA_VERSION, selected,
                    FACTOR_SCHEMA_VERSION, selected, FACTOR_SCHEMA_VERSION, FACTOR_COUNT,
                ),
            )
            return {row[0] for row in cursor.fetchall()}
    finally:
        connection.close()


def _materialize_one(target_date: date) -> dict[str, Any]:
    from .materializer import materialize_local_factor_snapshot

    return materialize_local_factor_snapshot(target_date)


def _sync_catalog_once() -> None:
    catalog_connection = get_conn()
    try:
        sync_factor_catalog(catalog_connection)
        catalog_connection.commit()
    except Exception:
        catalog_connection.rollback()
        raise
    finally:
        catalog_connection.close()


def materialize_factor_batch(
    dates: Iterable[date], *, workers: int = 1, force: bool = False,
    progress: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    """Publish dates with per-session atomic commits and resumable skipping.

    A batch is orchestration scope, not an alternate storage transaction: each
    data date remains independently locked, committed, validated and auditable.
    Failed dates do not roll back already certified dates and a rerun skips
    complete sessions.
    """

    requested = sorted(set(dates))
    if workers < 1 or workers > 4:
        raise ValueError("workers must be between 1 and 4")
    # Catalog publication is also performed by each worker as a short,
    # committed preflight. This parent preflight catches catalog drift before
    # any expensive worker process is launched.
    _sync_catalog_once()
    complete = set() if force else published_dates(requested)
    pending = [item for item in requested if item not in complete]
    results: dict[str, dict[str, Any]] = {}
    failures: dict[str, str] = {}
    if progress:
        progress({
            "event": "batch_started", "requested": len(requested),
            "skipped": len(complete), "pending": len(pending),
        })

    if workers == 1:
        for target_date in pending:
            try:
                results[target_date.isoformat()] = _materialize_one(target_date)
                if progress:
                    progress({"event": "date_completed" if results[target_date.isoformat()].get("data_ready") is True else "date_partial", "date": target_date.isoformat()})
            except Exception as exc:  # preserve completed sessions for resume
                failures[target_date.isoformat()] = f"{type(exc).__name__}: {exc}"
                if progress:
                    progress({"event": "date_failed", "date": target_date.isoformat(),
                              "error": failures[target_date.isoformat()]})
    else:
        with ProcessPoolExecutor(max_workers=workers) as executor:
            future_dates = {
                executor.submit(_materialize_one, target_date): target_date
                for target_date in pending
            }
            for future in as_completed(future_dates):
                target_date = future_dates[future]
                try:
                    results[target_date.isoformat()] = future.result()
                    if progress:
                        progress({"event": "date_completed" if results[target_date.isoformat()].get("data_ready") is True else "date_partial", "date": target_date.isoformat()})
                except Exception as exc:
                    failures[target_date.isoformat()] = f"{type(exc).__name__}: {exc}"
                    if progress:
                        progress({"event": "date_failed", "date": target_date.isoformat(),
                                  "error": failures[target_date.isoformat()]})

    return {
        "schema_version": FACTOR_SCHEMA_VERSION,
        "formula_digest": FORMULA_DIGEST,
        "requested_dates": [item.isoformat() for item in requested],
        "skipped_complete_dates": [item.isoformat() for item in sorted(complete)],
        "completed_dates": sorted(day for day, result in results.items() if result.get("data_ready") is True),
        "partial_dates": sorted(day for day, result in results.items() if result.get("data_ready") is not True),
        "failed_dates": failures,
        "results": results,
    }


def enqueue_factor_batch(dates: Iterable[date]) -> dict[str, Any]:
    """Create one governed V2 backfill execution per trading date.

    Direct materialization is useful for development diagnostics, but it must
    not be the operational history path: only a V2 execution can run the
    independent output audit and publish ``dataset_state``. The execution
    identity includes the active task-definition version, so a corrected
    definition can recertify a date without duplicating work within a version.
    """

    from service.orchestration_v2.gap_repair import create_repair_executions
    from service.orchestration_v2.repair_planning import RepairInstanceProposal
    from service.orchestration_v2.repository import OrchestrationV2Repository

    requested = sorted(set(dates))
    proposals = tuple(
        RepairInstanceProposal(
            task_key="local_factor_snapshot",
            observation_key=target_date.isoformat(),
            observation_start=target_date,
            observation_end=target_date,
            observation_period=target_date.isoformat(),
            datasets=("local_factor_snapshot", "technical_factor_snapshot"),
            reasons=("local_factor_historical_batch",),
        )
        for target_date in requested
    )
    result = create_repair_executions(
        proposals=proposals,
        repository=OrchestrationV2Repository(),
        actor_revision=APP_REVISION,
        image_digest=os.getenv("IMAGE_DIGEST", "runtime-local"),
        purpose="backfill",
        trigger_source="recovery",
        idempotency_prefix=f"v2:local-factor-history:{FACTOR_SCHEMA_VERSION}",
        frozen_scope_extra={
            "historical_source_validation": "transform_owned",
            "factor_schema_version": FACTOR_SCHEMA_VERSION,
            "formula_digest": FORMULA_DIGEST,
            "reuse_existing_snapshot": True,
        },
    )
    return {
        "mode": "v2_control_plane",
        "schema_version": FACTOR_SCHEMA_VERSION,
        "formula_digest": FORMULA_DIGEST,
        "requested_dates": [item.isoformat() for item in requested],
        **result,
    }
