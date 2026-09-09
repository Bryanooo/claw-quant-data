import csv
import io
import json
import socket
from urllib.error import URLError

import pytest

from service.cli.client import (
    ApiClient,
    CliError,
    EXIT_API_CLIENT,
    EXIT_CONNECTION,
    EXIT_INVALID_RESPONSE,
    EXIT_TIMEOUT,
)
from service.cli.main import DEFAULT_API_URL, main


class FakeClient:
    def __init__(self, responses=None):
        self.responses = responses or {}
        self.calls = []

    def get(self, path, *, params=None):
        self.calls.append((path, params))
        response = self.responses.get(path, {})
        if isinstance(response, Exception):
            raise response
        return response


class FakeResponse:
    def __init__(self, status_code, payload, *, headers=None, reason=""):
        self.status_code = status_code
        self.payload = payload
        self.headers = headers or {}
        self.reason = reason

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def getcode(self):
        return self.status_code

    def read(self):
        if isinstance(self.payload, bytes):
            return self.payload
        return json.dumps(self.payload).encode("utf-8")


class FakeOpener:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.calls = []

    def __call__(self, request, **kwargs):
        self.calls.append((request, kwargs))
        if self.error:
            raise self.error
        return self.response


def run_cli(arguments, client, capsys):
    exit_code = main(
        arguments,
        client_factory=lambda *_args, **_kwargs: client,
    )
    captured = capsys.readouterr()
    return exit_code, captured


def test_health_checks_live_and_ready(capsys):
    client = FakeClient(
        {
            "/health/live": {"status": "ok"},
            "/health/ready": {"status": "ready", "database": "ok"},
        }
    )

    exit_code, captured = run_cli(["health"], client, capsys)

    assert exit_code == 0
    assert json.loads(captured.out) == {
        "live": {"status": "ok"},
        "ready": {"database": "ok", "status": "ready"},
    }
    assert client.calls == [("/health/live", None), ("/health/ready", None)]
    assert captured.err == ""


def test_status_returns_consolidated_data_health(capsys):
    client = FakeClient(
        {
            "/v1/data-health/summary": {
                "status": "healthy",
                "summary": {"confirmed_issue_count": 0},
            }
        }
    )

    exit_code, captured = run_cli(["status"], client, capsys)

    assert exit_code == 0
    assert json.loads(captured.out)["status"] == "healthy"
    assert client.calls == [("/v1/data-health/summary", None)]


def test_status_full_requests_expensive_health_audit(capsys):
    client = FakeClient({"/v1/data-health": {"status": "warning"}})

    exit_code, _ = run_cli(["status", "--full"], client, capsys)

    assert exit_code == 0
    assert client.calls == [("/v1/data-health", None)]


def test_dataset_query_builds_only_explicit_parameters(capsys):
    client = FakeClient(
        {
            "/v1/datasets/stock_daily/records": {
                "data": [{"ts_code": "000001.SZ", "trade_date": "20260907"}],
                "meta": {"dataset": "stock_daily", "returned": 1},
                "page": {"limit": 20, "offset": 0, "has_more": False},
            }
        }
    )

    exit_code, captured = run_cli(
        [
            "query",
            "stock_daily",
            "--filter",
            "ts_code=000001.SZ",
            "--start-date",
            "2026-09-01",
            "--limit",
            "20",
            "--include-total",
        ],
        client,
        capsys,
    )

    assert exit_code == 0
    assert json.loads(captured.out)["meta"]["returned"] == 1
    assert client.calls == [
        (
            "/v1/datasets/stock_daily/records",
            {
                "ts_code": "000001.SZ",
                "start_date": "2026-09-01",
                "limit": 20,
                "offset": 0,
                "include_total": "true",
            },
        )
    ]


def test_interface_query_preserves_date_field_and_normalizes_name(capsys):
    client = FakeClient(
        {
            "/v1/interfaces/adj_factor/records": {
                "data": [],
                "meta": {"interface": "adj_factor"},
                "page": {"limit": 100, "offset": 0, "has_more": False},
            }
        }
    )

    exit_code, _captured = run_cli(
        [
            "interfaces",
            "query",
            "adj_factor",
            "--date-field",
            "trade_date",
            "--date",
            "20260907",
        ],
        client,
        capsys,
    )

    assert exit_code == 0
    assert client.calls == [
        (
            "/v1/interfaces/adj_factor/records",
            {
                "date": "20260907",
                "limit": 100,
                "offset": 0,
                "date_field": "trade_date",
            },
        )
    ]


