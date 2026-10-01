"""Safe, bounded planning for catalog interfaces that require fan-out."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import hashlib
import json
from typing import Any, Literal

from service.acquisition_runtime.models import (
    BatchChildSpec,
    InvalidTaskParametersError,
    max_attempts_for_cadence,
)
from service.db import query


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
    # Routine callers can keep the exact-date contract while full
    # initialization uses an officially supported start/end range.
    allow_date_window: bool = False


# Authoritative static universe published in Tushare's fut_index_daily
# contract (doc 468). The endpoint currently requires ts_code even though the
# parameter table labels it optional, so a frozen documented universe is safer
# than attempting an incomplete market-wide request.
NH_FUTURES_INDEX_CODES = (
    "NHAI.NH", "NHCI.NH", "NHECI.NH", "NHFI.NH", "NHII.NH", "NHMI.NH",
    "NHNFI.NH", "NHPMI.NH", "A.NH", "AG.NH", "AL.NH", "AP.NH", "AU.NH",
    "BB.NH", "BU.NH", "C.NH", "CF.NH", "CS.NH", "CU.NH", "CY.NH",
    "ER.NH", "FB.NH", "FG.NH", "FU.NH", "HC.NH", "I.NH", "J.NH",
    "JD.NH", "JM.NH", "JR.NH", "L.NH", "LR.NH", "M.NH", "ME.NH",
    "NI.NH", "P.NH", "PB.NH", "PP.NH", "RB.NH", "RM.NH", "RO.NH",
    "RS.NH", "RU.NH", "SC.NH", "SF.NH", "SM.NH", "SN.NH", "SP.NH",
    "SR.NH", "TA.NH", "TC.NH", "V.NH", "WR.NH", "WS.NH", "Y.NH",
    "ZN.NH",
)


_DEFINITIONS = (
    FanoutDefinition(
        "bc_otcqt", "bc_bond", "ts_code", "trade_date",
        max_window_days=31, allow_date_window=True,
    ),
    FanoutDefinition("cb_rate", "convertible_bond", "ts_code", "none", 20),
    FanoutDefinition("cb_rating", "convertible_bond", "ts_code", "none", 20),
    FanoutDefinition(
        "cb_share", "convertible_bond", "ts_code", "ann_date", 20,
        max_window_days=366, allow_date_window=True,
    ),
    # A market-wide CCASS detail day can exceed one million rows. Per-stock
    # monthly windows keep every child bounded and independently resumable.
    FanoutDefinition(
        "ccass_hold_detail", "stock", "ts_code", "date_window", 1, (), 31
    ),
    FanoutDefinition("top10_cb_holders", "convertible_bond", "ts_code", "period", 20),
    FanoutDefinition("cyq_chips", "stock", "ts_code", "date_window", 1, (), 31),
    FanoutDefinition("cyq_perf", "stock", "ts_code", "date_window", 1, (), 31),
    # The non-VIP dividend endpoint is complete per stock and has no reliable
    # market-wide historical window. One all-history request per frozen listed
    # stock is the bounded recovery scope used by research backfills.
    FanoutDefinition("dividend", "stock", "ts_code", "none"),
    FanoutDefinition("dc_concept_cons", "stock", "ts_code", "trade_date"),
    FanoutDefinition(
        "etf_sh_cons", "etf_sh", "ts_code", "trade_date",
        max_window_days=31, allow_date_window=True,
    ),
    FanoutDefinition(
        "etf_sz_cons", "etf_sz", "ts_code", "trade_date",
        max_window_days=31, allow_date_window=True,
    ),
    # One stock returns every factor, while one factor returns every stock.
    # Fan-out by factor_name remains below the 1000-call daily allowance.
    FanoutDefinition(
        "factor_value", "factor_name", "factor_name", "trade_date",
        max_window_days=31, allow_date_window=True,
    ),
    FanoutDefinition("fina_audit", "stock", "ts_code", "period"),
    FanoutDefinition("fina_indicator", "stock", "ts_code", "period"),
    FanoutDefinition("fina_mainbz", "stock", "ts_code", "period"),
    # The official contract explicitly supports comma-separated stock codes.
    # Twenty companies for one report period remain comfortably below the
    # response cap and avoid thousands of unnecessary one-code requests.
    FanoutDefinition("stk_rewards", "stock", "ts_code", "period", 20),
    FanoutDefinition("top10_floatholders", "stock", "ts_code", "period"),
    FanoutDefinition("top10_holders", "stock", "ts_code", "period"),
    FanoutDefinition("fund_nav", "fund", "ts_code", "date_window", 1, (), 366),
    FanoutDefinition("fund_portfolio", "fund", "ts_code", "period"),
    FanoutDefinition("index_weight", "index", "index_code", "date_window", 1, (), 31),
    # index_weekly/index_monthly deliberately do not fan out by index code.
    # Live probes proved that an exact market-wide trade_date request supports
    # offset exhaustion; per-index fan-out turns one logical period into tens
    # of thousands of calls and is both slower and less reliable.
    FanoutDefinition(
        "moneyflow_dc", "stock", "ts_code", "trade_date",
        max_window_days=31, allow_date_window=True,
    ),
    FanoutDefinition(
        "tdx_member", "tdx_index", "ts_code", "trade_date",
        max_window_days=31, allow_date_window=True,
    ),
    # ths_member is capped at 6,000 rows market-wide and the contract exposes
    # only one board-code predicate. Live verification shows memberships for
    # every ths_index type (including BB), so freeze the whole local universe.
    FanoutDefinition("ths_member", "ths_index", "ts_code", "none"),
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
        allow_date_window=True,
    ),
    FanoutDefinition(
        # Live gateway verification on 2026-09-08 showed that this endpoint
        # does not accept comma-separated index codes: a 20-code request
        # returned no rows while the same date/code requested individually
        # returned data. Keep one code per durable child job.
        "fut_index_daily", "static", "ts_code", "trade_date", 1,
        NH_FUTURES_INDEX_CODES,
        allow_date_window=True,
    ),
    FanoutDefinition(
        "opt_daily", "static", "exchange", "trade_date", 1,
        ("SSE", "SZSE", "CFFEX", "DCE", "SHFE", "CZCE"),
        allow_date_window=True,
    ),
    FanoutDefinition(
        "fut_weekly_monthly", "static", "freq", "date_window", 1,
        ("week", "month"), 7,
    ),
    FanoutDefinition(
        "stk_week_month_adj", "static", "freq", "date_window", 1,
        ("week", "month"), 7,
    ),
    FanoutDefinition(
        "stk_weekly_monthly", "static", "freq", "date_window", 1,
        ("week", "month"), 31,
    ),
    FanoutDefinition(
        "stock_hsgt", "static", "type", "trade_date", 1,
        ("HK_SZ", "SZ_HK", "HK_SH", "SH_HK"),
        max_window_days=31,
        allow_date_window=True,
    ),
    FanoutDefinition(
        "dc_index", "static", "idx_type", "trade_date", 1, ("概念板块",),
        max_window_days=31,
        allow_date_window=True,
    ),
)
FANOUT_DEFINITIONS = {item.api_name: item for item in _DEFINITIONS}


def list_fanout_values(source: str, *, as_of: date | None = None) -> list[str]:
    """Return an allow-listed point-in-time universe for one V2 acquire node."""

    statements = {
        "stock": """
            SELECT ts_code FROM stock_basic
            WHERE ts_code IS NOT NULL
              AND (%s::DATE IS NULL OR (
                (NULLIF(list_date, '') IS NULL OR list_date <= TO_CHAR(%s::DATE, 'YYYYMMDD'))
                AND (NULLIF(delist_date, '') IS NULL OR delist_date >= TO_CHAR(%s::DATE, 'YYYYMMDD'))
              )) ORDER BY ts_code
        """,
        "index": "SELECT ts_code FROM index_basic WHERE ts_code IS NOT NULL ORDER BY ts_code",
        "ci_index": "SELECT DISTINCT ts_code FROM tushare_norm_ci_daily WHERE ts_code IS NOT NULL ORDER BY ts_code",
        "sw_l3_index": "SELECT DISTINCT index_code FROM tushare_norm_index_classify WHERE index_code IS NOT NULL AND level='L3' ORDER BY index_code",
        "convertible_bond": """
            WITH latest AS (
              SELECT DISTINCT ON (ts_code) ts_code,list_date,delist_date
              FROM tushare_norm_cb_basic WHERE ts_code IS NOT NULL
              ORDER BY ts_code,_source_collected_at DESC
            ) SELECT ts_code FROM latest WHERE %s::DATE IS NULL OR (
              (list_date IS NULL OR list_date <= %s::DATE)
              AND (delist_date IS NULL OR delist_date >= %s::DATE)
            ) ORDER BY ts_code
        """,
        "fund": """
            WITH latest AS (
              SELECT DISTINCT ON (ts_code)
                ts_code,list_date,found_date,delist_date,due_date
              FROM tushare_norm_fund_basic WHERE ts_code IS NOT NULL
              ORDER BY ts_code,_source_collected_at DESC
            ) SELECT ts_code FROM latest WHERE %s::DATE IS NULL OR (
              (COALESCE(list_date,found_date) IS NULL OR COALESCE(list_date,found_date) <= %s::DATE)
              AND (COALESCE(delist_date,due_date) IS NULL OR COALESCE(delist_date,due_date) >= %s::DATE)
            ) ORDER BY ts_code
        """,
        "bc_bond": "SELECT DISTINCT ts_code FROM tushare_norm_bc_bestotcqt WHERE ts_code IS NOT NULL ORDER BY ts_code",
        "etf_sh": "SELECT DISTINCT ts_code FROM tushare_norm_etf_basic WHERE ts_code IS NOT NULL AND ts_code LIKE '%.SH' ORDER BY ts_code",
        "etf_sz": "SELECT DISTINCT ts_code FROM tushare_norm_etf_basic WHERE ts_code IS NOT NULL AND ts_code LIKE '%.SZ' ORDER BY ts_code",
        "tdx_index": "SELECT DISTINCT ts_code FROM tdx_index WHERE ts_code IS NOT NULL ORDER BY ts_code",
        "ths_index": "SELECT DISTINCT ts_code FROM ths_index WHERE ts_code IS NOT NULL ORDER BY ts_code",
        "pro_data": "SELECT DISTINCT name FROM tushare_norm_p_list WHERE name IS NOT NULL ORDER BY name",
        "factor_name": "SELECT DISTINCT factor_name FROM tushare_norm_factor_value WHERE factor_name IS NOT NULL AND factor_name<>'' ORDER BY factor_name",
    }
    try:
        statement = statements[source]
    except KeyError as exc:
        raise ValueError(f"unsupported fan-out universe: {source}") from exc
    params = (as_of, as_of, as_of) if source in {"stock", "convertible_bond", "fund"} else None
    return [str(row[next(iter(row))]) for row in query(statement, params)]


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
                    item.max_window_days
                    if item.scope == "date_window" or item.allow_date_window
                    else None
                ),
                "allow_date_window": item.allow_date_window,
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
                else self._repository.list_fanout_values(
                    definition.source, as_of=expected_for_override or expected_for
                )
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
            "universe_as_of": (
                (expected_for_override or expected_for).isoformat()
                if expected_for_override or expected_for
                else None
            ),
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
                    max_attempts=max_attempts_for_cadence(cadence),
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
        if definition.allow_date_window and start_date and end_date:
            parsed_start = date.fromisoformat(
                f"{start_date[:4]}-{start_date[4:6]}-{start_date[6:]}"
            )
            parsed_end = date.fromisoformat(
                f"{end_date[:4]}-{end_date[4:6]}-{end_date[6:]}"
            )
            if parsed_start > parsed_end:
                raise InvalidTaskParametersError(
                    "start_date must not be later than end_date"
                )
            if (parsed_end - parsed_start).days + 1 > definition.max_window_days:
                raise InvalidTaskParametersError(
                    f"date window cannot exceed {definition.max_window_days} days"
                )
            return (
                {"start_date": start_date, "end_date": end_date},
                f"{start_date}-{end_date}",
                parsed_end,
            )
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
