from service.collection_jobs.fanout_campaigns import FanoutCampaignService


class ActiveCampaignRepository:
    def runnable_ids(self, *, limit):
        assert limit == 20
        return [11, 12, 13]


def test_active_reconciliation_isolates_one_broken_campaign():
    service = FanoutCampaignService.__new__(FanoutCampaignService)
    service._repository = ActiveCampaignRepository()
    visited = []

    def reconcile(campaign_id):
        visited.append(campaign_id)
        if campaign_id == 12:
            raise RuntimeError("broken campaign")

    service.reconcile = reconcile

    assert service.reconcile_active(limit=20) == 2
    assert visited == [11, 12, 13]


class SeedJobRepository:
    def __init__(self):
        self.created = None

    def list_fanout_values(self, source, *, as_of=None):
        assert source == "stock"
        assert as_of is None
        return ["000001.SZ"]

    def create(self, task_name, parameters, **options):
        self.created = (task_name, parameters, options)
        return {
            "job_id": 99,
            "task_name": task_name,
            "parameters": parameters,
            "status": "queued",
        }, True


def test_factor_universe_discovery_is_a_durable_bounded_job():
    service = FanoutCampaignService.__new__(FanoutCampaignService)
    service._job_repository = SeedJobRepository()

    job = service._ensure_factor_value_universe_seed(
        {
            "campaign_id": 48,
            "request": {"api_name": "factor_value", "trade_date": "2026-08-28"},
            "cadence": "daily",
            "period_key": "2026-08-28",
            "expected_for": None,
        }
    )

    task_name, parameters, options = service._job_repository.created
    assert job["status"] == "queued"
    assert task_name == "tushare_interface"
    assert parameters["parameters"] == {
        "ts_code": "000001.SZ",
        "trade_date": "20260828",
    }
    assert options["idempotency_key"] == "fanout-campaign-48-factor-seed"
    assert options["resource_class"] == "fanout"
