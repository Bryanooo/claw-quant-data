from service.data_coverage.reconciliation import CoverageRuleReconciler
from service.data_coverage.registry import COVERAGE_RULES


class FakeRepository:
    def __init__(self):
        self.calls = []

    def queue_stale_partition_audits(self, versions, *, limit):
        assert versions == {r.dataset_name:r.revision for r in COVERAGE_RULES.list()
                            if r.date_partitioned and r.revision > 1}
        assert limit == 4
        return {"index_daily": 2}

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

    assert result == {"index_daily": 2}
    assert repository.calls == [
        (rule.dataset_name, rule.revision, 100)
        for rule in COVERAGE_RULES.list()
        if not rule.date_partitioned and rule.revision > 1
    ]
