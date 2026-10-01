from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException

from service.api.routers import sources as source_routes
from service.source_connectors.contracts import (
    AcquisitionMode,
    ConnectorRequest,
    ConnectorResult,
    EndpointSpec,
    SourceKind,
    SourceSpec,
)
from service.source_connectors.chinamoney import (
    ChinaMoneyConnector,
    parse_lpr_payload,
)
from service.source_connectors.financial_data import (
    FinancialDataConnector,
    validate_common_query,
)
from service.source_connectors.financial_data_catalog import FINANCIAL_DATA_ROUTES
from service.source_connectors.query_broker import QueryBroker, QueryCircuitOpenError
from service.source_connectors.registry import SOURCE_REGISTRY, SourceRegistry
from service.source_connectors.web_snapshot import (
    FetchedArtifact,
    ParserDriftError,
    WebSnapshotConnector,
)


def _source(mode: AcquisitionMode) -> SourceSpec:
    return SourceSpec(
        source_id="sample",
        display_name="Sample",
        kind=SourceKind.API,
        acquisition_modes=(mode,),
    )


def _registry(mode: AcquisitionMode, *, ttl: int | None = None) -> SourceRegistry:
    source = _source(mode)
    return SourceRegistry(
        (source,),
        (EndpointSpec(
            source_id="sample",
            endpoint_key="prices",
            title="Prices",
            acquisition_mode=mode,
            cache_ttl_seconds=ttl,
            parser_name="sample_parser",
            parser_version="1",
        ),),
    )


def test_tushare_is_registered_as_first_multi_source_adapter():
    source = SOURCE_REGISTRY.get_source("tushare")
    endpoints = SOURCE_REGISTRY.list_endpoints("tushare")
    assert source.kind == SourceKind.API
    assert AcquisitionMode.SCHEDULED_PULL in source.acquisition_modes
    assert len(endpoints) >= 180
    assert SOURCE_REGISTRY.get_endpoint("tushare", "daily").cadence == "daily"


def test_chinamoney_official_lpr_endpoint_is_registered():
    source = SOURCE_REGISTRY.get_source("chinamoney")
    endpoint = SOURCE_REGISTRY.get_endpoint("chinamoney", "lpr_history")

    assert source.display_name.startswith("中国货币网")
    assert endpoint.cadence == "monthly"
    assert endpoint.completeness_policy["authoritative"] is True


def test_financial_data_query_through_source_is_registered_without_secret():
    source = SOURCE_REGISTRY.get_source("financial_data")
    endpoint = SOURCE_REGISTRY.get_endpoint("financial_data", "common_query")
    assert source.credential_ref == "env:FINANCIAL_DATA_API_KEY"
    assert source.license_policy["persist_raw_records"] is False
    assert endpoint.acquisition_mode == AcquisitionMode.QUERY_THROUGH
    assert endpoint.request_contract["catalog_discovered_routes"] == 163
    assert len(FINANCIAL_DATA_ROUTES) == 163


def test_financial_data_gateway_is_registered_in_openapi():
    from service.api.app import create_app

    class FakeDatabase:
        def close(self):
            pass

    paths = create_app(database_factory=FakeDatabase).openapi()["paths"]
    assert "post" in paths["/api/v1/data/sources/financial_data/query"]


def test_financial_data_connector_validates_and_returns_protocol_payload():
    calls = []
    connector = FinancialDataConnector(
        api_key="test-only",
        transport=lambda payload: calls.append(payload) or {
            "status": "SUCCESS",
            "results": [{
                "url": "/api/v1/quote/basic-snapshot",
                "meta": {"fields": ["symbol", "last"]},
                "data": [["600519.SH", 100.0]],
            }],
        },
    )
    result = connector.query(ConnectorRequest(
        source_id="financial_data",
        endpoint_key="common_query",
        acquisition_mode=AcquisitionMode.QUERY_THROUGH,
        parameters={
            "mode": "data",
            "requests": [{
                "url": "/api/v1/quote/basic-snapshot",
                "params": {"symbols": ["600519.SH"]},
            }],
        },
    ))
    assert calls[0]["mode"] == "data"
    assert result.status == "complete"
    assert result.fetched_rows == 1
    assert result.evidence["api_version"] == "1.6.0"
    assert result.records[0]["status"] == "SUCCESS"


