"""Scheduled-pull collection for allow-listed 蚂蚁数据源 routes.

Product decision (2026-10): the query-time quota fallback is disabled, but a
reviewed set of routes with no Tushare equivalent is worth *periodic
collection* so research gets time series instead of point-in-time reads.
This module owns the whole scheduled path: symbol enumeration for
symbol-keyed routes, protocol decoding, typed normalization and idempotent
UPSERT into ``ant_norm_*`` tables.  It never touches the canonical read path.
"""

from __future__ import annotations

from datetime import date, datetime, timezone, timedelta
import hashlib
import json
from typing import Any, Callable, Mapping

import psycopg2
import psycopg2.extras

from service.config import DB_CONFIG
from service.source_connectors.financial_data_protocol import tabular_rows
from service.source_connectors.raw_archive import sha256_json

CST = timezone(timedelta(hours=8))

# Per-request symbol batch.  The common-query protocol accepts up to 100
# requests per payload; 50 symbols per request keeps one full-market sweep
# (~5800 A-share names) inside ~116 requests on a single payload.
SYMBOLS_PER_REQUEST = 50
MAX_REQUESTS_PER_PAYLOAD = 100


class ScheduledRouteSpec:
    __slots__ = ("endpoint_key", "route", "table", "title", "cadence", "symbol_keyed")

    def __init__(
        self,
        *,
        endpoint_key: str,
        route: str,
        table: str,
        title: str,
        cadence: str,
        symbol_keyed: bool,
    ):
        self.endpoint_key = endpoint_key
        self.route = route
        self.table = table
        self.title = title
        self.cadence = cadence
        self.symbol_keyed = symbol_keyed


SCHEDULED_ROUTES: dict[str, ScheduledRouteSpec] = {
    spec.endpoint_key: spec
    for spec in (
        ScheduledRouteSpec(
            endpoint_key="altdata.hot-stock-rank",
            route="/api/v1/altdata/hot-stock-rank",
            table="ant_norm_hot_stock_rank",
            title="支付宝热门股票榜",
            cadence="daily",
            symbol_keyed=False,
        ),
        ScheduledRouteSpec(
            endpoint_key="altdata.hot-plate-rank",
            route="/api/v1/altdata/hot-plate-rank",
            table="ant_norm_hot_plate_rank",
            title="支付宝热门板块榜",
            cadence="daily",
            symbol_keyed=False,
        ),
        ScheduledRouteSpec(
            endpoint_key="stock_fnd.equity-structure",
            route="/api/v1/stock_fnd/equity-structure",
            table="ant_norm_equity_structure",
            title="股本结构（全市场快照）",
            cadence="weekly",
            symbol_keyed=True,
        ),
        ScheduledRouteSpec(
            endpoint_key="stock_fnd.free-float",
            route="/api/v1/stock_fnd/free-float",
            table="ant_norm_free_float",
            title="自由流通股本（全市场事件史）",
            cadence="weekly",
            symbol_keyed=True,
        ),
        ScheduledRouteSpec(
            endpoint_key="stock_fnd.actual-controller",
            route="/api/v1/stock_fnd/actual-controller",
            table="ant_norm_actual_controller",
            title="实际控制人",
            cadence="monthly",
            symbol_keyed=True,
        ),
        ScheduledRouteSpec(
            endpoint_key="stock_fnd.controlling-shareholder",
            route="/api/v1/stock_fnd/controlling-shareholder",
            table="ant_norm_controlling_shareholder",
            title="控股股东",
            cadence="monthly",
            symbol_keyed=True,
        ),
        ScheduledRouteSpec(
            endpoint_key="stock_fnd.style-classification",
            route="/api/v1/stock_fnd/style-classification",
            table="ant_norm_style_classification",
            title="股票风格规模分类",
            cadence="monthly",
            symbol_keyed=True,
        ),
    )
}

# Route → default request parameters for market-wide (non symbol-keyed) pulls.
_ROUTE_BASE_PARAMS: dict[str, dict[str, Any]] = {
    "/api/v1/altdata/hot-stock-rank": {"count": 200},
    "/api/v1/altdata/hot-plate-rank": {"count": 200},
}


def _as_date(value: Any) -> date | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    try:
        return date.fromisoformat(text[:10])
    except ValueError as exc:
        raise ValueError(f"unsupported date value: {value!r}") from exc


def _number(value: Any) -> float | None:
    if value in (None, "", "-"):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _integer(value: Any) -> int | None:
    number = _number(value)
    return int(number) if number is not None else None


