"""Command definitions for the read-only clawq client."""

from __future__ import annotations

import argparse
import os
import re
import sys
from collections.abc import Callable, Sequence
from typing import Any

from service.cli.client import ApiClient, CliError, EXIT_INVALID_RESPONSE
from service.cli.output import render, render_error
from service.version import APP_VERSION


DEFAULT_API_URL = "http://127.0.0.1:8000/api"
DEFAULT_TIMEOUT_SECONDS = 15.0
EXIT_USAGE = 2
_DATASET_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,127}$")
_TS_CODE_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,31}$")


class JsonArgumentParser(argparse.ArgumentParser):
    """Emit parse failures as JSON so agents can branch on them reliably."""

    def error(self, message: str) -> None:
        error = CliError("invalid_arguments", message, EXIT_USAGE)
        self._print_message(f"{render_error(error)}\n", sys.stderr)
        raise SystemExit(EXIT_USAGE)


def build_parser() -> argparse.ArgumentParser:
    parser = JsonArgumentParser(
        prog="clawq",
        description="Read-only CLI for claw-quant-data",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {APP_VERSION}")
    parser.add_argument(
        "--api-url",
        default=os.getenv("CLAW_QUANT_API_URL", DEFAULT_API_URL),
        help="API root (default: %(default)s)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=_environment_float(
            "CLAW_QUANT_TIMEOUT_SECONDS",
            DEFAULT_TIMEOUT_SECONDS,
        ),
        help="HTTP timeout in seconds (default: %(default)s)",
    )
    parser.add_argument(
        "--output",
        choices=("json", "jsonl", "csv"),
        default="json",
        help="output encoding (default: %(default)s)",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="indent JSON output for interactive reading",
    )

    commands = parser.add_subparsers(dest="command", required=True)

    health = commands.add_parser("health", help="check API and database health")
    health.add_argument(
        "--live-only",
        action="store_true",
        help="skip the PostgreSQL readiness probe",
    )
    health.set_defaults(handler=_health)

    status = commands.add_parser(
        "status",
        help="show consolidated data health and collection status",
    )
    status.set_defaults(handler=_status)

    datasets = commands.add_parser("datasets", help="discover data service datasets")
    dataset_commands = datasets.add_subparsers(dest="datasets_command", required=True)
    dataset_list = dataset_commands.add_parser("list", help="list datasets")
    dataset_list.add_argument("--category", help="filter the returned category")
    dataset_list.set_defaults(handler=_datasets_list)
    dataset_describe = dataset_commands.add_parser("describe", help="describe a dataset")
    dataset_describe.add_argument("dataset", type=_dataset_name)
    dataset_describe.set_defaults(handler=_datasets_describe)

    query = commands.add_parser("query", help="query records from a dataset")
    query.add_argument("dataset", type=_dataset_name)
    _add_record_query_arguments(query)
    query.set_defaults(handler=_query_dataset)

    freshness = commands.add_parser("freshness", help="show dataset freshness")
    freshness.add_argument("dataset", nargs="?", type=_dataset_name)
    freshness.set_defaults(handler=_freshness)

    stock = commands.add_parser("stock", help="query high-level stock views")
    stock_commands = stock.add_subparsers(dest="stock_command", required=True)
    stock_snapshot = stock_commands.add_parser("snapshot", help="get a stock snapshot")
    stock_snapshot.add_argument("ts_code", type=_ts_code)
    stock_snapshot.set_defaults(handler=_stock_snapshot)
    stock_research = stock_commands.add_parser(
        "research-pack",
        help="get a governed multi-dataset stock research pack",
    )
    stock_research.add_argument("ts_code", type=_ts_code)
    stock_research.add_argument(
        "--lookback-days", type=_bounded_integer(30, 730), default=180
    )
    stock_research.add_argument(
        "--benchmark", type=_ts_code, default="399006.SZ"
    )
    stock_research.add_argument(
        "--financial-periods", type=_bounded_integer(1, 12), default=8
    )
    stock_research.add_argument("--as-of")
    stock_research.set_defaults(handler=_stock_research_pack)

    interfaces = commands.add_parser("interfaces", help="discover Tushare interfaces")
    interface_commands = interfaces.add_subparsers(
        dest="interfaces_command",
        required=True,
    )
    interface_list = interface_commands.add_parser("list", help="list interfaces")
    interface_list.add_argument("--permission", help="filter permission_status")
    interface_list.add_argument("--mode", help="filter implementation_mode")
    interface_list.set_defaults(handler=_interfaces_list)
    interface_describe = interface_commands.add_parser(
        "describe",
        help="describe an interface contract",
    )
    interface_describe.add_argument("api_name", type=_dataset_name)
    interface_describe.set_defaults(handler=_interfaces_describe)
    interface_query = interface_commands.add_parser(
        "query",
        help="query normalized interface records",
    )
    interface_query.add_argument("api_name", type=_dataset_name)
    interface_query.add_argument("--date-field", type=_dataset_name)
    _add_record_query_arguments(interface_query)
    interface_query.set_defaults(handler=_interfaces_query)

    coverage = commands.add_parser("coverage", help="inspect data coverage evidence")
    coverage_commands = coverage.add_subparsers(dest="coverage_command", required=True)
    coverage_summary = coverage_commands.add_parser("summary", help="show coverage overview")
    coverage_summary.set_defaults(handler=_coverage_summary)
    coverage_show = coverage_commands.add_parser(
        "show",
        help="show dataset partition coverage",
    )
    coverage_show.add_argument("dataset", type=_dataset_name)
    coverage_show.add_argument("--start-date")
    coverage_show.add_argument("--end-date")
    coverage_show.add_argument(
        "--status",
        choices=("present", "partial", "missing", "pending", "observed_only"),
    )
    coverage_show.add_argument("--limit", type=_bounded_integer(1, 1000), default=200)
    coverage_show.set_defaults(handler=_coverage_show)

    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    client_factory: Callable[..., ApiClient] = ApiClient,
) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        client = client_factory(args.api_url, timeout_seconds=args.timeout)
        payload = args.handler(client, args)
        encoded = render(
            payload,
            output_format=args.output,
            pretty=args.pretty,
        )
        if encoded:
            print(encoded)
        return 0
    except CliError as exc:
        print(render_error(exc), file=sys.stderr)
        return exc.exit_code
    except ValueError as exc:
        error = CliError("invalid_configuration", str(exc), EXIT_USAGE)
        print(render_error(error), file=sys.stderr)
        return error.exit_code
    except BrokenPipeError:
        return 0
    except KeyboardInterrupt:
        error = CliError("interrupted", "request interrupted", 130)
        print(render_error(error), file=sys.stderr)
        return error.exit_code


