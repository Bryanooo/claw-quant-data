"""Public adapter contract tests: malformed data must not become empty success."""
from datetime import datetime, timezone
from io import BytesIO
import json

import pandas as pd
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
import requests

from service.api.routers import sources
from service.source_connectors import public_parsers as parsers
from service.source_connectors.contracts import AcquisitionMode, ConnectorRequest
from service.source_connectors.public_catalog import PUBLIC_ENDPOINTS, validate_public_request
from service.source_connectors.public_web import PublicWebConnector, BoundedTransport
from service.source_connectors.query_broker import QueryBroker
from service.source_connectors.registry import SOURCE_REGISTRY


def response(value, *, encoding="utf-8", date="Thu, 15 Oct 2026 16:00:00 GMT"):
    r = requests.Response()
    r.status_code = 200
    r.url = "https://example.test/fixture"
    r.headers["Date"] = date
    r._content = value if isinstance(value, bytes) else (json.dumps(value, ensure_ascii=False) if isinstance(value, dict) else value).encode(encoding)
    return r


class Transport:
    def __init__(self, *responses):
        self.responses = iter(responses)
        self.calls = []
        self.urls = []

    def __call__(self, url, **kwargs):
        self.calls.append((url, kwargs))
        self.urls.append(url)
        value = next(self.responses)
        if isinstance(value, Exception):
            raise value
        return value


def query(source, endpoint, parameters, *responses, archive=None):
    http = Transport(*responses)
    connector = PublicWebConnector(SOURCE_REGISTRY.get_source(source), transport_factory=lambda: http, archive=archive)
    result = connector.query(ConnectorRequest(source, endpoint, AcquisitionMode.QUERY_THROUGH, parameters))
    return result, http


@pytest.mark.parametrize("source,endpoint,params", [
    ("cninfo", "investor_questions", {"code": "600519"}),
    ("sse", "investor_questions", {"code": "002594"}),
    ("sse", "investor_questions", {"page": True}),
    ("sina", "option_quote", {"code": "10012345&list=secret"}),
    ("sina", "option_contracts", {"underlying": "bad"}),
    ("chinamoney", "repo_fixing", {"kind": "SHIBOR"}),
    ("pboc", "social_financing", {"year": 2020}),
    ("chinabond", "yield_curve", {"start": "2024-01-01", "end": "2025-01-01"}),
    ("chinabond", "yield_curve", {"start": "2024-02-30", "end": "2024-03-01"}),
    ("pboc", "social_financing", {"year": 2025, "url": "https://evil.test"}),
])
def test_invalid_requests_rejected_before_transport(source, endpoint, params):
    with pytest.raises(ValueError):
        validate_public_request(source, endpoint, params)


def test_cninfo_exact_match_and_query_string_and_timezone():
    result, http = query("cninfo", "investor_questions", {"code": "002594"},
        response({"data": [{"code": "002595", "secid": "wrong"}, {"code": "002594", "secid": "right"}]}),
        response({"rows": [{"stockCode": "002594", "mainContent": "question", "pubDate": 1792022400000}]}))
    assert http.calls[1][1]["params"]["orgId"] == "right"
    assert "data" not in http.calls[1][1]
    assert result.records[0]["question_time"].endswith("+08:00")
    assert result.status == "page" and result.records[0]["answer"] is None
    assert result.evidence["history_verified"] is False


@pytest.mark.parametrize("rows", [None, {}, [{"stockCode": "002595", "mainContent": "q"}]])
def test_cninfo_drift_or_wrong_company_is_error(rows):
    with pytest.raises(RuntimeError):
        query("cninfo", "investor_questions", {"code": "002594"}, response({"data": [{"code": "002594", "secid": "right"}]}), response({"rows": rows}))


def sse_html(qtime="2026年10月14日 10:20", atime="昨天 18:16"):
    return ('<div class="m_feed_item m_qa_item" id="item-123">'
            '<div class="m_feed_detail m_qa_detail"><div class="m_feed_txt"><a>:公司(600000)</a>问题</div>'
            f'<div class="m_feed_from"><span>{qtime}</span></div></div>'
            '<div class="m_feed_detail m_qa"><div class="m_feed_txt">回答</div>'
            f'<div class="m_feed_from"><span>{atime}</span></div></div></div>')


def test_sse_relative_time_uses_shanghai_server_date_and_retains_original():
    result, _ = query("sse", "investor_questions", {}, response(sse_html()))
    row = result.records[0]
    assert row["answer_time"] == "2026-10-15T18:16:00+08:00"
    assert row["answer_time_raw"] == "昨天 18:16"
    assert row["time_reference_basis"] == "http_date"
    assert parsers.SSE_REFERENCE_TIME.get() is None


@pytest.mark.parametrize("html", ["", "<html>captcha</html>", sse_html(atime="unknown")])
def test_sse_changed_page_and_time_are_errors(html):
    with pytest.raises(RuntimeError):
        query("sse", "investor_questions", {}, response(html))


