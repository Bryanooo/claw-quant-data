from service.data_service.registry import DATASETS
from service.research.factor_inputs import FACTOR_INPUT_BUNDLES, factor_input_catalog
from scripts.audit_factor_lab_supply import DOMAINS


def test_factor_input_contract_is_versioned_and_resolves_public_datasets():
    catalog = factor_input_catalog()
    assert catalog["contract"] == "claw-factor-inputs@v1"
    ids = [bundle["id"] for bundle in catalog["bundles"]]
    assert len(ids) == len(set(ids)) == len(FACTOR_INPUT_BUNDLES)
    registered = {item.name for item in DATASETS.list()}
    for bundle in catalog["bundles"]:
        assert bundle["datasets"]
        assert {item["name"] for item in bundle["datasets"]} <= registered


def test_financial_bundle_declares_point_in_time_semantics():
    catalog = factor_input_catalog()
    bundle = next(
        item for item in catalog["bundles"]
        if item["id"] == "fundamentals_pit@v1"
    )
    assert bundle["point_in_time"] is True
    assert all(item["availability_column"] for item in bundle["datasets"])
    assert "disclosure_date" in bundle["excluded"]


def test_contract_distinguishes_continuous_and_optional_history():
    catalog = factor_input_catalog()
    bundles = {item["id"]: item for item in catalog["bundles"]}
    assert (
        bundles["flow_sentiment@v1"]["dataset_policies"]["moneyflow"]["coverage_mode"]
        == "stock_daily_sessions"
    )
    assert (
        bundles["fundamentals_pit@v1"]["dataset_policies"]["forecast"]["required"]
        is False
    )
    assert (
        bundles["core_daily@v1"]["dataset_policies"]["index_weight"]["required"]
        is False
    )


def test_factor_input_catalog_exposes_every_research_domain():
    bundle_ids = {bundle["id"] for bundle in factor_input_catalog()["bundles"]}

    assert {
        "core_daily@v1",
        "fundamentals_pit@v1",
        "fundamentals_reference@v1",
        "corporate_events@v1",
        "company_news@v1",
        "flow_sentiment@v1",
        "etf_market@v1",
        "index_industry@v1",
        "macro@v1",
    } <= bundle_ids

    delivered = {
        dataset["name"]
        for bundle in factor_input_catalog()["bundles"]
        for dataset in bundle["datasets"]
    }
    assert not {
        dataset
        for datasets in DOMAINS.values()
        for dataset in datasets
        if dataset not in delivered
    }
