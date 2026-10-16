"""Code-owned V2 derived-data handlers.

Transformations consume governed database datasets; they never call an
upstream provider.  The registry is deliberately explicit so task metadata
cannot load arbitrary code from the database.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import Decimal
from typing import Any

import psycopg2.extras

from service.db import get_conn
from service.research.service import _adjust_ohlcv
from service.research.technical_indicators import niumen_breakout_lines
from service.research.volume_price import transaction_cost_lines


FORMULA_VERSION = "niumen-tongdaxin-v1+transaction-cost-v1"
SUPPORTED_TRANSFORMATION_TASK_KEYS = frozenset({"technical_factor_snapshot"})


def _number(value: Any) -> float | None:
    if value is None or value == "":
        return None
    return float(value)


def build_technical_factor_snapshot_row(
    ts_code: str,
    snapshot_date: date,
    source_rows: list[dict[str, Any]],
    *,
    source_execution_id: int | None = None,
) -> dict[str, Any]:
    """Build one explicit, auditable stock snapshot from at most 60 raw bars."""

    ordered = sorted(source_rows, key=lambda item: item.get("trade_date") or date.min)
    raw_bars = [dict(item) for item in ordered if item.get("trade_date")]
    adjustments = [
        {"trade_date": item["trade_date"], "adj_factor": item.get("adj_factor")}
        for item in raw_bars
        if item.get("adj_factor") is not None
    ]
    adjusted, adjustment = _adjust_ohlcv(
        raw_bars, adjustments, dataset="adj_factor"
    )
    # _adjust_ohlcv intentionally returns continuous raw bars when factors are
    # partial so charts do not acquire artificial multi-year holes.  A derived
    # adjusted-factor snapshot, however, must fail closed rather than compute
    # adjusted indicators from those raw bars.
    usable = [
        item for item in adjusted
        if adjustment["status"] == "applied"
        and all(
            _number(item.get(field)) is not None
            for field in ("high", "low", "close")
        )
    ]
    highs = [float(item["high"]) for item in usable]
    lows = [float(item["low"]) for item in usable]
    closes = [float(item["close"]) for item in usable]
    niumen = niumen_breakout_lines(highs, lows, closes)
    costs = transaction_cost_lines(
        usable,
        closes[-1] if closes else 0.0,
        amount_to_price_factor=10.0,
        windows=(20, 60),
    )
    cost20 = costs["windows"]["20_day"]
    cost60 = costs["windows"]["60_day"]
    reasons: list[dict[str, Any]] = []
    if not raw_bars:
        reasons.append({"indicator": "all", "reason": "no_daily_bars"})
    if adjustment["status"] in {"missing", "stale", "partial_history"}:
        reasons.append({
            "indicator": "price_adjustment",
            "reason": f"adjustment_{adjustment['status']}",
            "source_bars": len(raw_bars),
            "matched_factors": int(adjustment["matched"]),
        })
    if niumen["status"] != "ready":
        reasons.append({
            "indicator": "niumen_confirmation",
            "reason": niumen["status"],
            "required_bars": 21,
            "available_adjusted_bars": len(usable),
        })
    normalized_costs: dict[int, dict[str, Any]] = {}
    for window, original in ((20, cost20), (60, cost60)):
        result = dict(original)
        if (
            result["status"] == "insufficient_history"
            and len(raw_bars) >= window
            and len(usable) < window
        ):
            result["status"] = "missing_input"
        normalized_costs[window] = result
        if result["status"] != "ready":
            reasons.append({
                "indicator": f"cost_{window}",
                "reason": result["status"],
                "required_bars": window,
                "available_adjusted_bars": len(usable),
                "usable_observations": result["usable_observations"],
            })

    cost20 = normalized_costs[20]
    cost60 = normalized_costs[60]

    statuses = (niumen["status"], cost20["status"], cost60["status"])
    if all(item == "ready" for item in statuses):
        calculation_status = "ready"
    elif any(item == "ready" for item in statuses):
        calculation_status = "partial"
    elif raw_bars and all(item == "insufficient_history" for item in statuses):
        calculation_status = "insufficient_history"
    else:
        calculation_status = "missing_input"

    values = niumen["values"]
    events = niumen["events"]
    return {
        "snapshot_date": snapshot_date,
        "ts_code": ts_code,
        "source_trade_date": raw_bars[-1]["trade_date"] if raw_bars else None,
        "source_bar_count": len(raw_bars),
        "adjustment_status": adjustment["status"],
        "adjustment_matched_count": int(adjustment["matched"]),
        "price_basis": str(adjustment["price_basis"]),
        "close": closes[-1] if closes else None,
        "prior_high_20": values["prior_high_20"],
        "atrv_sma_14": values["atrv_sma_14"],
        "niumen_line": values["niumen_line"],
        "confirmation_line": values["confirmation_line"],
        "signal_ma_10": values["signal_ma_10"],
        "niumen_state": niumen["state"],
        "crossed_niumen": events["crossed_niumen_today"],
        "crossed_confirmation": events["crossed_confirmation_today"],
        "cost_20": cost20["value"],
        "cost_20_status": cost20["status"],
        "cost_60": cost60["value"],
        "cost_60_status": cost60["status"],
        "calculation_status": calculation_status,
        "unavailable_reasons": reasons,
        "formula_version": FORMULA_VERSION,
        "source_execution_id": source_execution_id,
    }


def materialize_technical_factor_snapshot(
    snapshot_date: date,
    *,
    source_execution_id: int | None = None,
) -> dict[str, Any]:
    """Atomically materialize all stocks listed on ``snapshot_date``."""

    compact_date = snapshot_date.strftime("%Y%m%d")
    connection = get_conn()
    try:
        with connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
            cursor.execute(
                """
                SELECT stock.ts_code, bars.trade_date, bars.open, bars.high,
                       bars.low, bars.close, bars.pre_close, bars.vol,
                       bars.amount, bars.adj_factor
                FROM stock_basic AS stock
                LEFT JOIN LATERAL (
                    SELECT daily.trade_date, daily.open, daily.high, daily.low,
                           daily.close, daily.pre_close, daily.vol, daily.amount,
                           factor.adj_factor
                    FROM daily
                    LEFT JOIN LATERAL (
                        SELECT source.adj_factor
                        FROM tushare_norm_adj_factor AS source
                        WHERE source.ts_code=daily.ts_code
                          AND source.trade_date=daily.trade_date
                          AND source.adj_factor IS NOT NULL
                        ORDER BY source._last_seen_at DESC,
                                 source._record_hash DESC
                        LIMIT 1
                    ) AS factor ON TRUE
                    WHERE daily.ts_code=stock.ts_code
                      AND daily.trade_date <= %s
                    ORDER BY daily.trade_date DESC
                    LIMIT 60
                ) AS bars ON TRUE
                WHERE NULLIF(stock.list_date, '') IS NOT NULL
                  AND stock.list_date <= %s
                  AND (
                      NULLIF(stock.delist_date, '') IS NULL
                      OR stock.delist_date > %s
                  )
                ORDER BY stock.ts_code, bars.trade_date
                """,
                (snapshot_date, compact_date, compact_date),
            )
            grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
            for item in cursor.fetchall():
                row = dict(item)
                ts_code = str(row.pop("ts_code"))
                if row.get("trade_date") is not None:
                    grouped[ts_code].append(row)
                else:
                    grouped.setdefault(ts_code, [])
            rows = [
                build_technical_factor_snapshot_row(
                    ts_code,
                    snapshot_date,
                    source_rows,
                    source_execution_id=source_execution_id,
                )
                for ts_code, source_rows in grouped.items()
            ]
            columns = tuple(rows[0]) if rows else ()
            if rows:
                values = [
                    tuple(
                        psycopg2.extras.Json(value) if column == "unavailable_reasons" else value
                        for column, value in ((column, row[column]) for column in columns)
                    )
                    for row in rows
                ]
                updates = ", ".join(
                    f"{column}=EXCLUDED.{column}"
                    for column in columns
                    if column not in {"snapshot_date", "ts_code"}
                )
                psycopg2.extras.execute_values(
                    cursor,
                    f"INSERT INTO technical_factor_snapshot ({', '.join(columns)}) VALUES %s "
                    f"ON CONFLICT (snapshot_date, ts_code) DO UPDATE SET {updates}, computed_at=NOW()",
                    values,
                    page_size=1000,
                )
            cursor.execute(
                """
                DELETE FROM technical_factor_snapshot AS snapshot
                WHERE snapshot.snapshot_date=%s
                  AND NOT EXISTS (
                      SELECT 1 FROM stock_basic AS stock
                      WHERE stock.ts_code=snapshot.ts_code
                        AND NULLIF(stock.list_date, '') IS NOT NULL
                        AND stock.list_date <= %s
                        AND (NULLIF(stock.delist_date, '') IS NULL OR stock.delist_date > %s)
                  )
                """,
                (snapshot_date, compact_date, compact_date),
            )
            cursor.execute(
                """
                SELECT count(*) AS total,
                       count(*) FILTER (WHERE calculation_status='ready') AS ready,
                       count(*) FILTER (WHERE calculation_status='partial') AS partial,
                       count(*) FILTER (WHERE calculation_status='insufficient_history') AS insufficient_history,
                       count(*) FILTER (WHERE calculation_status='missing_input') AS missing_input,
                       count(*) FILTER (WHERE adjustment_status IN ('missing','stale','partial_history')) AS adjustment_incomplete,
                       count(*) FILTER (WHERE niumen_line IS NOT NULL AND confirmation_line IS NOT NULL) AS niumen_ready,
                       count(*) FILTER (WHERE cost_20_status='ready') AS cost_20_ready,
                       count(*) FILTER (WHERE cost_60_status='ready') AS cost_60_ready
                FROM technical_factor_snapshot WHERE snapshot_date=%s
                """,
                (snapshot_date,),
            )
            summary = dict(cursor.fetchone())
            if int(summary["total"]) != len(grouped):
                raise RuntimeError(
                    "technical snapshot row count does not equal listed-stock universe"
                )
        connection.commit()
        return {
            "dataset": "technical_factor_snapshot",
            "snapshot_date": snapshot_date.isoformat(),
            "formula_version": FORMULA_VERSION,
            "rows_written": len(rows),
            **{key: int(value) for key, value in summary.items()},
        }
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def run_transformation(
    task_key: str,
    observation_date: date,
    *,
    source_execution_id: int | None = None,
) -> dict[str, Any]:
    handlers = {
        "technical_factor_snapshot": materialize_technical_factor_snapshot,
    }
    try:
        handler = handlers[task_key]
    except KeyError as exc:
        raise LookupError(f"no code-owned transformation handler: {task_key}") from exc
    return handler(observation_date, source_execution_id=source_execution_id)