def test_sse_explicit_empty_is_allowed():
    result, _ = query("sse", "investor_questions", {}, response('<a class="m_feed_note">近1个月暂无回复</a>'))
    assert result.status == "empty"


def test_sina_greeks_positions_and_iv_decimal():
    fields = ["期权", "", "", "", "10", "0.5", "0.01", "-0.2", "0.7", "0.1735", "2", "1", "trade", "3", "1.5", "1.4"]
    result, _ = query("sina", "option_greeks", {"code": "10012345"}, response('var hq_str_CON_SO_10012345="' + ','.join(fields) + '";', encoding="gbk"))
    assert result.records[0]["delta"] == 0.5
    assert result.records[0]["iv"] == 0.1735
    assert result.evidence["observed_start"] is None


def test_sina_quote_mapping():
    v = [str(i) for i in range(43)]
    v[37] = "期权"
    result, _ = query("sina", "option_quote", {"code": "10012345"}, response('var hq_str_CON_OP_10012345="' + ','.join(v) + '";', encoding="gbk"))
    assert result.records[0]["strike"] == 7
    assert result.records[0]["amount"] == 42


def test_sina_contracts_do_not_drop_first_valid_month():
    result, _ = query("sina", "option_contracts", {}, response({"result": {"data": {"contractMonth": ["2026-10", "2026-11"]}}}),
        response('var hq_str_OP_UP_5100502610="CON_OP_10012345,";'),
        response('var hq_str_OP_UP_5100502611="CON_OP_10012346,";'))
    assert [r["month"] for r in result.records] == ["2610", "2611"]


@pytest.mark.parametrize("text", ['', 'var hq_str_CON_SO_10012345="";', 'var hq_str_CON_SO_10012345="name,1,2,3,4";'])
def test_sina_missing_response_is_not_empty_success(text):
    with pytest.raises(RuntimeError):
        query("sina", "option_greeks", {"code": "10012345"}, response(text))


def test_repo_fixing_units_fields_and_duplicates():
    row = "2026-10-14,,,,,,1.2,1.4,1.5"
    result, _ = query("chinamoney", "repo_fixing", {"kind": "FDR"}, response(row))
    assert result.records[0]["FDR007"] == 1.4
    assert "FR007" not in result.records[0]
    for text in [row + '\n' + row, '2026-10-14,,,,,,,,', '2026-10-14,changed,,,,,1,2,3']:
        with pytest.raises(RuntimeError):
            query("chinamoney", "repo_fixing", {}, response(text))


def bond_html(rows):
    header = '<tr>' + ''.join('<th>' + h + '</th>' for h in parsers._CHINABOND_HEADER) + '</tr>'
    return '<table></table><table>' + header + ''.join('<tr>' + ''.join('<td>' + v + '</td>' for v in row) + '</tr>' for row in rows) + '</table>'


def test_chinabond_requires_all_requested_curves_and_exact_dates():
    rows = [[name, "2026-10-14"] + ["1.5"] * 8 for name in parsers.CHINABOND_CURVE_NAMES.values()]
    p = {"start": "2026-10-14", "end": "2026-10-14", "curve": "all"}
    result, _ = query("chinabond", "yield_curve", p, response(bond_html(rows)))
    assert len(result.records) == 3
    for invalid in [rows[:2], rows + rows[:1], [[rows[0][0], "2026-10-13"] + ["1"] * 8]]:
        with pytest.raises(RuntimeError):
            query("chinabond", "yield_curve", p, response(bond_html(invalid)))


PBOC_HEADERS = ["月份", "社会融资规模增量", "人民币贷款", "外币贷款（折合人民币）", "委托贷款", "信托贷款", "未贴现银行承兑汇票", "企业债券", "政府债券", "非金融企业境内股票融资", "存款类金融机构资产支持证券", "贷款核销"]


def pboc_responses(*, headers=None, value=100):
    book = BytesIO()
    pd.DataFrame([headers or PBOC_HEADERS, [None] * 12, [None] * 12,
                  [2025.01, value] + [1] * 10, [2025.1, 200] + [2] * 10,
                  [2025.12] + [None] * 11]).to_excel(book, index=False, header=False)
    return (response('<a href="/year">2025年统计数据</a>'), response('<a href="/topic">社会融资规模</a>'), response('<a href="/table.xlsx">附件</a>'), response(book.getvalue()))


def test_pboc_october_label_and_unpublished_month():
    result, _ = query("pboc", "social_financing", {"year": 2025}, *pboc_responses())
    assert [r["month"] for r in result.records] == ["2025-01", "2025-10"]
    assert result.records[0]["afre_total"] == 100


def test_pboc_column_swap_and_bad_number_are_not_silent_nulls():
    headers = PBOC_HEADERS.copy()
    headers[2], headers[3] = headers[3], headers[2]
    for fixtures in [pboc_responses(headers=headers), pboc_responses(value="broken")]:
        with pytest.raises(RuntimeError):
            query("pboc", "social_financing", {"year": 2025}, *fixtures)
    with pytest.raises(RuntimeError):
        parsers._abs_pbc("https://evil.test/file.xlsx")