def _add_record_query_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--filter",
        action="append",
        default=[],
        metavar="NAME=VALUE",
        help="repeatable exact-match filter",
    )
    parser.add_argument("--date")
    parser.add_argument("--start-date")
    parser.add_argument("--end-date")
    parser.add_argument("--limit", type=_bounded_integer(1, 1000), default=100)
    parser.add_argument("--offset", type=_bounded_integer(0, None), default=0)
    parser.add_argument("--include-total", action="store_true")


def _record_query_params(args: argparse.Namespace) -> dict[str, Any]:
    params = _parse_filters(args.filter)
    reserved = {
        "date",
        "start_date",
        "end_date",
        "limit",
        "offset",
        "include_total",
        "date_field",
    }
    invalid = sorted(set(params) & reserved)
    if invalid:
        raise CliError(
            "reserved_filter",
            f"use dedicated options for: {', '.join(invalid)}",
            EXIT_USAGE,
        )
    optional = {
        "date": args.date,
        "start_date": args.start_date,
        "end_date": args.end_date,
    }
    params.update({key: value for key, value in optional.items() if value is not None})
    params.update(
        {
            "limit": args.limit,
            "offset": args.offset,
        }
    )
    if args.include_total:
        params["include_total"] = "true"
    return params


def _parse_filters(values: list[str]) -> dict[str, str]:
    filters: dict[str, str] = {}
    for item in values:
        name, separator, value = item.partition("=")
        name = name.strip()
        if not separator or not name or not value:
            raise CliError(
                "invalid_filter",
                f"filter must use NAME=VALUE: {item!r}",
                EXIT_USAGE,
            )
        if not _DATASET_PATTERN.fullmatch(name):
            raise CliError(
                "invalid_filter",
                f"filter name contains unsupported characters: {name!r}",
                EXIT_USAGE,
            )
        if name in filters:
            raise CliError(
                "duplicate_filter",
                f"filter specified more than once: {name}",
                EXIT_USAGE,
            )
        filters[name] = value
    return filters


