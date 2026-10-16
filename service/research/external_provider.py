"""Quota-aware external evidence for the public research contract.

The research layer owns provider selection.  Agents receive one stable response
shape and never call a vendor route directly.  Local normalized datasets remain
authoritative for deterministic calculations; 蚂蚁数据源 contributes
real-time observations and research evidence that the local store cannot fully
represent.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from service.clock import business_now
from service.source_connectors.contracts import AcquisitionMode, ConnectorRequest
from service.source_connectors.financial_data_protocol import tabular_rows


FUNDAMENTAL_ROUTES = {
    "consensus_statistics": "/api/v1/stock_fnd/consensus-stats",
    "rating_summary": "/api/v1/stock_fnd/rating-summary",
    "target_price": "/api/v1/stock_fnd/target-price",
}

TECHNICAL_ROUTES = {
    "provider_indicators": "/api/v1/stock/tech-indicators",
    "provider_patterns": "/api/v1/stock/tech-patterns",
}

REALTIME_ROUTES = {
    "quote_snapshot": "/api/v1/quote/basic-snapshot",
    "valuation_snapshot": "/api/v1/quote/derived-snapshot",
}


def _latest(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not rows:
        return None
    return max(
        rows,
        key=lambda row: str(
            row.get("end_date")
            or row.get("latest_trade_time")
            or row.get("snapshot_date")
            or row.get("date")
            or ""
        ),
    )


def _number(value: Any) -> float | None:
    try:
        return None if value is None or value == "" else float(value)
    except (TypeError, ValueError):
        return None


def _fundamental_summary(data: dict[str, Any]) -> dict[str, Any]:
    consensus = (data.get("consensus_statistics") or {}).get("latest") or {}
    rating = (data.get("rating_summary") or {}).get("latest") or {}
    target = (data.get("target_price") or {}).get("latest") or {}
    positive = sum(_number(rating.get(name)) or 0 for name in ("buy_num", "add_num"))
    neutral = _number(rating.get("neutral_num")) or 0
    negative = sum(
        _number(rating.get(name)) or 0 for name in ("reduce_num", "sell_num")
    )
    rating_total = _number(rating.get("rating_num"))
    if rating_total is None:
        rating_total = positive + neutral + negative
    return {
        "schema_version": "research-fundamental-evidence/v1",
        "consensus_revision": {
            "status": "available" if consensus else "empty",
            "observation_date": consensus.get("end_date"),
            "forecast_period": consensus.get("est_report_date"),
            "eps_upgrades": _number(consensus.get("est_eps_add")),
            "eps_downgrades": _number(consensus.get("est_eps_reduce")),
            "eps_unchanged": _number(consensus.get("est_eps_maint")),
            "revenue_upgrades": _number(consensus.get("est_oper_rev_add")),
            "revenue_downgrades": _number(consensus.get("est_oper_rev_reduce")),
            "revenue_unchanged": _number(consensus.get("est_oper_rev_maint")),
        },
        "rating_consensus": {
            "status": "available" if rating else "empty",
            "observation_date": rating.get("end_date"),
            "window": rating.get("date_flag"),
            "positive": positive if rating else None,
            "neutral": neutral if rating else None,
            "negative": negative if rating else None,
            "total": rating_total if rating else None,
            "positive_share_pct": (
                round(positive / rating_total * 100, 4)
                if rating and rating_total else None
            ),
            "upgrades": _number(rating.get("rating_upgrade_num")),
            "downgrades": _number(rating.get("rating_downgrade_num")),
            "organizations": _number(rating.get("rating_org_num")),
            "analysts": _number(rating.get("rating_analyst_num")),
        },
        "target_price": {
            "status": "available" if target else "not_requested_or_empty",
            "observation_date": target.get("end_date"),
            "window": target.get("date_flag"),
            "average": _number(target.get("target_price_avg")),
            "median": _number(target.get("target_price_med")),
            "minimum": _number(target.get("target_price_min")),
            "maximum": _number(target.get("target_price_max")),
            "standard_deviation": _number(target.get("target_price_sd")),
            "observations": _number(target.get("target_price_num")),
            "organizations": _number(target.get("target_price_org_num")),
            "analysts": _number(target.get("target_price_res_num")),
        },
    }


def _technical_summary(data: dict[str, Any]) -> dict[str, Any]:
    indicators = (data.get("provider_indicators") or {}).get("latest") or {}
    patterns = (data.get("provider_patterns") or {}).get("latest") or {}
    quote = (data.get("quote_snapshot") or {}).get("latest") or {}
    valuation = (data.get("valuation_snapshot") or {}).get("latest") or {}
    return {
        "schema_version": "research-technical-evidence/v1",
        "indicators": {
            "status": "available" if indicators else "empty",
            "observation_date": indicators.get("end_date"),
            "rsi": _number(indicators.get("rsi")),
            "macd": _number(indicators.get("macd")),
            "macd_dif": _number(indicators.get("dif")),
            "macd_signal": _number(indicators.get("dea")),
            "kdj": {
                "k": _number(indicators.get("kdj_k")),
                "d": _number(indicators.get("kdj_d")),
                "j": _number(indicators.get("kdj_j")),
            },
            "dmi": {
                "adx": _number(indicators.get("dmi_adx")),
                "adxr": _number(indicators.get("dmi_adxr")),
                "plus_di": _number(indicators.get("dmi_pdi")),
                "minus_di": _number(indicators.get("dmi_mdi")),
            },
            "moving_averages": {
                str(window): _number(indicators.get(f"close_ma_{window}d"))
                for window in (5, 10, 20, 60, 120, 250)
            },
        },
        "patterns": {
            "status": "available" if patterns else "not_requested_or_empty",
            "observation_date": patterns.get("end_date"),
            "ma_alignment": patterns.get("ma_bullish_bearish"),
            "breakouts": {
                str(window): patterns.get(f"break_ma_{window}d")
                for window in (5, 10, 20, 60)
            },
            "historical_new_high_count": patterns.get("hist_new_high_count"),
            "historical_new_low_count": patterns.get("hist_new_low_count"),
        },
        "quote": {
            "status": "available" if quote else "not_requested_or_empty",
            "observed_at": quote.get("latest_trade_time"),
            "last": _number(quote.get("last") or quote.get("close")),
            "previous_close": _number(quote.get("previous_close")),
            "change_pct": _number(quote.get("pct_chg")),
            "volume": _number(quote.get("volume")),
            "amount": _number(quote.get("amount")),
            "trade_status": quote.get("trade_status"),
            "suspension_state": quote.get("suspension_state"),
            "limit_status": quote.get("limit_status"),
        },
        "valuation": {
            "status": "available" if valuation else "not_requested_or_empty",
            "observed_at": valuation.get("snapshot_date") or valuation.get("date"),
            "pe_ttm": _number(valuation.get("pe_ttm")),
            "pe_forward": _number(valuation.get("pe_fwd")),
            "pb": _number(valuation.get("pb")),
            "turnover_rate": _number(valuation.get("turnover_rate")),
            "total_market_value": _number(valuation.get("total_mv")),
            "float_market_value": _number(valuation.get("circ_mv")),
        },
    }


class FinancialResearchEvidenceService:
    """Normalize optional 蚂蚁数据源 evidence for research responses."""

    def __init__(self, query_broker):
        self._broker = query_broker

    def _query(
        self,
        *,
        routes: dict[str, str],
        parameters: dict[str, dict[str, Any]],
        as_of: date,
        cache_ttl_seconds: int,
        point_in_time_safe: bool,
    ) -> dict[str, Any]:
        requested_at = datetime.now(timezone.utc)
        requests = [
            {"url": route, "params": parameters[name]}
            for name, route in routes.items()
        ]
        try:
            result = self._broker.query(
                ConnectorRequest(
                    source_id="financial_data",
                    endpoint_key="common_query",
                    acquisition_mode=AcquisitionMode.QUERY_THROUGH,
                    parameters={"mode": "data", "requests": requests},
                ),
                cache_ttl_seconds=cache_ttl_seconds,
            )
            if result.status != "complete" or not result.records:
                raise RuntimeError("provider request did not complete")
            response = result.records[0]
        except Exception as exc:
            return {
                "status": "unavailable",
                "source_id": "financial_data",
                "as_of": as_of,
                "point_in_time_safe": point_in_time_safe,
                "data": {name: None for name in routes},
                "provenance": [
                    {
                        "source_id": "financial_data",
                        "source_dataset": route,
                        "returned": 0,
                        "state": "unavailable",
                    }
                    for route in routes.values()
                ],
                "error": {
                    "code": type(exc).__name__,
                    "message": "蚂蚁数据源 evidence is temporarily unavailable",
                },
                "requested_at": requested_at,
            }

        decoded: dict[str, list[dict[str, Any]]] = {}
        route_errors: dict[str, dict[str, str]] = {}
        for name, route in routes.items():
            try:
                decoded[name] = tabular_rows(response, route=route)
            except Exception as exc:
                decoded[name] = []
                route_errors[name] = {
                    "code": type(exc).__name__,
                    "message": "蚂蚁数据源 route response failed validation",
                }
        empty = [
            name for name, rows in decoded.items()
            if not rows and name not in route_errors
        ]
        available = [name for name, rows in decoded.items() if rows]
        if len(route_errors) == len(decoded):
            status = "unavailable"
        elif route_errors or empty:
            status = "partial" if available else "empty"
        else:
            status = "ready"
        return {
            "status": status,
            "source_id": "financial_data",
            "as_of": as_of,
            "point_in_time_safe": point_in_time_safe,
            "data": {
                name: {
                    "latest": _latest(rows),
                    "rows": rows[:20],
                    "returned": len(rows),
                    "status": (
                        "unavailable" if name in route_errors
                        else "available" if rows else "empty"
                    ),
                    **({"error": route_errors[name]} if name in route_errors else {}),
                }
                for name, rows in decoded.items()
            },
            "provenance": [
                {
                    "source_id": "financial_data",
                    "source_dataset": route,
                    "returned": len(decoded[name]),
                    "state": (
                        "unavailable" if name in route_errors
                        else "available" if decoded[name] else "empty"
                    ),
                }
                for name, route in routes.items()
            ],
            "route_errors": route_errors,
            "cache": dict(result.evidence).get("cache"),
            "provider_fetched_at": dict(result.evidence).get("fetched_at"),
            "warnings": list(result.warnings) + [
                "Provider date filters do not certify publication-time or revision-safe history."
            ],
            "requested_at": requested_at,
        }

    def fundamentals(self, symbol: str, *, as_of: date) -> dict[str, Any]:
        historical = as_of < business_now().date()
        routes = {
            "consensus_statistics": FUNDAMENTAL_ROUTES["consensus_statistics"],
            "rating_summary": FUNDAMENTAL_ROUTES["rating_summary"],
        }
        common = {
            "symbols": [symbol],
            "end_date": as_of.isoformat(),
        }
        parameters = {name: dict(common) for name in routes}
        if not historical:
            routes["target_price"] = FUNDAMENTAL_ROUTES["target_price"]
            parameters["target_price"] = {"symbols": [symbol]}
        evidence = self._query(
            routes=routes,
            parameters=parameters,
            as_of=as_of,
            cache_ttl_seconds=21_600,
            point_in_time_safe=False,
        )
        evidence["normalized"] = _fundamental_summary(evidence["data"])
        evidence["omitted"] = ([{
            "source_dataset": FUNDAMENTAL_ROUTES["target_price"],
            "reason": "provider route has no historical cutoff contract",
        }] if historical else [])
        return evidence

    def technicals(
        self,
        symbol: str,
        *,
        as_of: date,
        include_realtime: bool = True,
    ) -> dict[str, Any]:
        historical = as_of < business_now().date()
        dated_routes = {
            "provider_indicators": TECHNICAL_ROUTES["provider_indicators"],
        }
        evidence = self._query(
            routes=dated_routes,
            parameters={
                "provider_indicators": {
                    "symbols": [symbol],
                    "end_date": as_of.isoformat(),
                }
            },
            as_of=as_of,
            cache_ttl_seconds=3_600,
            point_in_time_safe=False,
        )
        current: dict[str, Any] | None = None
        if not historical:
            current_routes = {
                "provider_patterns": TECHNICAL_ROUTES["provider_patterns"],
            }
            if include_realtime:
                current_routes.update(REALTIME_ROUTES)
            current = self._query(
                routes=current_routes,
                parameters={
                    name: {"symbols": [symbol]}
                    for name in current_routes
                },
                as_of=as_of,
                cache_ttl_seconds=15 if include_realtime else 3_600,
                point_in_time_safe=False,
            )

        combined_data = dict(evidence["data"])
        combined_provenance = list(evidence["provenance"])
        route_errors = dict(evidence.get("route_errors", {}))
        statuses = [evidence["status"]]
        warnings = list(evidence.get("warnings", []))
        if current is not None:
            combined_data.update(current["data"])
            combined_provenance.extend(current["provenance"])
            route_errors.update(current.get("route_errors", {}))
            statuses.append(current["status"])
            warnings.extend(current.get("warnings", []))
        if "unavailable" in statuses:
            status = "unavailable" if all(item == "unavailable" for item in statuses) else "partial"
        elif "partial" in statuses or "empty" in statuses:
            status = "partial" if any(item == "ready" for item in statuses) else "empty"
        else:
            status = "ready"
        result = {
            **evidence,
            "status": status,
            "data": combined_data,
            "provenance": combined_provenance,
            "route_errors": route_errors,
            "warnings": warnings,
            "omitted": ([
                {
                    "source_dataset": route,
                    "reason": "provider route has no historical cutoff contract",
                }
                for route in (
                    TECHNICAL_ROUTES["provider_patterns"],
                    *REALTIME_ROUTES.values(),
                )
            ] if historical else []),
        }
        result["normalized"] = _technical_summary(combined_data)
        return result
