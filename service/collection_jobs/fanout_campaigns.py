"""Durable whole-universe orchestration across bounded fan-out pages."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import date
import hashlib
import json
import logging
from typing import Any

import psycopg2
import psycopg2.extras

from service.collection_jobs.fanout import FANOUT_DEFINITIONS, FanoutPlanner
from service.collection_jobs.models import (
    InvalidTaskParametersError,
    JobConflictError,
    JobNotFoundError,
)
from service.collection_jobs.registry import TASKS
from service.collection_jobs.repository import JobRepository
from service.config import DB_CONFIG


_LOCK_NAMESPACE = 1_924_202_632
logger = logging.getLogger(__name__)


class FanoutCampaignRepository:
    def __init__(self, connection_factory: Callable[..., Any] = psycopg2.connect):
        self._connection_factory = connection_factory

    @contextmanager
    def _connection(self):
        connection = self._connection_factory(**DB_CONFIG)
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    @contextmanager
    def reconcile_lock(self, campaign_id: int) -> Iterator[bool]:
        connection = self._connection_factory(**DB_CONFIG)
        acquired = False
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT pg_try_advisory_lock(%s, %s)",
                    (_LOCK_NAMESPACE, campaign_id),
                )
                acquired = bool(cursor.fetchone()[0])
            yield acquired
        finally:
            if acquired:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT pg_advisory_unlock(%s, %s)",
                        (_LOCK_NAMESPACE, campaign_id),
                    )
            connection.close()

    def create(
        self,
        *,
        api_name: str,
        request: dict[str, Any],
        page_size: int,
        idempotency_key: str,
        initialization_id: int | None,
        cadence: str,
        period_key: str | None,
        expected_for: date | None,
        plan_version: int = 1,
        reuse_scope: bool = False,
    ) -> tuple[dict, bool]:
        with (
            self._connection() as connection,
            connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor,
        ):
            if reuse_scope and period_key:
                scope_lock = json.dumps(
                    [api_name, period_key, expected_for, plan_version, request],
                    ensure_ascii=False,
                    sort_keys=True,
                    default=str,
                    separators=(",", ":"),
                )
                cursor.execute(
                    "SELECT pg_advisory_xact_lock(%s, hashtext(%s))",
                    (_LOCK_NAMESPACE, scope_lock),
                )
                cursor.execute(
                    """
                    SELECT *
                    FROM sys_collection_fanout_campaign
                    WHERE api_name=%s
                      AND period_key=%s
                      AND expected_for IS NOT DISTINCT FROM %s
                      AND plan_version=%s
                      AND request=%s::jsonb
                      AND status IN ('running','success')
                    ORDER BY
                        CASE status WHEN 'success' THEN 0 ELSE 1 END,
                        campaign_id DESC
                    LIMIT 1
                    """,
                    (
                        api_name,
                        period_key,
                        expected_for,
                        plan_version,
                        json.dumps(request, ensure_ascii=False),
                    ),
                )
                reusable = cursor.fetchone()
                if reusable:
                    return dict(reusable), False
            cursor.execute(
                """
                INSERT INTO sys_collection_fanout_campaign(
                    api_name, request, page_size, initialization_id,
                    idempotency_key, cadence, period_key, expected_for, plan_version,
                    status, completion_status
                ) VALUES (%s,%s::jsonb,%s,%s,%s,%s,%s,%s,%s,'running','pending')
                ON CONFLICT (idempotency_key) DO NOTHING
                RETURNING *
                """,
                (
                    api_name,
                    json.dumps(request, ensure_ascii=False),
                    page_size,
                    initialization_id,
                    idempotency_key,
                    cadence,
                    period_key,
                    expected_for,
                    plan_version,
                ),
            )
            row = cursor.fetchone()
            if row:
                return dict(row), True
            cursor.execute(
                "SELECT * FROM sys_collection_fanout_campaign WHERE idempotency_key=%s",
                (idempotency_key,),
            )
            return dict(cursor.fetchone()), False

    def freeze_universe(
        self,
        campaign_id: int,
        *,
        source: str,
        values: list[str],
        digest: str,
    ) -> None:
        if not values:
            raise InvalidTaskParametersError(
                f"fan-out dependency {source} has no available values"
            )
        if any(not isinstance(value, str) or not value.strip() for value in values):
            raise InvalidTaskParametersError(
                f"fan-out dependency {source} contains an empty entity"
            )
        if len(set(values)) != len(values):
            raise InvalidTaskParametersError(
                f"fan-out dependency {source} contains duplicate entities"
            )
        with self._connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT universe_source, universe_total, universe_digest
                FROM sys_collection_fanout_campaign
                WHERE campaign_id=%s FOR UPDATE
                """,
                (campaign_id,),
            )
            row = cursor.fetchone()
            if row is None:
                raise JobNotFoundError(f"fan-out campaign not found: {campaign_id}")
            stored_source, stored_total, stored_digest = row
            if stored_digest:
                if (
                    stored_source != source
                    or int(stored_total) != len(values)
                    or stored_digest.strip() != digest
                ):
                    raise JobConflictError(
                        "cannot reconstruct previously frozen fan-out universe"
                    )
            else:
                cursor.execute(
                    """
                    UPDATE sys_collection_fanout_campaign
                    SET universe_source=%s, universe_total=%s,
                        universe_digest=%s, updated_at=NOW()
                    WHERE campaign_id=%s
                    """,
                    (source, len(values), digest, campaign_id),
                )
            cursor.execute(
                """
                SELECT COUNT(*) FROM sys_collection_fanout_campaign_entity
                WHERE campaign_id=%s
                """,
                (campaign_id,),
            )
            entity_count = int(cursor.fetchone()[0])
            if entity_count == len(values):
                return
            if entity_count:
                raise JobConflictError(
                    "frozen fan-out universe entity count is inconsistent"
                )
            psycopg2.extras.execute_values(
                cursor,
                """
                INSERT INTO sys_collection_fanout_campaign_entity(
                    campaign_id, entity_index, entity_value
                ) VALUES %s
                """,
                [(campaign_id, index, value) for index, value in enumerate(values)],
                page_size=1000,
            )

    def universe_values(self, campaign_id: int) -> list[str]:
        with self._connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT entity_value
                FROM sys_collection_fanout_campaign_entity
                WHERE campaign_id=%s
                ORDER BY entity_index
                """,
                (campaign_id,),
            )
            return [str(row[0]) for row in cursor.fetchall()]

    def get(self, campaign_id: int) -> dict | None:
        with (
            self._connection() as connection,
            connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor,
        ):
            cursor.execute(
                "SELECT * FROM sys_collection_fanout_campaign WHERE campaign_id=%s",
                (campaign_id,),
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def list(self, *, status: str | None = None, limit: int = 50) -> list[dict]:
        where = "WHERE status=%s" if status else ""
        parameters: tuple[Any, ...] = (status, limit) if status else (limit,)
        with (
            self._connection() as connection,
            connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor,
        ):
            cursor.execute(
                f"""
                SELECT * FROM sys_collection_fanout_campaign
                {where}
                ORDER BY created_at DESC, campaign_id DESC
                LIMIT %s
                """,
                parameters,
            )
            return [dict(row) for row in cursor.fetchall()]

    def runnable_ids(self, *, limit: int = 20) -> list[int]:
        with self._connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT campaign.campaign_id
                FROM sys_collection_fanout_campaign AS campaign
                LEFT JOIN sys_collection_initialization AS initialization
                  ON initialization.initialization_id=campaign.initialization_id
                WHERE campaign.status='running'
                  AND (
                    campaign.initialization_id IS NULL
                    OR initialization.status='running'
                  )
                ORDER BY campaign.updated_at, campaign.campaign_id
                LIMIT %s
                """,
                (limit,),
            )
            return [int(row[0]) for row in cursor.fetchall()]

    def pages(self, campaign_id: int) -> list[dict]:
        with (
            self._connection() as connection,
            connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor,
        ):
            cursor.execute(
                """
                SELECT mapping.*, job.status AS batch_status,
                       job.completion_status AS batch_completion_status,
                       job.child_total, job.child_queued, job.child_running,
                       job.child_succeeded, job.child_failed,
                       job.rows_fetched, job.rows_inserted,
                       job.completion_evidence, job.error_message
                FROM sys_collection_fanout_campaign_batch AS mapping
                JOIN sys_collection_job AS job ON job.job_id=mapping.batch_job_id
                WHERE mapping.campaign_id=%s
                ORDER BY mapping.page_index
                """,
                (campaign_id,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def page_state(self, batch_job_id: int) -> dict:
        with (
            self._connection() as connection,
            connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor,
        ):
            cursor.execute(
                """
                SELECT COUNT(*)::INTEGER AS total,
                       COUNT(*) FILTER (WHERE status='success')::INTEGER AS succeeded,
                       COUNT(*) FILTER (WHERE status='failed')::INTEGER AS failed,
                       COUNT(*) FILTER (WHERE status IN ('queued','running'))::INTEGER AS active,
                       COALESCE(BOOL_AND(
                           status='success'
                           AND completion_status IN ('complete','empty')
                           AND COALESCE((completion_evidence->>'verified')::BOOLEAN,FALSE)
                       ), FALSE) AS verified
                FROM sys_collection_job
                WHERE parent_job_id=%s
                """,
                (batch_job_id,),
            )
            return dict(cursor.fetchone())

    def attach_page(self, campaign_id: int, batch: dict) -> None:
        plan = batch["parameters"]["plan"]
        with self._connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM sys_collection_fanout_campaign WHERE campaign_id=%s FOR UPDATE",
                (campaign_id,),
            )
            campaign = cursor.fetchone()
            if campaign is None:
                raise JobNotFoundError(f"fan-out campaign not found: {campaign_id}")
            # Column order follows the table definition. Named access is not
            # available on this cursor, so validate against explicit values.
            cursor.execute(
                """
                SELECT universe_source, universe_total, universe_digest,
                       pages_created
                FROM sys_collection_fanout_campaign
                WHERE campaign_id=%s
                """,
                (campaign_id,),
            )
            source, total, digest, pages_created = cursor.fetchone()
            if digest and (
                digest.strip() != plan["universe_digest"]
                or source != plan["universe_source"]
                or int(total) != int(plan["universe_total"])
            ):
                raise JobConflictError(
                    "fan-out page plan does not match the frozen campaign universe"
                )
            page_index = int(pages_created)
            cursor.execute(
                """
                INSERT INTO sys_collection_fanout_campaign_batch(
                    campaign_id, page_index, batch_job_id, entity_offset,
                    next_offset, entities_selected, selected_digest
                ) VALUES (%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (campaign_id, page_index) DO NOTHING
                """,
                (
                    campaign_id,
                    page_index,
                    batch["job_id"],
                    plan["entity_offset"],
                    plan["next_offset"],
                    plan["entities_selected"],
                    plan["selected_digest"],
                ),
            )
            cursor.execute(
                """
                UPDATE sys_collection_fanout_campaign
                SET universe_source=COALESCE(universe_source,%s),
                    universe_total=COALESCE(universe_total,%s),
                    universe_digest=COALESCE(universe_digest,%s),
                    next_offset=%s,
                    pages_created=(
                        SELECT COUNT(*) FROM sys_collection_fanout_campaign_batch
                        WHERE campaign_id=%s
                    ),
                    completion_status='running', updated_at=NOW()
                WHERE campaign_id=%s
                """,
                (
                    plan["universe_source"],
                    plan["universe_total"],
                    plan["universe_digest"],
                    plan["next_offset"],
                    campaign_id,
                    campaign_id,
                ),
            )

    def update_progress(self, campaign_id: int) -> None:
        with self._connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                WITH aggregate AS (
                    SELECT
                        COUNT(*)::INTEGER AS pages_created,
                        COUNT(*) FILTER (
                            WHERE parent.status='success'
                              AND NOT EXISTS (
                                SELECT 1 FROM sys_collection_job AS child
                                WHERE child.parent_job_id=parent.job_id
                                  AND NOT (
                                    child.status='success'
                                    AND child.completion_status IN ('complete','empty')
                                    AND COALESCE(
                                      (child.completion_evidence->>'verified')::BOOLEAN,
                                      FALSE
                                    )
                                  )
                              )
                        )::INTEGER AS pages_completed,
                        COALESCE(MAX(mapping.next_offset) FILTER (
                            WHERE parent.status='success'
                              AND NOT EXISTS (
                                SELECT 1 FROM sys_collection_job AS child
                                WHERE child.parent_job_id=parent.job_id
                                  AND NOT (
                                    child.status='success'
                                    AND child.completion_status IN ('complete','empty')
                                    AND COALESCE(
                                      (child.completion_evidence->>'verified')::BOOLEAN,
                                      FALSE
                                    )
                                  )
                              )
                        ), 0)::INTEGER AS completed_offset,
                        COALESCE(SUM(parent.rows_fetched),0)::BIGINT AS rows_fetched,
                        COALESCE(SUM(parent.rows_inserted),0)::BIGINT AS rows_inserted
                    FROM sys_collection_fanout_campaign_batch AS mapping
                    JOIN sys_collection_job AS parent
                      ON parent.job_id=mapping.batch_job_id
                    WHERE mapping.campaign_id=%s
                )
                UPDATE sys_collection_fanout_campaign
                SET pages_created=aggregate.pages_created,
                    pages_completed=aggregate.pages_completed,
                    completed_offset=aggregate.completed_offset,
                    rows_fetched=aggregate.rows_fetched,
                    rows_inserted=aggregate.rows_inserted,
                    updated_at=NOW()
                FROM aggregate
                WHERE campaign_id=%s
                """,
                (campaign_id, campaign_id),
            )

    def set_status(
        self,
        campaign_id: int,
        status: str,
        completion_status: str,
        *,
        error_message: str | None = None,
    ) -> None:
        with self._connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE sys_collection_fanout_campaign
                SET status=%s, completion_status=%s, error_message=%s,
                    updated_at=NOW(),
                    finished_at=CASE
                        WHEN %s IN ('success','superseded') THEN NOW()
                        ELSE NULL
                    END
                WHERE campaign_id=%s
                """,
                (status, completion_status, error_message, status, campaign_id),
            )

    def supersede(
        self,
        campaign_id: int,
        replacement_campaign_id: int,
        *,
        message: str,
    ) -> None:
        """Resolve an obsolete failed plan through a verified replacement."""
        if campaign_id == replacement_campaign_id:
            raise JobConflictError("a campaign cannot supersede itself")
        with (
            self._connection() as connection,
            connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor,
        ):
            cursor.execute(
                """
                SELECT * FROM sys_collection_fanout_campaign
                WHERE campaign_id IN (%s,%s)
                ORDER BY campaign_id FOR UPDATE
                """,
                (campaign_id, replacement_campaign_id),
            )
            campaigns = {int(row["campaign_id"]): dict(row) for row in cursor.fetchall()}
            original = campaigns.get(campaign_id)
            replacement = campaigns.get(replacement_campaign_id)
            if not original or not replacement:
                raise JobNotFoundError("fan-out campaign for supersession was not found")
            if original["status"] not in {"attention", "paused"}:
                raise JobConflictError(
                    "only an attention or paused campaign can be superseded"
                )
            if (
                replacement["status"] != "success"
                or replacement["completion_status"] not in {"complete", "empty"}
            ):
                raise JobConflictError(
                    "replacement campaign must be successfully verified first"
                )
            if original["api_name"] != replacement["api_name"]:
                raise JobConflictError("replacement campaign must use the same interface")
            if original.get("period_key") != replacement.get("period_key"):
                raise JobConflictError("replacement campaign must cover the same period")
            cursor.execute(
                """
                UPDATE sys_collection_fanout_campaign
                SET status='superseded', completion_status='incomplete',
                    superseded_by_campaign_id=%s, resolution_message=%s,
                    error_message=NULL, updated_at=NOW(), finished_at=NOW()
                WHERE campaign_id=%s
                """,
                (replacement_campaign_id, message[:4000], campaign_id),
            )

    def failed_child_ids(self, campaign_id: int) -> list[int]:
        with self._connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT child.job_id
                FROM sys_collection_fanout_campaign_batch AS mapping
                JOIN sys_collection_job AS child
                  ON child.parent_job_id=mapping.batch_job_id
                WHERE mapping.campaign_id=%s AND child.status='failed'
                ORDER BY child.job_id
                """,
                (campaign_id,),
            )
            return [int(row[0]) for row in cursor.fetchall()]


def _json_request(request: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value.isoformat() if isinstance(value, date) else value
        for key, value in request.items()
        if value is not None and key not in {"offset", "max_children", "page_size"}
    }


def _universe_digest(values: list[str]) -> str:
    return hashlib.sha256(
        json.dumps(
            values,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


class FanoutCampaignService:
    def __init__(
        self,
        repository: FanoutCampaignRepository | None = None,
        job_repository: JobRepository | None = None,
    ):
        self._repository = repository or FanoutCampaignRepository()
        self._job_repository = job_repository or JobRepository()
        self._planner = FanoutPlanner(self._job_repository, TASKS)

    def submit(
        self,
        request: dict[str, Any],
        *,
        idempotency_key: str | None,
        initialization_id: int | None = None,
        cadence: str = "backfill",
        period_key: str | None = None,
        expected_for: date | None = None,
        plan_version: int = 1,
        reuse_scope: bool = False,
    ) -> tuple[dict, bool]:
        api_name = request["api_name"]
        if api_name not in FANOUT_DEFINITIONS:
            raise InvalidTaskParametersError(
                f"{api_name} is not enabled for safe fan-out collection"
            )
        page_size = int(request.get("page_size", 100))
        if not 1 <= page_size <= 200:
            raise InvalidTaskParametersError("page_size must be between 1 and 200")
        if cadence not in {
            "backfill", "initialization", "daily", "weekly", "monthly", "quarterly"
        }:
            raise InvalidTaskParametersError(f"unsupported fan-out cadence: {cadence}")
        if plan_version < 1:
            raise InvalidTaskParametersError("fan-out plan_version must be positive")
        normalized = _json_request(request)
        key = idempotency_key or (
            f"fanout-campaign:{api_name}:"
            f"{hashlib.sha256(json.dumps(normalized, sort_keys=True).encode()).hexdigest()[:40]}"
        )
        campaign, created = self._repository.create(
            api_name=api_name,
            request=normalized,
            page_size=page_size,
            idempotency_key=key,
            initialization_id=initialization_id,
            cadence=cadence,
            period_key=period_key,
            expected_for=expected_for,
            plan_version=plan_version,
            reuse_scope=reuse_scope,
        )
        reused_scope = not created and campaign["idempotency_key"] != key
        if not created and not reused_scope and (
            campaign["api_name"] != api_name
            or campaign["request"] != normalized
            or campaign["page_size"] != page_size
            or campaign.get("initialization_id") != initialization_id
            or campaign.get("cadence") != cadence
            or campaign.get("period_key") != period_key
            or campaign.get("expected_for") != expected_for
            or int(campaign.get("plan_version") or 1) != plan_version
        ):
            raise JobConflictError(
                "idempotency key is already associated with another fan-out campaign"
            )
        if created:
            self.reconcile(campaign["campaign_id"])
        return self.get(campaign["campaign_id"]), created

    def get(self, campaign_id: int) -> dict:
        campaign = self._repository.get(campaign_id)
        if not campaign:
            raise JobNotFoundError(f"fan-out campaign not found: {campaign_id}")
        result = dict(campaign)
        result["pages"] = self._repository.pages(campaign_id)
        total = result.get("universe_total") or 0
        result["progress_ratio"] = (
            min(result["completed_offset"] / total, 1.0) if total else 0.0
        )
        return result

    def list(self, *, status: str | None = None, limit: int = 50) -> list[dict]:
        return [
            {
                **item,
                "progress_ratio": (
                    min(item["completed_offset"] / item["universe_total"], 1.0)
                    if item.get("universe_total") else 0.0
                ),
            }
            for item in self._repository.list(status=status, limit=limit)
        ]

    def supersede(
        self,
        campaign_id: int,
        replacement_campaign_id: int,
        *,
        message: str,
    ) -> dict:
        self._repository.supersede(
            campaign_id,
            replacement_campaign_id,
            message=message,
        )
        return self.get(campaign_id)

    def reconcile_active(self, *, limit: int = 20) -> int:
        reconciled = 0
        for campaign_id in self._repository.runnable_ids(limit=limit):
            try:
                self.reconcile(campaign_id)
                reconciled += 1
            except Exception:
                # One malformed or temporarily unavailable campaign must not
                # starve every later campaign in this Scheduler tick.
                logger.exception(
                    "fan-out campaign reconciliation failed: %s", campaign_id
                )
        return reconciled

    def _ensure_factor_value_universe_seed(self, campaign: dict) -> dict:
        """Durably discover factor names on a fresh database.

        ``factor_list`` is not available to every token. A single bounded
        factor_value request for one locally known stock returns the factor
        catalog and is normalized before this campaign freezes its universe.
        The seed is a normal durable job, so it inherits retries, quota deferral
        and failure evidence instead of making an untracked synchronous call.
        """
        from service.collection_jobs.service import CollectionJobService

        stocks = self._job_repository.list_fanout_values("stock")
        if not stocks:
            raise InvalidTaskParametersError(
                "factor_value fan-out needs stock_basic before factor discovery"
            )
        parameters: dict[str, Any] = {"ts_code": stocks[0]}
        if campaign["request"].get("trade_date"):
            trade_date = str(campaign["request"]["trade_date"])
            parameters["trade_date"] = date.fromisoformat(trade_date).strftime("%Y%m%d")
        job_service = CollectionJobService(self._job_repository, TASKS)
        job, _ = job_service.submit(
            "tushare_interface",
            {
                "api_name": "factor_value",
                "parameters": parameters,
                "complete": True,
                "resume": True,
            },
            max_attempts=3,
            idempotency_key=f"fanout-campaign-{campaign['campaign_id']}-factor-seed",
            api_name="factor_value",
            cadence=campaign["cadence"],
            period_key=campaign.get("period_key"),
            expected_for=campaign.get("expected_for"),
            priority=70 if campaign["cadence"] == "daily" else 30,
            resource_class=(
                "initialization"
                if campaign["cadence"] == "initialization"
                else "fanout"
            ),
        )
        return job

    def reconcile(self, campaign_id: int) -> dict:
        with self._repository.reconcile_lock(campaign_id) as acquired:
            if not acquired:
                return self.get(campaign_id)
            campaign = self._repository.get(campaign_id)
            if not campaign:
                raise JobNotFoundError(f"fan-out campaign not found: {campaign_id}")
            if campaign["status"] != "running":
                return self.get(campaign_id)

            pages = self._repository.pages(campaign_id)
            self._repository.update_progress(campaign_id)
            if pages:
                latest = pages[-1]
                page_state = self._repository.page_state(latest["batch_job_id"])
                if page_state["active"]:
                    return self.get(campaign_id)
                if page_state["failed"] or not page_state["verified"]:
                    self._repository.set_status(
                        campaign_id,
                        "attention",
                        "incomplete",
                        error_message=(
                            f"fan-out page {latest['page_index']} is not verified: "
                            f"failed={page_state['failed']}, "
                            f"succeeded={page_state['succeeded']}/{page_state['total']}"
                        ),
                    )
                    return self.get(campaign_id)
                plan = (latest.get("completion_evidence") or {}).get("plan") or {}
                if not plan:
                    # The immutable plan also lives on the batch parameters,
                    # but every fan-out parent stores it in evidence at creation.
                    self._repository.set_status(
                        campaign_id,
                        "attention",
                        "incomplete",
                        error_message="fan-out page is missing immutable plan evidence",
                    )
                    return self.get(campaign_id)
                if not plan.get("has_more"):
                    self._repository.update_progress(campaign_id)
                    refreshed = self._repository.get(campaign_id)
                    completion = "complete" if refreshed["rows_fetched"] else "empty"
                    self._repository.set_status(
                        campaign_id, "success", completion, error_message=None
                    )
                    return self.get(campaign_id)
                offset = int(plan["next_offset"])
            else:
                offset = 0

            page_index = len(pages)
            page_request = {
                **campaign["request"],
                "offset": offset,
                "max_children": campaign["page_size"],
            }
            try:
                definition = FANOUT_DEFINITIONS[campaign["api_name"]]
                universe = self._repository.universe_values(campaign_id)
                if not universe:
                    source_values = (
                        list(definition.static_values)
                        if definition.source == "static"
                        else self._job_repository.list_fanout_values(
                            definition.source,
                            as_of=campaign.get("expected_for"),
                        )
                    )
                    if not source_values and definition.source == "factor_name":
                        seed = self._ensure_factor_value_universe_seed(campaign)
                        if seed["status"] == "failed":
                            self._repository.set_status(
                                campaign_id,
                                "attention",
                                "incomplete",
                                error_message=(
                                    "factor-name discovery job failed: "
                                    f"job_id={seed['job_id']}; "
                                    f"{seed.get('error_message') or 'no error detail'}"
                                )[:4000],
                            )
                        elif seed["status"] == "success":
                            self._repository.set_status(
                                campaign_id,
                                "attention",
                                "incomplete",
                                error_message=(
                                    "factor-name discovery completed but produced no "
                                    "normalized factor names"
                                ),
                            )
                        return self.get(campaign_id)
                    self._repository.freeze_universe(
                        campaign_id,
                        source=definition.source,
                        values=source_values,
                        digest=_universe_digest(source_values),
                    )
                    universe = self._repository.universe_values(campaign_id)
                    campaign = self._repository.get(campaign_id)
                priority = {
                    "daily": 70,
                    "weekly": 40,
                    "monthly": 30,
                    "quarterly": 25,
                    "initialization": 30,
                }.get(campaign["cadence"], 20)
                batch, _ = self._planner.create_batch(
                    page_request,
                    idempotency_key=(
                        f"fanout-campaign-{campaign_id}-page-{page_index}"
                    ),
                    universe_values=universe,
                    universe_source=campaign["universe_source"],
                    cadence=campaign["cadence"],
                    period_key_override=campaign.get("period_key"),
                    expected_for_override=campaign.get("expected_for"),
                    priority=priority,
                    resource_class=(
                        "initialization"
                        if campaign["cadence"] == "initialization"
                        else "fanout"
                    ),
                )
                self._repository.attach_page(campaign_id, batch)
            except Exception as exc:
                self._repository.set_status(
                    campaign_id,
                    "attention",
                    "incomplete",
                    error_message=f"{type(exc).__name__}: {exc}"[:4000],
                )
            return self.get(campaign_id)

    def pause(self, campaign_id: int) -> dict:
        with self._repository.reconcile_lock(campaign_id) as acquired:
            if not acquired:
                raise JobConflictError(
                    "fan-out campaign is being reconciled; retry pause"
                )
            campaign = self.get(campaign_id)
            if campaign["status"] != "running":
                raise JobConflictError(
                    "only a running fan-out campaign can be paused"
                )
            self._repository.set_status(campaign_id, "paused", "incomplete")
        return self.get(campaign_id)

    def resume(self, campaign_id: int) -> dict:
        with self._repository.reconcile_lock(campaign_id) as acquired:
            if not acquired:
                raise JobConflictError(
                    "fan-out campaign is being reconciled; retry resume"
                )
            campaign = self.get(campaign_id)
            if campaign["status"] not in {"paused", "attention"}:
                raise JobConflictError(
                    "only a paused or attention fan-out campaign can resume"
                )
            if campaign["status"] == "attention":
                for job_id in self._repository.failed_child_ids(campaign_id):
                    self._job_repository.requeue_failed_batch_child(job_id)
            self._repository.set_status(campaign_id, "running", "running")
        return self.reconcile(campaign_id)
