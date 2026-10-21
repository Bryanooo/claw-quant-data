from service.data_coverage.reconciliation import CoverageRuleReconciler
from service.data_coverage.registry import COVERAGE_RULES


class FakeRepository:
    def __init__(self):
        self.calls = []

    def requeue_stale_rule_audits(
        self, dataset_name, *, rule_revision, limit
    ):
        self.calls.append((dataset_name, rule_revision, limit))
        return 37 if dataset_name == "index_daily" else 0


def test_rule_reconciler_only_requeues_versioned_obsolete_audits():
    repository = FakeRepository()

    result = CoverageRuleReconciler(repository=repository).reconcile(
        limit_per_rule=100
    )

    assert result == {"index_daily": 37}
    assert repository.calls == [
        (rule.dataset_name, rule.revision, 100)
        for rule in COVERAGE_RULES.list()
        if rule.revision > 1
    ]
    assert ("cyq_chips", 2, 100) in repository.calls
    assert ("hk_daily", 2, 100) in repository.calls
    assert ("stk_factor_pro", 5, 100) in repository.calls