def active_a_share_symbols() -> list[str]:
    """Listed A-share symbols from the local security master (stock_basic)."""
    connection = psycopg2.connect(**DB_CONFIG)
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT ts_code FROM stock_basic "
                "WHERE list_status = 'L' ORDER BY ts_code"
            )
            return [row[0] for row in cursor.fetchall()]
    finally:
        connection.close()


def _chunked(items: list[str], size: int) -> list[list[str]]:
    return [items[i:i + size] for i in range(0, len(items), size)]


def _row_from_record(
    spec: ScheduledRouteSpec,
    record: Mapping[str, Any],
    trade_date: date,
) -> dict[str, Any]:
    row: dict[str, Any] = {"payload": {k: v for k, v in record.items()}}
    if spec.table == "ant_norm_hot_stock_rank":
        row.update({
            "trade_date": trade_date,
            "rank": _integer(record.get("rank")),
            "symbol": record.get("symbol"),
            "sec_name": record.get("sec_name"),
            "score": _number(record.get("score")),
            "rank_raise": _integer(record.get("rank_raise")),
            "begin_date": _as_date(record.get("begin_date")),
        })
    elif spec.table == "ant_norm_hot_plate_rank":
        row.update({
            "trade_date": trade_date,
            "rank": _integer(record.get("rank")),
            "symbol": record.get("symbol"),
            "plate_name": record.get("plate_name"),
            "pct_chg": _number(record.get("pct_chg")),
            "pct_chg_abs": _number(record.get("pct_chg_abs")),
            "pct_chg_1m": _number(record.get("pct_chg_1m")),
            "pct_chg_3m": _number(record.get("pct_chg_3m")),
            "main_net_inflow": _number(record.get("main_net_inflow")),
            "main_net_inflow_1w": _number(record.get("main_net_inflow_1w")),
        })
    elif spec.table == "ant_norm_equity_structure":
        row.update({
            "symbol": record.get("symbol"),
            "end_date": _as_date(record.get("end_date")),
        })
    elif spec.table == "ant_norm_free_float":
        row.update({
            "symbol": record.get("symbol"),
            "adjustment_date": _as_date(record.get("adjustment_date")),
            "free_float_shares": _number(record.get("free_float_shares")),
            "free_float_share_ratio": _number(record.get("free_float_share_ratio")),
            "non_free_float_shares": _number(record.get("non_free_float_shares")),
            "free_float_share_change_type": record.get(
                "free_float_share_change_type"
            ),
            "is_share_change_corporate_action": record.get(
                "is_share_change_corporate_action"
            ),
        })
    elif spec.table == "ant_norm_actual_controller":
        row.update({
            "symbol": record.get("symbol"),
            "end_date": _as_date(record.get("end_date")),
            "actual_controller_name": record.get("actual_controller_name"),
            "actual_controller_type": record.get("actual_controller_type"),
            "actual_controller_total_hold_ratio": _number(
                record.get("actual_controller_total_hold_ratio")
            ),
        })
    elif spec.table == "ant_norm_controlling_shareholder":
        row.update({
            "symbol": record.get("symbol"),
            "end_date": _as_date(record.get("end_date")),
            "controlling_shareholder_name": record.get(
                "controlling_shareholder_name"
            ),
            "controlling_shareholder_type": record.get(
                "controlling_shareholder_type"
            ),
            "controlling_shareholder_total_hold_ratio": _number(
                record.get("controlling_shareholder_total_hold_ratio")
            ),
        })
    elif spec.table == "ant_norm_style_classification":
        row.update({
            "symbol": record.get("symbol"),
            "end_date": _as_date(record.get("end_date")),
            "stock_size_classification": record.get("stock_size_classification"),
            "stock_style_classification": record.get(
                "stock_style_classification"
            ),
            "stock_size_value": _number(record.get("stock_size_value")),
            "stock_style_value": _number(record.get("stock_style_value")),
        })
    else:  # pragma: no cover - guarded by SCHEDULED_ROUTES
        raise ValueError(f"unknown scheduled route table: {spec.table}")
    return row


