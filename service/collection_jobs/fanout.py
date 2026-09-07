"""Safe, bounded planning for catalog interfaces that require fan-out."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import hashlib
import json
from typing import Any, Literal

from service.collection_jobs.models import BatchChildSpec, InvalidTaskParametersError


ScopeKind = Literal["none", "trade_date", "ann_date", "period", "date_window"]


@dataclass(frozen=True, slots=True)
class FanoutDefinition:
    api_name: str
    source: str
    parameter_name: str
    scope: ScopeKind
    batch_size: int = 1
    static_values: tuple[str, ...] = ()
    max_window_days: int = 366


_DEFINITIONS = (
    FanoutDefinition("bc_otcqt", "bc_bond", "ts_code", "trade_date"),
    FanoutDefinition("cb_rate", "convertible_bond", "ts_code", "none", 20),
    FanoutDefinition("cb_rating", "convertible_bond", "ts_code", "none", 20),
    FanoutDefinition("cb_share", "convertible_bond", "ts_code", "ann_date", 20),
    FanoutDefinition("top10_cb_holders", "convertible_bond", "ts_code", "period", 20),
    FanoutDefinition("cyq_chips", "stock", "ts_code", "date_window", 1, (), 31),
    FanoutDefinition("cyq_perf", "stock", "ts_code", "date_window", 1, (), 31),
    FanoutDefinition("dc_concept_cons", "stock", "ts_code", "trade_date"),
    FanoutDefinition("etf_sh_cons", "etf_sh", "ts_code", "trade_date"),
    FanoutDefinition("etf_sz_cons", "etf_sz", "ts_code", "trade_date"),
    # One stock returns every factor, while one factor returns every stock.
    # Fan-out by factor_name remains below the 1000-call daily allowance.
    FanoutDefinition("factor_value", "factor_name", "factor_name", "trade_date"),
    FanoutDefinition("fina_audit", "stock", "ts_code", "period"),
    FanoutDefinition("fina_indicator", "stock", "ts_code", "period"),
    FanoutDefinition("fina_mainbz", "stock", "ts_code", "period"),
    FanoutDefinition("stk_rewards", "stock", "ts_code", "period"),
    FanoutDefinition("top10_floatholders", "stock", "ts_code", "period"),
    FanoutDefinition("top10_holders", "stock", "ts_code", "period"),
    FanoutDefinition("fund_nav", "fund", "ts_code", "date_window", 1, (), 366),
    FanoutDefinition("fund_portfolio", "fund", "ts_code", "period"),
    FanoutDefinition("index_weight", "index", "index_code", "date_window", 1, (), 31),
    FanoutDefinition("index_weekly", "index", "ts_code", "date_window", 1, (), 3660),
    FanoutDefinition("index_monthly", "index", "ts_code", "date_window", 1, (), 3660),
    FanoutDefinition("moneyflow_dc", "stock", "ts_code", "trade_date"),
    FanoutDefinition("tdx_member", "tdx_index", "ts_code", "trade_date"),
    FanoutDefinition("ci_index_member", "ci_index", "l3_code", "none"),
    FanoutDefinition("index_member_all", "sw_l3_index", "l3_code", "none"),
    FanoutDefinition("pledge_stat", "stock", "ts_code", "none"),
    FanoutDefinition("p_get", "pro_data", "name", "none"),
    FanoutDefinition(
        "fut_basic", "static", "exchange", "none", 1,
        ("CFFEX", "DCE", "CZCE", "SHFE", "INE", "GFEX"),
    ),
    FanoutDefinition(
        "fut_holding", "static", "exchange", "trade_date", 1,
        ("CFFEX", "DCE", "CZCE", "SHFE", "INE", "GFEX"),
    ),
    FanoutDefinition(
        "opt_daily", "static", "exchange", "trade_date", 1,
        ("SSE", "SZSE", "CFFEX", "DCE", "SHFE", "CZCE"),
    ),
    FanoutDefinition(
        "fut_weekly_monthly", "static", "freq", "date_window", 1,
        ("week", "month"),
    ),
    FanoutDefinition(
        "stk_week_month_adj", "static", "freq", "date_window", 1,
        ("week", "month"),
    ),
    FanoutDefinition(
        "dc_index", "static", "idx_type", "trade_date", 1, ("概念板块",),
    ),
)
FANOUT_DEFINITIONS = {item.api_name: item for item in _DEFINITIONS}


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _compact(value: date | str | None, name: str) -> str | None:
    if value is None:
        return None
    try:
        parsed = value if isinstance(value, date) else date.fromisoformat(str(value))
    except ValueError as exc:
        raise InvalidTaskParametersError(f"{name} must use YYYY-MM-DD") from exc
    return parsed.strftime("%Y%m%d")


class FanoutPlanner:
    """Build durable leaf jobs without permitting arbitrary or unbounded fan-out."""

    def __init__(self, repository, registry):
        self._repository = repository
        self._registry = registry

    @staticmethod
    def definitions() -> list[dict[str, Any]]:
        return [
            {
                "api_name": item.api_name,
                "universe_source": item.source,
                "partition_parameter": item.parameter_name,
                "required_scope": item.scope,
                "batch_size": item.batch_size,
                "max_window_days": (
                    item.max_window_days if item.scope == "date_window" else None
                ),
                "static_values": list(item.static_values),
            }
            for item in _DEFINITIONS
        ]

    def create_batch(
        self,
        request: dict[str, Any],
        *,
        idempotency_key: str | None,
        universe_values: list[str] | None = None,
        universe_source: str | None = None,
        cadence: str = "backfill",
        period_key_override: str | None = None,
        expected_for_override: date | None = None,
        priority: int = 20,
        resource_class: str = "backfill",
    ) -> tuple[dict, bool]:
        api_name = request["api_name"]
        try:
            definition = FANOUT_DEFINITIONS[api_name]
        except KeyError as exc:
            raise InvalidTaskParametersError(
                f"{api_name} is not enabled for safe fan-out collection"
            ) from exc

        scope, period_key, expected_for = self._scope(definition, request)
        # Campaign metadata is the system-wide period identity.  Prefer it
        # over the compact upstream parameter representation produced by the
        # scope parser so parent and child jobs remain queryable by one key.
        period_key = period_key_override or period_key
        expected_for = expected_for_override or expected_for
        if universe_values is None:
            values = (
                list(definition.static_values)
                if definition.source == "static"
                else self._repository.list_fanout_values(definition.source)
            )
        else:
            if universe_source != definition.source:
                raise InvalidTaskParametersError(
                    "frozen fan-out universe source does not match definition"
                )
            values = list(universe_values)
        if not values:
            raise InvalidTaskParametersError(
                f"fan-out dependency {definition.source} has no available values"
            )

        offset = int(request.get("offset", 0))
        max_children = int(request.get("max_children", 50))
        selected_limit = max_children * definition.batch_size
        selected = values[offset : offset + selected_limit]
        if not selected:
            raise InvalidTaskParametersError(
                f"offset {offset} is beyond universe size {len(values)}"
            )

        normalized_request = {
            key: (value.isoformat() if isinstance(value, date) else value)
            for key, value in request.items()
            if value is not None
        }
        plan = {
            "api_name": api_name,
            "universe_source": definition.source,
            "universe_total": len(values),
            "universe_digest": _digest(values),
            "entity_offset": offset,
            "entities_selected": len(selected),
            "selected_digest": _digest(selected),
            "batch_size": definition.batch_size,
            "child_total": (
                len(selected) + definition.batch_size - 1
            ) // definition.batch_size,
            "next_offset": offset + len(selected),
            "has_more": offset + len(selected) < len(values),
            "scope": scope,
        }
        parent_parameters = {"request": normalized_request, "plan": plan}
        parent_key = idempotency_key or f"fanout:{api_name}:{_digest(parent_parameters)[:40]}"

        children: list[BatchChildSpec] = []
        for index in range(0, len(selected), definition.batch_size):
            chunk = selected[index : index + definition.batch_size]
            interface_parameters = {
                **scope,
                definition.parameter_name: ",".join(chunk),
            }
            task_parameters = {
                "api_name": api_name,
                "parameters": interface_parameters,
                "complete": True,
                "resume": True,
            }
            validated = self._registry.validate("tushare_interface", task_parameters)
            normalized = validated.model_dump(mode="json")
            handler = self._registry.handler_metadata("tushare_interface", normalized)
            children.append(
                BatchChildSpec(
                    task_name="tushare_interface",
                    parameters=normalized,
                    idempotency_key=f"fanout-child:{_digest([parent_key, index, normalized])}",
                    api_name=api_name,
                    cadence=cadence,
                    period_key=period_key,
                    expected_for=expected_for,
                    handler=handler,
                    priority=priority,
                    resource_class=resource_class,
                )
            )

        parent, created = self._repository.create_batch(
            parent_parameters,
            children,
            idempotency_key=parent_key,
            api_name=api_name,
            period_key=period_key,
            expected_for=expected_for,
            completion_evidence={"plan": plan},
            cadence=cadence,
            priority=priority,
            resource_class=resource_class,
        )
        if not created and parent.get("parameters") != parent_parameters:
            raise InvalidTaskParametersError(
                "idempotency key is already associated with another fan-out plan"
            )
        return parent, created

    @staticmethod
    def _scope(
        definition: FanoutDefinition,
        request: dict[str, Any],
    ) -> tuple[dict[str, str], str | None, date | None]:
        trade_date = _compact(request.get("trade_date"), "trade_date")
        ann_date = _compact(request.get("ann_date"), "ann_date")
        period = _compact(request.get("period"), "period")
        start_date = _compact(request.get("start_date"), "start_date")
        end_date = _compact(request.get("end_date"), "end_date")

        if definition.scope == "none":
            return {}, None, None
        if definition.scope == "trade_date":
            if not trade_date:
                raise InvalidTaskParametersError(
                    f"{definition.api_name} fan-out requires trade_date"
                )
            parsed = date.fromisoformat(
                f"{trade_date[:4]}-{trade_date[4:6]}-{trade_date[6:]}"
            )
            return {"trade_date": trade_date}, trade_date, parsed
        if definition.scope == "ann_date":
            if not ann_date:
                raise InvalidTaskParametersError(
                    f"{definition.api_name} fan-out requires ann_date"
                )
            return {"ann_date": ann_date}, ann_date, None
        if definition.scope == "period":
            if not period:
                raise InvalidTaskParametersError(
                    f"{definition.api_name} fan-out requires period"
                )
            if period[4:] not in {"0331", "0630", "0930", "1231"}:
                raise InvalidTaskParametersError("period must be a calendar quarter end")
            parameter = "end_date" if definition.api_name == "stk_rewards" else "period"
            return {parameter: period}, period, None
        if not start_date or not end_date:
            raise InvalidTaskParametersError(
                f"{definition.api_name} fan-out requires start_date and end_date"
            )
        start = date.fromisoformat(f"{start_date[:4]}-{start_date[4:6]}-{start_date[6:]}")
        end = date.fromisoformat(f"{end_date[:4]}-{end_date[4:6]}-{end_date[6:]}")
        if start > end:
            raise InvalidTaskParametersError("start_date must not be later than end_date")
        if (end - start).days + 1 > definition.max_window_days:
            raise InvalidTaskParametersError(
                f"{definition.api_name} date window cannot exceed "
                f"{definition.max_window_days} days"
            )
        return (
            {"start_date": start_date, "end_date": end_date},
            f"{start_date}:{end_date}",
            end,
        )
