from datetime import timedelta

from service.clock import business_now
from service.research.external_provider import FinancialResearchEvidenceService
from service.source_connectors.contracts import AcquisitionMode, ConnectorResult


class FakeBroker:
    def __init__(self, *, fail: Exception | None = None):
        self.calls = []
        self.fail = fail

    def query(self, request, **options):
        self.calls.append((request, options))
        if self.fail:
            raise self.fail
        results = []
        for item in request.parameters["requests"]:
            route = item["url"]
            if route.endswith("consensus-stats"):
                fields = ["symbol", "end_date", "est_eps_add"]
                rows = [["300750.SZ", "2026-10-10", 3]]
            elif route.endswith("tech-indicators"):
                fields = ["symbol", "end_date", "rsi", "macd"]
                rows = [["300750.SZ", "2026-10-10", 42.0, -1.2]]
            else:
                fields = ["symbol", "end_date"]
                rows = [["300750.SZ", "2026-10-10"]]
            results.append({
                "url": route,
                "meta": {"fields": fields},
                "data": rows,
            })
        return ConnectorResult(
            source_id="financial_data",
            endpoint_key="common_query",
            acquisition_mode=AcquisitionMode.QUERY_THROUGH,
            records=({"status": "SUCCESS", "results": results},),
            fetched_rows=len(results),
            status="complete",
            evidence={"cache": "miss", "fetched_at": "2026-10-11T00:00:00Z"},
        )


def test_fundamental_evidence_batches_provider_routes_and_preserves_lineage():
    broker = FakeBroker()
    service = FinancialResearchEvidenceService(broker)

    result = service.fundamentals(
        "300750.SZ", as_of=business_now().date()
    )

    assert result["status"] == "ready"
    assert result["source_id"] == "financial_data"
    assert result["data"]["consensus_statistics"]["latest"]["est_eps_add"] == 3
    assert result["normalized"]["schema_version"] == (
        "research-fundamental-evidence/v1"
    )
    assert result["normalized"]["consensus_revision"]["eps_upgrades"] == 3
    assert len(result["provenance"]) == 3
    request, options = broker.calls[0]
    assert len(request.parameters["requests"]) == 3
    assert options["cache_ttl_seconds"] == 21_600


def test_historical_evidence_omits_routes_without_cutoff_contracts():
    broker = FakeBroker()
    service = FinancialResearchEvidenceService(broker)
    historical = business_now().date() - timedelta(days=1)

    fundamentals = service.fundamentals("300750.SZ", as_of=historical)
    technicals = service.technicals("300750.SZ", as_of=historical)

    assert len(broker.calls[0][0].parameters["requests"]) == 2
    assert fundamentals["omitted"][0]["source_dataset"].endswith("target-price")
    assert len(broker.calls[1][0].parameters["requests"]) == 1
    assert all(
        item["reason"] == "provider route has no historical cutoff contract"
        for item in technicals["omitted"]
    )


def test_provider_failure_is_explicit_and_does_not_fabricate_evidence():
    service = FinancialResearchEvidenceService(
        FakeBroker(fail=TimeoutError("secret upstream detail"))
    )

    result = service.fundamentals(
        "300750.SZ", as_of=business_now().date()
    )

    assert result["status"] == "unavailable"
    assert result["error"] == {
        "code": "TimeoutError",
        "message": "蚂蚁数据源 evidence is temporarily unavailable",
    }
    assert all(item["state"] == "unavailable" for item in result["provenance"])


def test_one_malformed_route_does_not_discard_valid_batch_results():
    class PartialBroker(FakeBroker):
        def query(self, request, **options):
            result = super().query(request, **options)
            response = dict(result.records[0])
            items = [dict(item) for item in response["results"]]
            items[0] = {**items[0], "meta": {"fields": []}}
            return ConnectorResult(
                source_id=result.source_id,
                endpoint_key=result.endpoint_key,
                acquisition_mode=result.acquisition_mode,
                records=({**response, "results": items},),
                fetched_rows=result.fetched_rows,
                status=result.status,
                evidence=result.evidence,
            )

    result = FinancialResearchEvidenceService(PartialBroker()).fundamentals(
        "300750.SZ", as_of=business_now().date()
    )

    assert result["status"] == "partial"
    assert result["data"]["consensus_statistics"]["status"] == "unavailable"
    assert result["data"]["rating_summary"]["status"] == "available"
    assert result["data"]["target_price"]["status"] == "available"
    assert result["provenance"][0]["state"] == "unavailable"
    assert result["route_errors"]["consensus_statistics"]["code"] == (
        "FinancialDataProtocolError"
    )


def test_technical_evidence_merges_route_errors_from_current_batch():
    class CurrentPartialBroker(FakeBroker):
        def query(self, request, **options):
            result = super().query(request, **options)
            if len(self.calls) == 2:
                response = dict(result.records[0])
                items = [dict(item) for item in response["results"]]
                items[0] = {**items[0], "meta": {"fields": []}}
                return ConnectorResult(
                    source_id=result.source_id,
                    endpoint_key=result.endpoint_key,
                    acquisition_mode=result.acquisition_mode,
                    records=({**response, "results": items},),
                    fetched_rows=result.fetched_rows,
                    status=result.status,
                    evidence=result.evidence,
                )
            return result

    result = FinancialResearchEvidenceService(CurrentPartialBroker()).technicals(
        "300750.SZ", as_of=business_now().date()
    )

    assert result["status"] == "partial"
    assert result["data"]["provider_indicators"]["status"] == "available"
    assert result["data"]["provider_patterns"]["status"] == "unavailable"
    assert result["route_errors"]["provider_patterns"]["code"] == (
        "FinancialDataProtocolError"
    )


def test_provider_date_filter_is_not_a_point_in_time_guarantee():
    service = FinancialResearchEvidenceService(FakeBroker())
    for cutoff in (business_now().date(), business_now().date() - timedelta(days=1)):
        assert service.fundamentals("300750.SZ", as_of=cutoff)["point_in_time_safe"] is False
        assert service.technicals("300750.SZ", as_of=cutoff)["point_in_time_safe"] is False
