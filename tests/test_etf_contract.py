from service.data_service.etf_contract import etf_rotation_contract


def test_reviewed_actions_have_unique_dates_and_provenance():
    contract = etf_rotation_contract()
    actions = contract["evidence"]["share_transformations"]
    assert len(actions) == 8
    assert len({(e["symbol"], e["price_effective_date"]) for e in actions}) == 8
    for event in actions:
        assert event["new_shares_per_old_share"] > 0
        assert event["registration_date"] <= event["price_effective_date"]
        assert event["source_url"].startswith("https://")
    assert not any(contract["capabilities"].values())
