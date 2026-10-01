"""V2-only installation audit and missing-history recovery."""

from __future__ import annotations

from datetime import date, timedelta
import hashlib
import time

from service.clock import business_today
from service.data_coverage.registry import COVERAGE_RULES
from service.data_coverage.service import CoverageService
from service.initialization.repository import InitializationRepository
from service.orchestration_v2.gap_repair import (
    create_repair_executions,
    current_problem_partitions,
    plan_current_repairs,
)
from service.orchestration_v2.repository import OrchestrationV2Repository


_TERMINAL = frozenset({"success", "attention", "superseded", "cancelled"})


class InitializationService:
    """Treat initialization as grouped V2 audits and execution instances."""

    def __init__(
        self,
        repository: InitializationRepository | None = None,
        orchestration_repository: OrchestrationV2Repository | None = None,
        coverage_service: CoverageService | None = None,
    ):
        self._repository = repository or InitializationRepository()
        self._orchestration = orchestration_repository or OrchestrationV2Repository()
        self._coverage = coverage_service or CoverageService()

    @staticmethod
    def _bounds(history_start: date | None, history_end: date | None) -> tuple[date, date]:
        end = history_end or (business_today() - timedelta(days=1))
        start = history_start or date(1990, 1, 1)
        if start > end:
            raise ValueError("history_start must not be later than history_end")
        if end >= business_today():
            raise ValueError("initialization history_end must be a completed day")
        return start, end

    def preflight(self, *, profile: str, history_start=None, history_end=None) -> dict:
        start, end = self._bounds(history_start, history_end)
        rules = [rule for rule in COVERAGE_RULES.list() if rule.auditable]
        active = self._orchestration.control_plane_summary()
        return {
            "engine": "orchestration_v2",
            "profile": profile,
            "history_start": start,
            "history_end": end,
            "auditable_datasets": len(rules),
            "active_acquisition_tasks": active["definitions"].get("acquisition:active", 0),
            "checks": {
                "v2_installed": active["status"] == "installed",
                "all_audits_code_owned": all(rule.strict_audit_mode for rule in rules),
                "v1_required": False,
            },
        }

    def start(
        self,
        *,
        profile: str,
        history_start=None,
        history_end=None,
        auto_activate: bool = True,
        idempotency_key: str | None = None,
    ) -> tuple[dict, bool]:
        start, end = self._bounds(history_start, history_end)
        identity = idempotency_key or f"{profile}:{start}:{end}"
        digest = int(hashlib.sha256(identity.encode()).hexdigest()[:14], 16)
        initialization_id = digest or int(time.time() * 1_000_000)
        existing = self._repository.audit_jobs(initialization_id)
        if existing:
            return self.get(initialization_id), False
        datasets = [rule.dataset_name for rule in COVERAGE_RULES.list() if rule.auditable]
        self._coverage.submit_audits(
            datasets,
            start_date=start,
            end_date=end,
            idempotency_key=f"v2-init:{initialization_id}:audit",
        )
        campaign = self.reconcile(initialization_id)
        campaign["auto_activate"] = auto_activate
        return campaign, True

    def get(self, initialization_id: int) -> dict:
        audits = self._repository.audit_jobs(initialization_id)
        executions = self._repository.executions(initialization_id)
        if not audits and not executions:
            raise LookupError(f"V2 initialization not found: {initialization_id}")
        initial_audits = [
            row for row in audits if ":verify:" not in row.get("idempotency_key", "")
        ]
        verification_audits = [
            row for row in audits if ":verify:" in row.get("idempotency_key", "")
        ]
        verification_rounds = {
            self._verification_round(row.get("idempotency_key", "")): row
            for row in verification_audits
        }
        latest_verification_round = max(verification_rounds, default=0)
        latest_verification_audits = [
            row for row in verification_audits
            if self._verification_round(row.get("idempotency_key", ""))
            == latest_verification_round
        ]
        audit_counts = self._counts(audits)
        initial_audit_counts = self._counts(initial_audits)
        verification_counts = self._counts(latest_verification_audits)
        execution_counts = self._counts(executions)
        audit_failed = initial_audit_counts.get("failed", 0) + verification_counts.get(
            "failed", 0
        )
        execution_failed = execution_counts.get("attention", 0)
        active = sum(
            count for status, count in execution_counts.items() if status not in _TERMINAL
        )
        # Only a successful repair can change business data and require a new
        # post-repair verification round.  Superseded/cancelled scopes are
        # retained as audit history but must not make an otherwise complete
        # historical campaign perpetually verification-pending.
        latest_execution_id = max(
            (
                int(row["task_execution_id"])
                for row in executions
                if row.get("status") == "success"
            ),
            default=0,
        )
        campaign_start, campaign_end = self._audit_bounds(initialization_id)
        campaign_problems = current_problem_partitions(
            start_date=campaign_start,
            end_date=campaign_end,
        )
        if audit_failed or execution_failed:
            status = "attention"
        elif initial_audit_counts.get("queued", 0) or initial_audit_counts.get(
            "running", 0
        ):
            status = "auditing"
        elif active:
            status = "collecting"
        elif executions and latest_verification_round < latest_execution_id:
            status = "verification_pending"
        elif verification_counts.get("queued", 0) or verification_counts.get(
            "running", 0
        ):
            status = "verifying"
        elif latest_verification_audits and verification_counts.get(
            "success", 0
        ) == len(latest_verification_audits):
            status = "attention" if campaign_problems else "ready"
        elif initial_audits and initial_audit_counts.get("success", 0) == len(
            initial_audits
        ):
            status = "attention" if campaign_problems else "ready"
        else:
            status = "pending"
        return {
            "initialization_id": initialization_id,
            "engine": "orchestration_v2",
            "status": status,
            "audit_counts": audit_counts,
            "verification_counts": verification_counts,
            "latest_verification_round": latest_verification_round or None,
            "execution_counts": execution_counts,
            "planned_steps": len(audits) + len(executions),
            "completed_steps": (
                audit_counts.get("success", 0)
                + audit_counts.get("failed", 0)
                + sum(
                    execution_counts.get(item, 0)
                    for item in _TERMINAL
                )
            ),
            "failed_steps": audit_failed + execution_failed,
            "current_phase": (
                "complete"
                if status == "ready"
                else "audit"
                if status in {"auditing", "verification_pending", "verifying"}
                else "recover"
            ),
            "phase_name": (
                "initialization_complete"
                if status == "ready"
                else "strict_data_audit"
                if status == "auditing"
                else "strict_post_repair_verification"
                if status in {"verification_pending", "verifying"}
                else "v2_gap_recovery"
            ),
        }

    @staticmethod
    def _verification_round(idempotency_key: str) -> int:
        marker = ":verify:"
        if marker not in idempotency_key:
            return 0
        value = idempotency_key.split(marker, 1)[1].split(":", 1)[0]
        try:
            return int(value)
        except ValueError:
            return 0

    @staticmethod
    def _counts(rows: list[dict]) -> dict[str, int]:
        counts: dict[str, int] = {}
        for row in rows:
            key = str(row["status"])
            counts[key] = counts.get(key, 0) + 1
        return counts

    def list_steps(self, initialization_id: int, *, limit: int = 500) -> list[dict]:
        audits = [
            {**item, "resource_type": "strict_audit"}
            for item in self._repository.audit_jobs(initialization_id)
        ]
        executions = [
            {**item, "resource_type": "v2_execution"}
            for item in self._repository.executions(initialization_id, limit=limit)
        ]
        return (audits + executions)[:limit]

    def reconcile(self, initialization_id: int) -> dict:
        current = self.get(initialization_id)
        if current["status"] == "verification_pending":
            executions = self._repository.executions(initialization_id)
            verification_round = max(
                (int(row["task_execution_id"]) for row in executions),
                default=0,
            )
            datasets = [
                rule.dataset_name for rule in COVERAGE_RULES.list() if rule.auditable
            ]
            start, end = self._audit_bounds(initialization_id)
            self._coverage.submit_audits(
                datasets,
                start_date=start,
                end_date=end,
                idempotency_key=(
                    f"v2-init:{initialization_id}:verify:{verification_round}"
                ),
            )
            return self.get(initialization_id)
        if current["status"] == "attention" and not current["failed_steps"]:
            start, end = self._audit_bounds(initialization_id)
            proposals = plan_current_repairs(
                self._orchestration,
                start_date=start,
                end_date=end,
            )
            audits = self._repository.audit_jobs(initialization_id)
            audit_round = max((int(row["job_id"]) for row in audits), default=0)
            create_repair_executions(
                self._orchestration,
                proposals=proposals,
                purpose="initialization",
                trigger_source="recovery",
                frozen_scope_extra={"initialization_id": str(initialization_id)},
                idempotency_prefix=f"v2:init:{initialization_id}:a{audit_round}",
            )
            current = self.get(initialization_id)
        return current

    def _audit_bounds(self, initialization_id: int) -> tuple[date, date]:
        audits = self._repository.audit_jobs(initialization_id)
        starts = [row["start_date"] for row in audits if row.get("start_date")]
        ends = [row["end_date"] for row in audits if row.get("end_date")]
        if not starts or not ends:
            raise LookupError(f"V2 initialization has no audit bounds: {initialization_id}")
        return min(starts), max(ends)

    def reconcile_active(self) -> dict | None:
        latest = self._repository.find_latest_id()
        return self.reconcile(latest) if latest is not None else None

    def overview(self) -> dict:
        latest = self._repository.find_latest_id()
        return {
            "engine": "orchestration_v2",
            "latest": self.reconcile(latest) if latest is not None else None,
            "v1_required": False,
        }

    def pause(self, initialization_id: int) -> dict:
        self.get(initialization_id)
        self._repository.set_execution_status(initialization_id, "paused")
        return self.get(initialization_id)

    def resume(self, initialization_id: int) -> dict:
        self.get(initialization_id)
        self._repository.set_execution_status(initialization_id, "resumed")
        return self.reconcile(initialization_id)

    def activate(self, initialization_id: int) -> dict:
        campaign = self.reconcile(initialization_id)
        if campaign["status"] != "ready":
            raise ValueError("initialization is not strictly ready")
        return campaign
