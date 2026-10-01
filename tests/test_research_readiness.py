from datetime import date

from service.data_service.registry import DATASETS
from service.research.readiness import (
    RESEARCH_DATA_CONTRACTS,
    evaluate_research_readiness,
)
from service.research.validation import (
    RESEARCH_VALIDATION_CASES,
    validate_research_response,
)


AS_OF = date(2026, 9, 22)


def _complete_evidence():
    dataset_names = {
        dependency["dataset"]
        for contract in RESEARCH_DATA_CONTRACTS
        for dependency in contract["dependencies"]
    }
    coverage = {"datasets": []}
    freshness = []
    for name in sorted(dataset_names):
        specification = DATASETS.get(name)
        freshness.append({
            "dataset": name,
            "status": "fresh" if specification.date_column else "not_applicable",
            "latest_date": AS_OF if specification.date_column else None,
            "estimated_rows": 100,
        })
        coverage["datasets"].append({
            "dataset": name,
            "auditable": bool(specification.date_column),
            "latest": (
                {
                    "status": "complete",
                    "start_date": date(1990, 1, 1),
                    "end_date": AS_OF,
                    "missing_partitions": 0,
                    "partial_partitions": 0,
                }
                if specification.date_column
                else None
            ),
        })
    return coverage, freshness


def test_every_research_dependency_references_a_public_dataset():
    contract_ids = [item["id"] for item in RESEARCH_DATA_CONTRACTS]
    assert len(contract_ids) == len(set(contract_ids))
    for contract in RESEARCH_DATA_CONTRACTS:
        assert contract["dependencies"]
        for dependency in contract["dependencies"]:
            assert DATASETS.get(dependency["dataset"])


def test_research_readiness_requires_fresh_and_strict_historical_evidence():
    coverage, freshness = _complete_evidence()

    result = evaluate_research_readiness(
        coverage=coverage, freshness=freshness, as_of=AS_OF
    )

    assert result["status"] == "ready"
    assert result["summary"]["ready_capabilities"] == len(
        RESEARCH_DATA_CONTRACTS
    )
    macro = next(
        item for item in result["capabilities"] if item["id"] == "macro-regime"
    )
    assert macro["status"] == "ready"

    stock_daily = next(
        item for item in coverage["datasets"]
        if item["dataset"] == "stock_daily"
    )
    stock_daily["latest"]["start_date"] = date(2026, 5, 25)
    result = evaluate_research_readiness(
        coverage=coverage, freshness=freshness, as_of=AS_OF
    )

    technicals = next(
        item for item in result["capabilities"] if item["id"] == "technicals"
    )
    dependency = next(
        item for item in technicals["dependencies"]
        if item["dataset"] == "stock_daily"
    )
    assert technicals["status"] == "degraded"
    assert dependency["state"] == "unverified"
    assert dependency["history_status"] == "range_insufficient"


def test_task_success_cannot_hide_a_confirmed_data_gap():
    coverage, freshness = _complete_evidence()
    stock_daily = next(
        item for item in coverage["datasets"]
        if item["dataset"] == "stock_daily"
    )
    stock_daily["latest"].update(
        status="gaps", missing_partitions=2, partial_partitions=1
    )

    result = evaluate_research_readiness(
        coverage=coverage, freshness=freshness, as_of=AS_OF
    )

    technicals = next(
        item for item in result["capabilities"] if item["id"] == "technicals"
    )
    assert technicals["status"] == "degraded"
    evidence = next(
        item for item in technicals["dependencies"]
        if item["dataset"] == "stock_daily"
    )
    assert evidence["history_status"] == "gaps"
    assert evidence["missing_partitions"] == 2


def test_readiness_respects_audited_provider_availability_boundary():
    coverage, freshness = _complete_evidence()
    tdx = next(
        item for item in coverage["datasets"]
        if item["dataset"] == "tdx_daily"
    )
    tdx["latest"].update(
        start_date=date(2025, 3, 28),
        verified_start_date=date(2025, 3, 28),
        evidence={"availability_start": "2025-03-28"},
    )

    result = evaluate_research_readiness(
        coverage=coverage,
        freshness=freshness,
        as_of=AS_OF,
    )
    capability = next(
        item for item in result["capabilities"]
        if item["id"] == "instrument-technicals-sector"
    )
    dependency = next(
        item for item in capability["dependencies"]
        if item["dataset"] == "tdx_daily"
    )

    assert dependency["state"] == "ready"
    assert dependency["history_status"] == "strictly_verified"
    assert dependency["required_history_start"] == date(2023, 9, 24)
    assert dependency["provider_availability_start"] == date(2025, 3, 28)
    assert dependency["effective_required_history_start"] == date(2025, 3, 28)


def test_readiness_uses_merged_verified_span_instead_of_latest_window_only():
    coverage, freshness = _complete_evidence()
    stock_daily = next(
        item for item in coverage["datasets"]
        if item["dataset"] == "stock_daily"
    )
    stock_daily["latest"].update(
        start_date=date(2026, 5, 25),
        verified_start_date=date(1990, 12, 19),
        verified_end_date=AS_OF,
    )

    result = evaluate_research_readiness(
        coverage=coverage, freshness=freshness, as_of=AS_OF
    )

    technicals = next(
        item for item in result["capabilities"] if item["id"] == "technicals"
    )
    dependency = next(
        item for item in technicals["dependencies"]
        if item["dataset"] == "stock_daily"
    )
    assert dependency["state"] == "ready"
    assert dependency["audited_start"] == date(1990, 12, 19)


def test_readiness_rejects_audit_that_ends_before_latest_data():
    coverage, freshness = _complete_evidence()
    stock_daily = next(
        item for item in coverage["datasets"]
        if item["dataset"] == "stock_daily"
    )
    stock_daily["latest"]["end_date"] = date(2026, 9, 20)

    result = evaluate_research_readiness(
        coverage=coverage, freshness=freshness, as_of=AS_OF
    )

    technicals = next(
        item for item in result["capabilities"] if item["id"] == "technicals"
    )
    dependency = next(
        item for item in technicals["dependencies"]
        if item["dataset"] == "stock_daily"
    )
    assert dependency["state"] == "unverified"
    assert dependency["history_status"] == "audit_behind_latest_data"


def test_research_validation_set_has_unique_cases_and_enforces_history_shape():
    ids = [item["id"] for item in RESEARCH_VALIDATION_CASES]
    assert len(ids) == len(set(ids))
    assert len(RESEARCH_VALIDATION_CASES) >= 10
    case = {
        "required_paths": ["data.items", "meta.quality.status"],
        "minimum_lengths": {"data.items": 2},
    }
    assert validate_research_response(
        case, 200, {"data": {"items": [1]}, "meta": {"quality": {"status": "ready"}}}
    ) == ["data.items has 1 item(s), expected at least 2"]
