"""Recover durable audits after a coverage rule semantics upgrade."""

from __future__ import annotations

from service.data_coverage.registry import COVERAGE_RULES, CoverageRuleRegistry
from service.data_coverage.repository import CoverageRepository


class CoverageRuleReconciler:
    """Queue database-only re-audits for results made stale by rule changes."""

    def __init__(
        self,
        repository: CoverageRepository | None = None,
        registry: CoverageRuleRegistry = COVERAGE_RULES,
    ):
        self._repository = repository or CoverageRepository()
        self._registry = registry

    def reconcile(self, *, limit_per_rule: int = 500) -> dict[str, int]:
        requeued: dict[str, int] = {}
        for rule in self._registry.list():
            if rule.revision <= 1:
                continue
            count = self._repository.requeue_stale_rule_audits(
                rule.dataset_name,
                rule_revision=rule.revision,
                limit=limit_per_rule,
            )
            if count:
                requeued[rule.dataset_name] = count
        return requeued