def test_financial_data_connector_rejects_absolute_or_uncatalogued_urls():
    with pytest.raises(ValueError, match="audited catalog"):
        validate_common_query({
            "mode": "data",
            "requests": [{
                "url": "https://example.test/api/v1/quote",
                "params": {},
            }],
        })
    with pytest.raises(ValueError, match="audited catalog"):
        validate_common_query({
            "mode": "data",
            "requests": [{"url": "/api/v1/unknown", "params": {}}],
        })
    assert validate_common_query({
        "mode": "data",
        "requests": [{
            "url": "/api/v2/info/news/article",
            "params": {"id": "example"},
        }],
    })["requests"][0]["url"] == "/api/v2/info/news/article"
    with pytest.raises(ValueError, match="only a params"):
        validate_common_query({
            "mode": "tool_recall",
            "requests": [{"url": "/api/v1/x", "params": {}}],
        })


def test_financial_data_route_rejects_bad_input_before_open_circuit(monkeypatch):
    class CircuitMustNotBeConsulted:
        def query(self, _request):
            raise AssertionError("invalid local input reached query broker")

    monkeypatch.setattr(
        source_routes,
        "_QUERY_BROKER",
        CircuitMustNotBeConsulted(),
    )
    with pytest.raises(HTTPException) as error:
        source_routes.query_financial_data({
            "mode": "data",
            "requests": [{"url": "/api/v1/unknown", "params": {}}],
        })
    assert error.value.status_code == 422


def test_chinamoney_lpr_connector_parses_archives_and_stores_official_record():
    content = b'''{
      "head": {"rep_code": "200", "rep_message": ""},
      "data": {"baseCurveCfgList": ["1Y", "5Y"]},
      "records": [{
        "showDateCN": "2024-11-20",
        "showDateEN": "20 Nov 2024",
        "1Y": "3.10",
        "5Y": "3.60"
      }]
    }'''
    parsed = parse_lpr_payload(content)
    archive_calls = []
    store_calls = []

    class Archive:
        def archive_response(self, **kwargs):
            archive_calls.append(kwargs)
            return {
                "request_id": 9,
                "request_hash": "a" * 64,
                "logical_request_hash": "b" * 64,
            }

    connector = ChinaMoneyConnector(
        fetcher=lambda start, end: (
            content,
            f"https://official.test/lpr?start={start}&end={end}",
        ),
        archive=Archive(),
        store=lambda records, evidence: (
            store_calls.append((records, evidence)) or len(records)
        ),
    )
    result = connector.execute(ConnectorRequest(
        source_id="chinamoney",
        endpoint_key="lpr_history",
        acquisition_mode=AcquisitionMode.SCHEDULED_PULL,
        parameters={"start_date": "2024-11-01", "end_date": "2024-11-30"},
    ))

    assert parsed[0]["publication_date"].isoformat() == "2024-11-20"
    assert str(parsed[0]["one_year"]) == "3.10"
    assert str(parsed[0]["five_year"]) == "3.60"
    assert result.status == "complete"
    assert result.fetched_rows == result.stored_rows == 1
    assert result.evidence["verification_type"] == (
        "official_monthly_history_response"
    )
    assert archive_calls[0]["endpoint_key"] == "lpr_history"
    assert store_calls[0][0][0]["raw"]["showDateCN"] == "2024-11-20"


def test_chinamoney_lpr_connector_accepts_persisted_source_job_shape():
    content = b'''{
      "head": {"rep_code": "200", "rep_message": ""},
      "records": [{"showDateCN": "2024-11-20", "1Y": "3.10", "5Y": "3.60"}]
    }'''
    requested_ranges = []

    class Archive:
        def archive_response(self, **_kwargs):
            return {
                "request_id": 10,
                "request_hash": "c" * 64,
                "logical_request_hash": "d" * 64,
            }

    connector = ChinaMoneyConnector(
        fetcher=lambda start, end: (
            requested_ranges.append((start, end))
            or (content, "https://official.test/lpr")
        ),
        archive=Archive(),
        store=lambda records, _evidence: len(records),
    )
    result = connector.execute(ConnectorRequest(
        source_id="chinamoney",
        endpoint_key="lpr_history",
        acquisition_mode=AcquisitionMode.SCHEDULED_PULL,
        parameters={
            "parameters": {
                "start_date": "2024-11-01",
                "end_date": "2024-11-30",
            },
            "fields": None,
            "complete": True,
            "page_size": None,
            "max_pages": None,
            "resume": True,
        },
    ))

    assert requested_ranges[0][0].isoformat() == "2024-11-01"
    assert requested_ranges[0][1].isoformat() == "2024-11-30"
    assert result.stored_rows == 1