# Typed columns per table; ``payload`` is written separately as JSONB.
_TYPED_COLUMNS: dict[str, tuple[str, ...]] = {
    "ant_norm_hot_stock_rank": (
        "trade_date", "rank", "symbol", "sec_name", "score", "rank_raise",
        "begin_date",
    ),
    "ant_norm_hot_plate_rank": (
        "trade_date", "rank", "symbol", "plate_name", "pct_chg",
        "pct_chg_abs", "pct_chg_1m", "pct_chg_3m", "main_net_inflow",
        "main_net_inflow_1w",
    ),
    "ant_norm_equity_structure": ("symbol", "end_date"),
    "ant_norm_free_float": (
        "symbol", "adjustment_date", "free_float_shares",
        "free_float_share_ratio", "non_free_float_shares",
        "free_float_share_change_type", "is_share_change_corporate_action",
    ),
    "ant_norm_actual_controller": (
        "symbol", "end_date", "actual_controller_name",
        "actual_controller_type", "actual_controller_total_hold_ratio",
    ),
    "ant_norm_controlling_shareholder": (
        "symbol", "end_date", "controlling_shareholder_name",
        "controlling_shareholder_type",
        "controlling_shareholder_total_hold_ratio",
    ),
    "ant_norm_style_classification": (
        "symbol", "end_date", "stock_size_classification",
        "stock_style_classification", "stock_size_value", "stock_style_value",
    ),
}


def _row_hash(table: str, row: Mapping[str, Any]) -> str:
    material = {"table": table, "row": {
        key: row.get(key) for key in _TYPED_COLUMNS[table]
    }, "payload": row.get("payload")}
    return hashlib.sha256(
        json.dumps(material, ensure_ascii=False, sort_keys=True, default=str)
        .encode("utf-8")
    ).hexdigest()


def store_rows(
    spec: ScheduledRouteSpec,
    rows: list[dict[str, Any]],
) -> int:
    """Idempotent UPSERT keyed by the content hash of each business row."""
    if not rows:
        return 0
    typed = _TYPED_COLUMNS[spec.table]
    columns = ("_record_hash", "_source_collected_at", *typed, "payload")
    collected_at = datetime.now(timezone.utc)
    values = []
    for row in rows:
        record_hash = _row_hash(spec.table, row)
        values.append((
            record_hash,
            collected_at,
            *(row.get(column) for column in typed),
            psycopg2.extras.Json(row.get("payload") or {}),
        ))
    update_assignments = ",\n".join(
        f'"{column}"=EXCLUDED."{column}"' for column in (*typed, "payload")
    )
    connection = psycopg2.connect(**DB_CONFIG)
    try:
        with connection.cursor() as cursor:
            psycopg2.extras.execute_values(
                cursor,
                f"""
                INSERT INTO {spec.table} ({", ".join(f'"{c}"' for c in columns)})
                VALUES %s
                ON CONFLICT (_record_hash) DO UPDATE SET
                    _last_seen_at=NOW(),
                    {update_assignments}
                """,
                values,
                page_size=500,
            )
        connection.commit()
    finally:
        connection.close()
    return len(values)


def run_scheduled_pull(
    spec: ScheduledRouteSpec,
    transport: Callable[[dict[str, Any]], Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Fetch every partition of one route and persist normalized rows."""
    trade_date = datetime.now(CST).date()
    if spec.symbol_keyed:
        symbols = active_a_share_symbols()
        if not symbols:
            raise RuntimeError(
                "local stock_basic is empty; cannot enumerate symbols for "
                f"{spec.route}"
            )
        chunks = _chunked(symbols, SYMBOLS_PER_REQUEST)
        if len(chunks) > MAX_REQUESTS_PER_PAYLOAD:
            raise RuntimeError(
                f"{spec.route} needs {len(chunks)} requests which exceeds the "
                f"{MAX_REQUESTS_PER_PAYLOAD}-request payload bound"
            )
        payload = {
            "mode": "data",
            "requests": [
                {"url": spec.route, "params": {"symbols": chunk}}
                for chunk in chunks
            ],
        }
        param_note = {"symbol_batches": len(chunks), "symbols": len(symbols)}
    else:
        payload = {
            "mode": "data",
            "requests": [{
                "url": spec.route,
                "params": dict(_ROUTE_BASE_PARAMS.get(spec.route, {})),
            }],
        }
        param_note = {"symbol_batches": 0}

    response = transport(payload)
    records: list[dict[str, Any]] = []
    if spec.symbol_keyed:
        # One result entry per request chunk; decode each independently.
        results = response.get("results") or []
        for item in results:
            if not isinstance(item, Mapping):
                continue
            records.extend(tabular_rows(
                {"status": response.get("status"), "results": [item]},
                route=spec.route,
            ))
    else:
        records.extend(tabular_rows(response, route=spec.route))

    rows = [_row_from_record(spec, record, trade_date) for record in records]
    stored = store_rows(spec, rows)
    evidence = {
        "verified": True,
        "verification_type": "financial_data_scheduled_pull",
        "route": spec.route,
        "table": spec.table,
        "trade_date": trade_date.isoformat(),
        "fetched_rows": len(records),
        "stored_rows": stored,
        **param_note,
    }
    return rows, evidence
