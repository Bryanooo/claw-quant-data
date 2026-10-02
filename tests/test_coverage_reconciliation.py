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
            ("bak_daily", 3, 100),
            ("balancesheet", 4, 100),
            ("cashflow", 4, 100),
            ("cb_daily", 3, 100),
            ("ci_daily", 2, 100),
            ("cn_gdp", 2, 100),
            ("cn_lpr", 3, 100),
            ("cn_pmi", 2, 100),
        ("cn_ppi", 2, 100),
        ("etf_share_size", 3, 100),
            ("financial_indicator", 4, 100),
            ("fund_share", 2, 100),
            ("ggt_monthly", 2, 100),
            ("income", 4, 100),
        ("index_daily", 4, 100),
        ("index_dailybasic", 2, 100),
            ("industry_daily", 2, 100),
            ("margin", 2, 100),
            ("margin_detail", 2, 100),
            ("moneyflow", 2, 100),
            ("moneyflow_cnt_ths", 3, 100),
            ("moneyflow_ind_dc", 3, 100),
            ("moneyflow_ind_ths", 3, 100),
            ("moneyflow_ths", 3, 100),
        ("repurchase", 3, 100),
        ("sf_month", 2, 100),
        ("sge_daily", 2, 100),
        ("shibor", 2, 100),
        ("stock_daily", 2, 100),
        ("stock_daily_basic", 2, 100),
            ("stock_limit", 2, 100),
            ("sw_daily", 2, 100),
            ("sz_daily_info", 3, 100),
            ("tdx_daily", 2, 100),
        ("tdx_index", 2, 100),
        ("ths_hot", 3, 100),
    ]
