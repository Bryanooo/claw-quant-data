import json
from pathlib import Path

from service.api.routers.datasets import (
    get_source_priorities,
    get_tushare_financial_mapping,
)
from service.data_service.provider_equivalence import (
    ANNOUNCEMENT_PARSE_ROUTES,
    DERIVED_EQUIVALENTS,
    DIRECT_EQUIVALENTS,
    EQUIVALENCE_CLASSES,
    FINANCIAL_DATA_ONLY,
    PARTIAL_TUSHARE_OVERLAPS,
    TUSHARE_ANNOUNCEMENT_PARSE,
    TUSHARE_DERIVED,
    TUSHARE_DIRECT,
    financial_tushare_catalog,
    financial_tushare_mapping,
    financial_tushare_summary,
    tushare_financial_reverse_catalog,
    tushare_financial_reverse_summary,
)
from service.source_connectors.financial_data_catalog import FINANCIAL_DATA_ROUTES


def test_all_financial_routes_are_classified_once_in_the_four_class_model():
    items = financial_tushare_catalog()
    summary = financial_tushare_summary(items)

    assert len(items) == 163
    assert {item.route for item in items} == FINANCIAL_DATA_ROUTES
    assert {item.equivalence_class for item in items} == set(EQUIVALENCE_CLASSES)
    assert summary["tushare_direct"] == 26
    assert summary["tushare_derived"] == 34
    assert summary["tushare_announcement_parse"] == 22
    assert summary["financial_data_only"] == 81
    assert sum(summary[name] for name in EQUIVALENCE_CLASSES) == 163


def test_full_equivalence_classes_are_disjoint_and_partial_is_not_promoted():
    direct = set(DIRECT_EQUIVALENTS)
    derived = set(DERIVED_EQUIVALENTS)
    announcement = set(ANNOUNCEMENT_PARSE_ROUTES)

    assert not direct & derived
    assert not direct & announcement
    assert not derived & announcement
    assert not set(PARTIAL_TUSHARE_OVERLAPS) & (
        direct | derived | announcement
    )
    assert set(PARTIAL_TUSHARE_OVERLAPS) <= (
        FINANCIAL_DATA_ROUTES - direct - derived - announcement
    )


def test_every_referenced_tushare_api_exists_in_the_244_contract_catalog():
    payload = json.loads(
        (Path("docs") / "tushare" / "contracts.json").read_text(
            encoding="utf-8"
        )
    )
    contracts = {item["api_name"] for item in payload["interfaces"]}
    referenced = {
        api
        for item in financial_tushare_catalog()
        for api in (
            *item.tushare_interfaces,
            *item.related_tushare_interfaces,
        )
    }

    assert len(payload["interfaces"]) == 244
    assert sum(item["collectable"] for item in payload["interfaces"]) == 201
    assert referenced <= contracts


def test_permission_and_vendor_capability_are_not_conflated():
    auction = financial_tushare_mapping("/api/v1/quote/auction-snapshot")
    block_trade = financial_tushare_mapping(
        "/api/v1/stock/block-trading-details"
    )
    announcement = financial_tushare_mapping(
        "/api/v1/stock_fnd/actual-controller"
    )
    macro = financial_tushare_mapping("/api/v1/macro/data-query")

    assert auction.equivalence_class == FINANCIAL_DATA_ONLY
    assert auction.coverage == "partial_overlap_only"
    assert block_trade.equivalence_class == TUSHARE_DIRECT
    assert block_trade.as_dict()["current_token_ready"] is True
    assert announcement.equivalence_class == TUSHARE_ANNOUNCEMENT_PARSE
    assert announcement.as_dict()["current_token_ready"] is False
    assert announcement.as_dict()["tushare_interfaces"][0]["permission"] == "无权限"
    assert macro.equivalence_class == FINANCIAL_DATA_ONLY
    assert macro.coverage == "partial_overlap_only"


def test_derived_routes_name_inputs_and_carry_derivation_warning():
    item = financial_tushare_mapping(
        "/api/v1/index_fnd/index-fnd-financial-statement"
    )

    assert item.equivalence_class == TUSHARE_DERIVED
    assert {"index_weight", "income", "balancesheet", "cashflow"} <= set(
        item.tushare_interfaces
    )
    assert "版本化" in item.rationale


def test_source_priority_api_exposes_and_filters_provider_equivalence():
    result = get_source_priorities(
        dependency_class=None,
        equivalence_class=TUSHARE_ANNOUNCEMENT_PARSE,
        requires_financial_data=None,
        current_token_ready=False,
        namespace=None,
        limit=500,
        offset=0,
    )

    assert result["page"]["total"] == 22
    assert result["provider_equivalence_summary"]["financial_data_routes"] == 163
    assert all(
        item["provider_equivalence"]["equivalence_class"]
        == TUSHARE_ANNOUNCEMENT_PARSE
        for item in result["items"]
    )
    assert all(
        item["provider_equivalence"]["current_token_ready"] is False
        for item in result["items"]
    )


def test_reverse_catalog_covers_every_tushare_contract_once():
    items = tushare_financial_reverse_catalog()
    summary = tushare_financial_reverse_summary(items)

    assert len(items) == 244
    assert len({item["api_name"] for item in items}) == 244
    assert sum(
        summary[name]
        for name in (
            "full_equivalence_input",
            "partial_overlap_only",
            "no_financial_data_counterpart",
        )
    ) == 244
    auction = next(item for item in items if item["api_name"] == "stk_auction")
    assert auction["full_equivalence_routes"] == []
    assert auction["partial_overlap_routes"] == [
        "/api/v1/quote/auction-snapshot"
    ]


def test_reverse_mapping_api_is_filterable():
    result = get_tushare_financial_mapping(
        mapping_status="no_financial_data_counterpart",
        permission="有权限",
        collectable=True,
        query="可转债",
        limit=500,
        offset=0,
    )

    assert result["summary"]["tushare_contracts"] == 244
    assert result["items"]
    assert all(
        item["mapping_status"] == "no_financial_data_counterpart"
        and item["permission"] == "有权限"
        and item["collectable"] is True
        and "可转债" in item["title"]
        for item in result["items"]
    )