def test_broker_capability_checks_precede_network_and_cache_is_bounded():
    http = Transport(response('2026-10-14,,,,,,1,2,3'), response('2026-10-14,,,,,,4,5,6'))
    connector = PublicWebConnector(SOURCE_REGISTRY.get_source("chinamoney"), transport_factory=lambda: http)
    broker = QueryBroker(registry=SOURCE_REGISTRY, connector_resolver=lambda _: connector, max_cache_entries=1)
    request = ConnectorRequest("chinamoney", "repo_fixing", AcquisitionMode.QUERY_THROUGH, {"kind": "FR"})
    for kwargs in [{"required_fields": ("FDR007",)}, {"require_point_in_time": True}]:
        with pytest.raises(ValueError):
            broker.query(request, **kwargs)
    assert not http.calls
    assert broker.query(request, required_fields=("FR007",)).evidence["cache"] == "miss"
    assert broker.query(request).evidence["cache"] == "hit"
    broker.query(ConnectorRequest("chinamoney", "repo_fixing", AcquisitionMode.QUERY_THROUGH, {"kind": "FDR"}))
    assert len(broker._cache) == 1


def test_public_api_errors_aliases_and_discovery(monkeypatch):
    app = FastAPI()
    app.include_router(sources.router)
    client = TestClient(app)
    assert client.get('/v1/data/sources/ant_data').json()['display_name'] == '蚂蚁数据源'
    assert client.get('/v1/data/sources/ant_data/route-contracts').json()['total'] == 163
    assert client.post('/v1/data/sources/pboc/endpoints/social_financing/query', json={'parameters': {'year': 2020}}).status_code == 422
    assert client.post('/v1/data/sources/nope/endpoints/x/query', json={}).status_code == 404
    assert len(PUBLIC_ENDPOINTS) == 8
    assert all(e.capabilities['point_in_time'] is False for e in PUBLIC_ENDPOINTS)
    schema = app.openapi()
    assert '/v1/data/sources/ant_data/query' in schema['paths']
    assert schema['paths']['/v1/data/sources/financial_data/query']['post']['deprecated'] is True


def test_audit_failure_does_not_hide_data_and_raw_records_not_persisted():
    class Archive:
        def archive_response(self, **kwargs):
            assert kwargs['persist_records'] is False
            raise OSError('offline')
    result, _ = query('chinamoney', 'repo_fixing', {}, response('2026-10-14,,,,,,1,2,3'), archive=Archive())
    assert any('audit unavailable' in w for w in result.warnings)


@pytest.mark.parametrize('url', ['https://evil.test/a', 'http://www.pbc.gov.cn/a', 'https://www.pbc.gov.cn:444/a'])
def test_transport_rejects_unapproved_targets(url):
    with pytest.raises(RuntimeError):
        BoundedTransport()(url)


def test_ant_alias_reuses_durable_identity_and_cache():
    from service.source_connectors.contracts import ConnectorResult
    calls = []
    class Connector:
        def query(self, request):
            calls.append(request.source_id)
            return ConnectorResult(request.source_id, request.endpoint_key, request.acquisition_mode, status="complete")
    broker = QueryBroker(registry=SOURCE_REGISTRY, connector_resolver=lambda source: Connector())
    for source in ('ant_data', 'financial_data'):
        broker.query(ConnectorRequest(source, 'common_query', AcquisitionMode.QUERY_THROUGH, {}))
    assert calls == ['financial_data']


def test_registry_persistence_includes_capabilities_without_new_schema(monkeypatch):
    from unittest.mock import MagicMock
    from service.source_connectors.persistence import sync_source_registry
    import psycopg2.extras
    batches = []
    monkeypatch.setattr(psycopg2.extras, 'execute_values', lambda cursor, sql, values, **kwargs: batches.append(values))
    sync_source_registry(MagicMock())
    source_ids = {row[0] for row in batches[0]}
    assert {'cninfo', 'sse', 'sina', 'chinabond', 'pboc'} <= source_ids
    endpoint = next(row for row in batches[1] if row[:2] == ('pboc', 'social_financing'))
    contract = endpoint[9].adapted
    assert contract['x-capabilities']['point_in_time'] is False
    assert contract['x-capabilities']['units'] == 'CNY_100million'


def test_research_gateway_keeps_supplemental_evidence_separate(monkeypatch):
    from service.api.routers import research
    app = FastAPI()
    app.include_router(research.router)
    client = TestClient(app)
    discovery = client.get('/v1/research/public-evidence/capabilities').json()
    assert discovery['total'] == 8 and discovery['canonical'] is False
    assert client.post('/v1/research/public-evidence/pboc/social_financing', json={'parameters': {'year': 2020}}).status_code == 422
    monkeypatch.setattr(research, 'query_public_source', lambda *args: {'data': [], 'meta': {'status': 'empty'}})
    result = client.post('/v1/research/public-evidence/pboc/social_financing', json={'parameters': {'year': 2025}}).json()
    assert result['evidence_only'] is True and result['point_in_time'] is False