def test_stock_research_pack_cli_forwards_bounded_scope(capsys):
    path = "/v1/stocks/300750.SZ/research-pack"
    client = FakeClient({path: {"data": {}, "meta": {"ts_code": "300750.SZ"}}})

    exit_code, captured = run_cli(
        [
            "stock",
            "research-pack",
            "300750.sz",
            "--lookback-days",
            "90",
            "--benchmark",
            "399006.sz",
            "--financial-periods",
            "4",
            "--as-of",
            "2026-09-08",
        ],
        client,
        capsys,
    )

    assert exit_code == 0
    assert json.loads(captured.out)["meta"]["ts_code"] == "300750.SZ"
    assert client.calls == [
        (
            path,
            {
                "lookback_days": 90,
                "benchmark": "399006.SZ",
                "financial_periods": 4,
                "as_of": "2026-09-08",
            },
        )
    ]


def test_sector_research_cli_commands_forward_normalized_scope(capsys):
    list_path = "/v1/sectors"
    pack_path = "/v1/sectors/ths/885001.TI/research-pack"
    client = FakeClient(
        {
            list_path: {"data": [], "meta": {}},
            pack_path: {"data": {}, "meta": {"provider": "ths"}},
        }
    )

    exit_code, _ = run_cli(
        ["sector", "list", "--provider", "ths", "--query", "人工", "--limit", "20"],
        client,
        capsys,
    )
    assert exit_code == 0
    exit_code, _ = run_cli(
        [
            "sector", "research-pack", "ths", "885001.ti",
            "--lookback-days", "90", "--member-limit", "200",
            "--as-of", "2026-09-08",
        ],
        client,
        capsys,
    )
    assert exit_code == 0
    assert client.calls == [
        (
            list_path,
            {"provider": "ths", "query": "人工", "limit": 20},
        ),
        (
            pack_path,
            {
                "lookback_days": 90,
                "member_limit": 200,
                "as_of": "2026-09-08",
            },
        ),
    ]


def test_stock_sector_and_peer_cli_commands(capsys):
    sectors_path = "/v1/stocks/300750.SZ/sectors"
    peers_path = "/v1/stocks/300750.SZ/peers"
    client = FakeClient(
        {
            sectors_path: {"data": [], "meta": {}},
            peers_path: {"data": [], "meta": {}},
        }
    )

    assert run_cli(
        ["stock", "sectors", "300750.sz", "--provider", "ths"],
        client, capsys,
    )[0] == 0
    assert run_cli(
        [
            "stock", "peers", "300750.sz", "--provider", "ths",
            "--max-sectors", "3", "--limit", "20",
        ],
        client, capsys,
    )[0] == 0
    assert client.calls == [
        (sectors_path, {"provider": "ths"}),
        (
            peers_path,
            {"max_sectors": 3, "limit": 20, "provider": "ths"},
        ),
    ]


def test_list_commands_support_deterministic_client_side_filters(capsys):
    client = FakeClient(
        {
            "/v1/datasets": [
                {"name": "stock_daily", "category": "market"},
                {"name": "income", "category": "finance"},
            ]
        }
    )

    exit_code, captured = run_cli(
        ["datasets", "list", "--category", "market"],
        client,
        capsys,
    )

    assert exit_code == 0
    assert json.loads(captured.out) == [
        {"category": "market", "name": "stock_daily"}
    ]


def test_csv_output_extracts_query_rows_and_encodes_nested_values(capsys):
    client = FakeClient(
        {
            "/v1/datasets/stock_daily/records": {
                "data": [
                    {
                        "ts_code": "000001.SZ",
                        "trade_date": "20260907",
                        "source": {"vendor": "Tushare"},
                    }
                ],
                "meta": {"returned": 1},
                "page": {},
            }
        }
    )

    exit_code, captured = run_cli(
        ["--output", "csv", "query", "stock_daily"],
        client,
        capsys,
    )

    assert exit_code == 0
    rows = list(csv.DictReader(io.StringIO(captured.out)))
    assert rows == [
        {
            "source": '{"vendor":"Tushare"}',
            "trade_date": "20260907",
            "ts_code": "000001.SZ",
        }
    ]


