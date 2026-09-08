from service.data_coverage.reconciliation import CoverageRuleReconciler


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
        ("balancesheet", 3, 100),
        ("cashflow", 3, 100),
        ("financial_indicator", 3, 100),
        ("income", 3, 100),
        ("index_daily", 4, 100),
    ]
