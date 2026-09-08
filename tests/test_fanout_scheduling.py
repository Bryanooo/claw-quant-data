from datetime import date

import service.fanout_scheduling as scheduling


class FakeCampaignService:
    def __init__(self):
        self.calls = []
        self.keys = set()

    def submit(self, request, **options):
        key = options["idempotency_key"]
        created = key not in self.keys
        self.keys.add(key)
        self.calls.append((request, options))
        return {"campaign_id": len(self.calls)}, created


def test_daily_fanout_recipes_use_closed_and_bounded_scopes(monkeypatch):
    import service.initialization.repository as initialization_repository

    monkeypatch.setattr(
        initialization_repository, "routine_collection_enabled", lambda: True
    )
    monkeypatch.setattr(scheduling, "_latest_trade_date", lambda _day: "20260828")
    service = FakeCampaignService()

    first = scheduling.submit_scheduled_fanouts(
        "daily", today=date(2026, 8, 30), service=service
    )
    second = scheduling.submit_scheduled_fanouts(
        "daily", today=date(2026, 8, 30), service=service
    )

    daily_count = sum(
        recipe.cadence == "daily" for recipe in scheduling.SCHEDULED_FANOUT_RECIPES
    )
    assert first == {"created": daily_count, "existing": 0, "failed": 0}
    assert second == {"created": 0, "existing": daily_count, "failed": 0}
    requests = {call[0]["api_name"]: call[0] for call in service.calls[:daily_count]}
    assert requests["dc_index"]["trade_date"] == date(2026, 8, 28)
    assert requests["dc_index"]["page_size"] == 1
    assert requests["fut_index_daily"]["page_size"] == 56
    assert requests["cb_share"]["ann_date"] == date(2026, 8, 29)
    factor_options = next(
        options for request, options in service.calls[:daily_count]
        if request["api_name"] == "factor_value"
    )
    assert factor_options["idempotency_key"].endswith(":v2")
    assert factor_options["plan_version"] == 2
    assert factor_options["reuse_scope"] is True


def test_post_close_daily_fanouts_use_current_trade_date(monkeypatch):
    import service.initialization.repository as initialization_repository

    monkeypatch.setattr(
        initialization_repository, "routine_collection_enabled", lambda: True
    )
    monkeypatch.setattr(scheduling, "_latest_trade_date", lambda day: day.strftime("%Y%m%d"))
    service = FakeCampaignService()

    result = scheduling.submit_scheduled_fanouts(
        "daily",
        today=date(2026, 8, 31),
        include_current_daily=True,
        service=service,
    )

    assert result["created"] == sum(
        recipe.cadence == "daily" for recipe in scheduling.SCHEDULED_FANOUT_RECIPES
    )
    requests = {call[0]["api_name"]: call[0] for call in service.calls}
    assert requests["dc_index"]["trade_date"] == date(2026, 8, 31)
    assert requests["cb_share"]["ann_date"] == date(2026, 8, 31)


def test_weekly_and_monthly_fanouts_have_stable_closed_period_identity(monkeypatch):
    import service.initialization.repository as initialization_repository

    monkeypatch.setattr(
        initialization_repository, "routine_collection_enabled", lambda: True
    )
    service = FakeCampaignService()

    weekly = scheduling.submit_scheduled_fanouts(
        "weekly", today=date(2026, 8, 30), service=service
    )
    monthly = scheduling.submit_scheduled_fanouts(
        "monthly", today=date(2026, 8, 30), service=service
    )

    weekly_count = sum(
        recipe.cadence == "weekly" for recipe in scheduling.SCHEDULED_FANOUT_RECIPES
    )
    assert weekly["created"] == weekly_count
    assert monthly["created"] == 1
    assert all(
        options["period_key"] == "2026-W34"
        for _, options in service.calls[:weekly_count]
    )
    ths_request, ths_options = next(
        (request, options) for request, options in service.calls
        if request["api_name"] == "ths_member"
    )
    assert ths_request["page_size"] == 200
    assert ths_options["plan_version"] == 2
    assert service.calls[-1][1]["period_key"] == "2026-07"
    assert service.calls[-1][1]["expected_for"] == date(2026, 7, 31)


def test_routine_gate_prevents_scheduled_fanout_side_effects(monkeypatch):
    import service.initialization.repository as initialization_repository

    monkeypatch.setattr(
        initialization_repository, "routine_collection_enabled", lambda: False
    )
    service = FakeCampaignService()

    result = scheduling.submit_scheduled_fanouts(
        "weekly", today=date(2026, 8, 30), service=service
    )

    assert result == {"created": 0, "existing": 0, "failed": 0}
    assert service.calls == []