def test_invalid_and_duplicate_filters_fail_without_network_access(capsys):
    client = FakeClient()

    exit_code, captured = run_cli(
        ["query", "stock_daily", "--filter", "broken"],
        client,
        capsys,
    )

    assert exit_code == 2
    assert json.loads(captured.err)["error"]["code"] == "invalid_filter"
    assert client.calls == []

    exit_code, captured = run_cli(
        [
            "query",
            "stock_daily",
            "--filter",
            "ts_code=000001.SZ",
            "--filter",
            "ts_code=600000.SH",
        ],
        client,
        capsys,
    )
    assert exit_code == 2
    assert json.loads(captured.err)["error"]["code"] == "duplicate_filter"
    assert client.calls == []


def test_parser_rejects_path_like_dataset_as_json(capsys):
    with pytest.raises(SystemExit) as raised:
        main(["datasets", "describe", "../../health"])

    captured = capsys.readouterr()
    assert raised.value.code == 2
    assert json.loads(captured.err)["error"]["code"] == "invalid_arguments"


def test_cli_propagates_machine_readable_api_error(capsys):
    client = FakeClient(
        {
            "/v1/datasets/missing": CliError(
                "dataset_not_found",
                "unknown dataset: missing",
                EXIT_API_CLIENT,
                status_code=404,
                request_id="request-1",
            )
        }
    )

    exit_code, captured = run_cli(
        ["datasets", "describe", "missing"],
        client,
        capsys,
    )

    assert exit_code == EXIT_API_CLIENT
    assert json.loads(captured.err) == {
        "error": {
            "code": "dataset_not_found",
            "message": "unknown dataset: missing",
            "request_id": "request-1",
            "status_code": 404,
        }
    }


def test_api_client_sends_request_context_and_decodes_success():
    opener = FakeOpener(
        FakeResponse(
            200,
            {"status": "ok"},
            headers={"X-Request-ID": "server-request"},
        )
    )
    client = ApiClient("http://localhost:8000/api/", timeout_seconds=2, opener=opener)

    assert client.get("/health/live") == {"status": "ok"}
    request, options = opener.calls[0]
    assert request.full_url == "http://localhost:8000/api/health/live"
    assert options["timeout"] == 2
    assert request.get_header("Accept") == "application/json"
    assert request.get_header("X-request-id")


@pytest.mark.parametrize(
    ("error", "expected_exit", "expected_code"),
    [
        (socket.timeout("late"), EXIT_TIMEOUT, "request_timeout"),
        (
            URLError("offline"),
            EXIT_CONNECTION,
            "connection_error",
        ),
    ],
)
def test_api_client_classifies_transport_errors(error, expected_exit, expected_code):
    client = ApiClient(
        DEFAULT_API_URL,
        opener=FakeOpener(error=error),
    )

    with pytest.raises(CliError) as raised:
        client.get("/health/live")

    assert raised.value.exit_code == expected_exit
    assert raised.value.code == expected_code
    assert raised.value.request_id


def test_api_client_preserves_server_error_contract():
    client = ApiClient(
        DEFAULT_API_URL,
        opener=FakeOpener(
            FakeResponse(
                404,
                {
                    "error": {
                        "code": "dataset_not_found",
                        "message": "unknown dataset",
                        "request_id": "api-request",
                    }
                },
            )
        ),
    )

    with pytest.raises(CliError) as raised:
        client.get("/v1/datasets/missing")

    assert raised.value.code == "dataset_not_found"
    assert raised.value.exit_code == EXIT_API_CLIENT
    assert raised.value.status_code == 404
    assert raised.value.request_id == "api-request"


def test_api_client_rejects_non_json_and_credentialed_urls():
    client = ApiClient(
        DEFAULT_API_URL,
        opener=FakeOpener(FakeResponse(200, b"not json")),
    )
    with pytest.raises(CliError) as raised:
        client.get("/health/live")
    assert raised.value.exit_code == EXIT_INVALID_RESPONSE

    with pytest.raises(ValueError, match="embedded credentials"):
        ApiClient("http://user:password@localhost:8000/api")