def test_source_registry_rejects_endpoint_mode_not_supported_by_source():
    source = _source(AcquisitionMode.SCHEDULED_PULL)
    registry = SourceRegistry((source,))
    with pytest.raises(ValueError, match="not supported"):
        registry.register_endpoint(EndpointSpec(
            source_id="sample",
            endpoint_key="prices",
            title="Prices",
            acquisition_mode=AcquisitionMode.QUERY_THROUGH,
        ))


class _QueryConnector:
    def __init__(self, source):
        self.source = source
        self.calls = 0
        self.failure = None

    def query(self, request):
        self.calls += 1
        if self.failure:
            raise self.failure
        return ConnectorResult(
            source_id=request.source_id,
            endpoint_key=request.endpoint_key,
            acquisition_mode=request.acquisition_mode,
            records=({"price": 10},),
            fetched_rows=1,
            status="complete",
        )


def test_query_broker_caches_and_falls_back_to_stale_after_failure():
    now = datetime(2026, 9, 21, tzinfo=timezone.utc)
    clock = [now]
    registry = _registry(AcquisitionMode.QUERY_THROUGH, ttl=10)
    connector = _QueryConnector(registry.get_source("sample"))
    broker = QueryBroker(
        registry=registry,
        connector_resolver=lambda _source_id: connector,
        failure_threshold=1,
        clock=lambda: clock[0],
    )
    request = ConnectorRequest(
        source_id="sample",
        endpoint_key="prices",
        acquisition_mode=AcquisitionMode.QUERY_THROUGH,
        parameters={"symbol": "A"},
    )
    assert broker.query(request).evidence["cache"] == "miss"
    assert broker.query(request).evidence["cache"] == "hit"
    clock[0] += timedelta(seconds=11)
    connector.failure = RuntimeError("upstream unavailable")
    assert broker.query(request).evidence["cache"] == "stale"
    with pytest.raises(QueryCircuitOpenError):
        broker.query(request, allow_stale=False)


class _Archive:
    def __init__(self):
        self.calls = []

    def archive_artifact(self, **kwargs):
        self.calls.append(kwargs)
        return {"artifact_id": 7, "content_hash": "abc"}


def test_web_snapshot_archives_before_parsing_and_keeps_parser_lineage():
    registry = _registry(AcquisitionMode.WEB_SNAPSHOT)
    archive = _Archive()
    fetched_at = datetime(2026, 9, 21, tzinfo=timezone.utc)
    connector = WebSnapshotConnector(
        source=registry.get_source("sample"),
        registry=registry,
        fetcher=lambda _request: FetchedArtifact(
            url="https://example.test/prices",
            status_code=200,
            content_type="text/html",
            content=b"<table></table>",
            headers={"etag": "v1"},
            fetched_at=fetched_at,
        ),
        parser=lambda _content, _request: ({"price": 10},),
        archive=archive,
    )
    request = ConnectorRequest(
        source_id="sample",
        endpoint_key="prices",
        acquisition_mode=AcquisitionMode.WEB_SNAPSHOT,
    )
    result = connector.execute(request)
    assert result.status == "complete"
    assert result.evidence["artifact_id"] == 7
    assert archive.calls[0]["parser_version"] == "1"


def test_web_snapshot_parser_drift_preserves_artifact_id():
    registry = _registry(AcquisitionMode.WEB_SNAPSHOT)
    archive = _Archive()
    connector = WebSnapshotConnector(
        source=registry.get_source("sample"),
        registry=registry,
        fetcher=lambda _request: FetchedArtifact(
            url="https://example.test/prices",
            status_code=200,
            content_type="text/html",
            content=b"changed",
            headers={},
            fetched_at=datetime.now(timezone.utc),
        ),
        parser=lambda *_args: (_ for _ in ()).throw(ValueError("selector missing")),
        archive=archive,
    )
    with pytest.raises(ParserDriftError, match="artifact_id=7"):
        connector.execute(ConnectorRequest(
            source_id="sample",
            endpoint_key="prices",
            acquisition_mode=AcquisitionMode.WEB_SNAPSHOT,
        ))
    assert len(archive.calls) == 1