def _health(client: ApiClient, args: argparse.Namespace) -> dict[str, Any]:
    result = {"live": client.get("/health/live")}
    if not args.live_only:
        result["ready"] = client.get("/health/ready")
    return result


def _status(client: ApiClient, _args: argparse.Namespace) -> Any:
    return client.get("/v1/data-health")


def _datasets_list(client: ApiClient, args: argparse.Namespace) -> list[dict[str, Any]]:
    rows = _require_object_list(client.get("/v1/datasets"), "datasets")
    if args.category:
        rows = [row for row in rows if row.get("category") == args.category]
    return rows


def _datasets_describe(client: ApiClient, args: argparse.Namespace) -> Any:
    return client.get(f"/v1/datasets/{args.dataset}")


def _query_dataset(client: ApiClient, args: argparse.Namespace) -> Any:
    return client.get(
        f"/v1/datasets/{args.dataset}/records",
        params=_record_query_params(args),
    )


def _freshness(client: ApiClient, args: argparse.Namespace) -> Any:
    params = {"dataset": args.dataset} if args.dataset else None
    return client.get("/v1/freshness", params=params)


def _stock_snapshot(client: ApiClient, args: argparse.Namespace) -> Any:
    return client.get(f"/v1/stocks/{args.ts_code.upper()}/snapshot")


def _stock_research_pack(client: ApiClient, args: argparse.Namespace) -> Any:
    params = {
        "lookback_days": args.lookback_days,
        "benchmark": args.benchmark.upper(),
        "financial_periods": args.financial_periods,
    }
    if args.as_of:
        params["as_of"] = args.as_of
    return client.get(
        f"/v1/stocks/{args.ts_code.upper()}/research-pack",
        params=params,
    )


def _interfaces_list(client: ApiClient, args: argparse.Namespace) -> list[dict[str, Any]]:
    rows = _require_object_list(client.get("/v1/interfaces"), "interfaces")
    if args.permission:
        rows = [row for row in rows if row.get("permission_status") == args.permission]
    if args.mode:
        rows = [row for row in rows if row.get("implementation_mode") == args.mode]
    return rows


def _interfaces_describe(client: ApiClient, args: argparse.Namespace) -> Any:
    return client.get(f"/v1/interfaces/{args.api_name}")


def _interfaces_query(client: ApiClient, args: argparse.Namespace) -> Any:
    params = _record_query_params(args)
    if args.date_field:
        params["date_field"] = args.date_field
    return client.get(
        f"/v1/interfaces/{args.api_name}/records",
        params=params,
    )


def _coverage_summary(client: ApiClient, _args: argparse.Namespace) -> Any:
    return client.get("/v1/coverage")


def _coverage_show(client: ApiClient, args: argparse.Namespace) -> Any:
    params = {
        key: value
        for key, value in {
            "start_date": args.start_date,
            "end_date": args.end_date,
            "status": args.status,
            "limit": args.limit,
        }.items()
        if value is not None
    }
    return client.get(
        f"/v1/coverage/datasets/{args.dataset}/partitions",
        params=params,
    )


def _require_object_list(payload: Any, label: str) -> list[dict[str, Any]]:
    if not isinstance(payload, list) or not all(
        isinstance(item, dict) for item in payload
    ):
        raise CliError(
            "invalid_response",
            f"{label} endpoint did not return a list of objects",
            EXIT_INVALID_RESPONSE,
        )
    return payload


def _bounded_integer(minimum: int, maximum: int | None) -> Callable[[str], int]:
    def parse(value: str) -> int:
        try:
            parsed = int(value)
        except ValueError as exc:
            raise argparse.ArgumentTypeError("must be an integer") from exc
        if parsed < minimum or (maximum is not None and parsed > maximum):
            if maximum is None:
                message = f"must be at least {minimum}"
            else:
                message = f"must be between {minimum} and {maximum}"
            raise argparse.ArgumentTypeError(message)
        return parsed

    return parse


def _environment_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        # Defer the error until main() so it follows the normal JSON contract.
        return -1


def _dataset_name(value: str) -> str:
    if not _DATASET_PATTERN.fullmatch(value):
        raise argparse.ArgumentTypeError(
            "must start with a letter and contain only letters, digits, or underscores"
        )
    return value


def _ts_code(value: str) -> str:
    if not _TS_CODE_PATTERN.fullmatch(value):
        raise argparse.ArgumentTypeError("contains unsupported characters")
    return value.upper()


if __name__ == "__main__":
    raise SystemExit(main())
