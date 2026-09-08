"""Derived collection policies for every cataloged Tushare interface.

The official contract describes fields and permissions. A collection policy
adds operational semantics: cadence, parameter partitioning, pagination and
rate limits. Policies are conservative by design; unsupported fan-out is
marked manual instead of pretending a single request is complete.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import re
from typing import Literal

from service.tushare_catalog import (
    TushareInterfaceCatalog,
    TushareInterfaceContract,
)


Cadence = Literal["daily", "weekly", "monthly", "quarterly", "manual"]
ParameterStrategy = Literal[
    "snapshot",
    "trade_date",
    "date_window",
    "month",
    "report_period",
    "week",
    "ts_code_fanout",
    "dependency_fanout",
    "manual",
]
PaginationMode = Literal["none", "offset", "partitioned"]


@dataclass(frozen=True, slots=True)
class TushareCollectionPolicy:
    api_name: str
    cadence: Cadence
    parameter_strategy: ParameterStrategy
    pagination_mode: PaginationMode
    page_size: int
    max_pages: int
    documented_row_limit: int | None
    min_interval_seconds: float
    automatic_safe: bool
    automatic_reason: str


_RATE_LIMIT_SECONDS = {
    "hk_daily": 3600.0,
    "stk_mins": 3600.0,
}

_PAGE_SIZE_OVERRIDES = {
    # Live gateway probes on 2026-09-08 returned the exact same unique rows
    # with 1,000- and 5,000-row offset pagination.  The larger page cuts
    # current market-wide requests from 6/10 pages to 2 pages respectively.
    "stk_limit": 5000,
    "index_daily": 5000,
    # Live gateway verification: requests above 3,000 are capped to 3,000,
    # while 3,000 + matching offsets exhaust the endpoint without gaps.
    "kpl_concept_cons": 3000,
    # Live exact-date probes on 2026-09-08 proved standard offset exhaustion:
    # 5,000 + 3,316 distinct rows for ccass_hold and a 3,800-row documented
    # page boundary for hk_hold.
    "ccass_hold": 5000,
    "hk_hold": 3800,
}

# Some official pages keep the call limit in a separate "调取说明" block that
# is not part of the generated description/permission contract. Keep these
# reviewed limits explicit rather than losing the evidence during catalog
# generation. ``daily`` doc 27 states 6,000 rows per request.
_DOCUMENTED_ROW_LIMIT_OVERRIDES = {
    "daily": 6000,
}

_DEPENDENCY_FANOUT = {
    "p_get",
}

# The official table labels ``ts_code`` as required, but its description says
# it is an alternative to ``trade_date``. Daily market-wide collection is both
# supported and substantially safer than creating thousands of symbol jobs.
_TRADE_DATE_ALTERNATIVES = {
    "daily_basic",
    # The parameter table marks ts_code as required, but live gateway
    # verification proves that trade_date alone returns the complete market.
    "index_daily",
}

_STRATEGY_OVERRIDES: dict[str, ParameterStrategy] = {
    # These endpoints document all parameters as optional but reject an empty
    # request. The override encodes the smallest complete request partition.
    "dividend": "trade_date",
    "fund_div": "trade_date",
    "fut_weekly_detail": "week",
    # A market-wide request cannot be proven complete for these interfaces.
    "factor_value": "dependency_fanout",
    "fund_basic": "manual",
    "fund_nav": "ts_code_fanout",
    "fund_portfolio": "ts_code_fanout",
    "fut_index_daily": "ts_code_fanout",
    # A market-wide ccass_hold_detail date contains more than one million
    # institution-seat rows. It must remain an explicitly scoped query rather
    # than silently creating an unbounded daily workload.
    "ccass_hold_detail": "manual",
    # Live collection proved that one market-wide partition reaches an upstream
    # cap. Keep these interfaces implemented, but do not automate them until
    # their dependency fan-out has an authoritative universe.
    "tdx_member": "dependency_fanout",
    "opt_daily": "manual",
    "moneyflow_dc": "ts_code_fanout",
    # Live probes prove both endpoints support a complete market-wide
    # trade_date partition through standard limit/offset pagination.
    "index_weekly": "trade_date",
    "index_monthly": "trade_date",
    "index_daily": "trade_date",
    # Live collection reached the upstream hard cap for unpartitioned calls.
    # These contracts are complete only through the allow-listed fan-out
    # universes in service.collection_jobs.fanout.
    "ci_index_member": "dependency_fanout",
    "index_member_all": "dependency_fanout",
    "pledge_stat": "ts_code_fanout",
    "fut_holding": "manual",
    "etf_sz_cons": "ts_code_fanout",
    "etf_sh_cons": "ts_code_fanout",
    "dc_concept_cons": "dependency_fanout",
    "bc_otcqt": "ts_code_fanout",
    "fut_weekly_detail": "manual",
}

_CADENCE_OVERRIDES: dict[str, Cadence] = {
    "dividend": "daily",
    "fund_div": "daily",
    "index_weekly": "weekly",
    "index_monthly": "monthly",
}

_NO_LOOP_APIS = {
    "p_list",
    "p_get",
    "ths_index",  # Official documentation explicitly says not to loop.
}

# Tushare's HTTP gateway accepts the standard ``limit``/``offset`` arguments
# for these ETF constituent endpoints even though the parameter tables omit
# them.  A live probe is important here: broad ETFs can contain exactly 1000
# rows, so treating that response as a complete non-paginated partition would
# either fail forever or silently truncate a future 1000+ constituent basket.
_OFFSET_PAGINATION_OVERRIDES = {
    # Official doc 27 supports market-wide trade_date requests with a 6,000
    # row call limit. Live probes on 2000-08-11, 2000-10-30 and 2026-09-04
    # prove that standard limit/offset is honored. Offset exhaustion prevents
    # a legitimate 1,000-row historical cross-section from being mistaken for
    # a transport cap and remains safe if the market grows beyond 6,000 rows.
    "daily",
    # Live gateway verification on 2026-09-06 proved that the documented
    # 15,000-row cap is pageable: market=O,status=L returned distinct rows at
    # offsets 0/5,000/10,000/15,000/20,000 and exhausted at 24,974 rows.
    # The parameter table omits limit/offset, so keep this explicit evidence.
    "fund_basic",
    "etf_sh_cons",
    "etf_sz_cons",
    # Live verification on 2026-08-30 returned 2000 rows at offsets 0 and
    # 2000 for one trade_date. The gateway supports standard limit/offset.
    "fund_share",
    # Live verification on 2026-09-07 exhausted the day's 22,248-row
    # ``float_date`` partition in four distinct pages (6,000/6,000/6,000/
    # 4,248).  Without offset exhaustion the first round page was correctly
    # rejected as suspicious, but the routine job could never complete.
    "share_float",
    # Two historical trade dates (2010-12-22/23) contain exactly 2,000 rows.
    # Live probes returned a distinct empty page at offset 2,000, proving that
    # the round first page is legitimate and that standard offset is honored.
    "stk_limit",
    # A full financing/margin detail partition is normally about 4,400 rows.
    # Live probes prove that limit/offset is honored; page exhaustion and the
    # coverage layer's market-universe threshold are both required because
    # exchanges can publish at different times.
    "margin_detail",
    # Live verification on 2026-09-03 exhausted 2026-08-28 weekly data in
    # 15 pages (14,312 rows) and 2026-08-31 monthly data in 10 pages
    # (9,364 rows). Per-symbol fan-out is unnecessary and much less reliable.
    "index_weekly",
    "index_monthly",
    "index_daily",
    # Single-day securities-lending scopes can exceed 2,000 rows. Live probes
    # confirm that the gateway honors standard limit/offset for all four.
    "slb_len",
    "slb_len_mm",
    "slb_sec",
    "slb_sec_detail",
    # The official parameter table omits limit/offset, but a live 2026-08-28
    # probe exhausted 13,463 rows in 14 pages.  A capped 3,000-row request is
    # therefore recoverable without an inferred concept universe.
    "kpl_concept_cons",
    "ccass_hold",
    "hk_hold",
}

# hk_daily is a separately purchased, one-request-per-hour interface. A single
# exact-date request per business day is bounded and the distributed limiter
# guarantees that manual/retry activity cannot violate the provider interval.
_SAFE_LOW_FREQUENCY_APIS = {"hk_daily"}


def _parameter_names(contract: TushareInterfaceContract) -> set[str]:
    return {item["name"] for item in contract.input_parameters}


def _required_parameters(contract: TushareInterfaceContract) -> set[str]:
    return {
        item["name"]
        for item in contract.input_parameters
        if item.get("required", "").upper() == "Y"
    }


def _documented_row_limit(contract: TushareInterfaceContract) -> int | None:
    text = f"{contract.description} {contract.permission.get('official_text', '')}"
    patterns = (
        r"单次(?:请求)?最大(?:返回|获取|提取|可以提取)?\s*(\d+)\s*条?行?",
        r"每次请求最多返回\s*(\d+)\s*条?",
        r"单次\s*(\d+)\s*行",
        r"单次返回\s*(\d+)\s*行",
    )
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return int(match.group(1))
    return None


def _strategy(contract: TushareInterfaceContract) -> ParameterStrategy:
    names = _parameter_names(contract)
    required = _required_parameters(contract)
    if contract.api_name in _STRATEGY_OVERRIDES:
        return _STRATEGY_OVERRIDES[contract.api_name]
    if contract.api_name in _DEPENDENCY_FANOUT:
        return "dependency_fanout"
    if contract.api_name in _TRADE_DATE_ALTERNATIVES:
        return "trade_date"
    if required & {"ts_code", "symbol", "code"}:
        return "ts_code_fanout"
    if required & {"period", "report_date"}:
        return "report_period"
    if required & {"month", "m", "start_m", "start_month"}:
        return "month"
    if required & {"trade_date", "date", "cal_date"}:
        return "trade_date"
    if required & {"start_date", "end_date"}:
        return "date_window"
    if required:
        return "manual"
    if "trade_date" in names:
        return "trade_date"
    if {"start_date", "end_date"} <= names:
        return "date_window"
    if names & {"month", "m", "start_m", "start_month"}:
        return "month"
    if names & {"period", "report_date"}:
        return "report_period"
    return "snapshot"


def _cadence(
    contract: TushareInterfaceContract,
    strategy: ParameterStrategy,
) -> Cadence:
    if contract.api_name in _CADENCE_OVERRIDES:
        return _CADENCE_OVERRIDES[contract.api_name]
    if strategy in {"manual", "dependency_fanout", "ts_code_fanout"}:
        return "manual"
    if strategy == "report_period" or "财务" in contract.category_path:
        return "quarterly"
    if strategy == "month":
        return "monthly"
    if strategy == "week":
        return "weekly"
    if strategy in {"trade_date", "date_window"}:
        return "daily"
    if any(word in contract.description for word in ("实时", "每日", "日线", "公告", "新闻")):
        return "daily"
    return "weekly"


def derive_policy(contract: TushareInterfaceContract) -> TushareCollectionPolicy:
    strategy = _strategy(contract)
    names = _parameter_names(contract)
    required = _required_parameters(contract)
    row_limit = _DOCUMENTED_ROW_LIMIT_OVERRIDES.get(
        contract.api_name, _documented_row_limit(contract)
    )
    if contract.api_name in _NO_LOOP_APIS:
        pagination: PaginationMode = "none"
    elif (
        {"limit", "offset"} <= names
        or contract.api_name in _OFFSET_PAGINATION_OVERRIDES
    ):
        pagination = "offset"
    elif strategy in {
        "trade_date",
        "date_window",
        "month",
        "report_period",
        "week",
        "ts_code_fanout",
    }:
        pagination = "partitioned"
    else:
        pagination = "none"

    supported_required = {
        "snapshot": set(),
        "trade_date": {"trade_date", "date", "cal_date", "start_date", "end_date"},
        "date_window": {"trade_date", "date", "start_date", "end_date"},
        "month": {"month", "m", "start_m", "end_m", "start_month", "end_month"},
        "report_period": {"period", "report_date", "end_date"},
        "week": {"week", "start_week", "end_week"},
    }.get(strategy, set())
    unsupported_required = required - supported_required
    if contract.api_name in _TRADE_DATE_ALTERNATIVES:
        unsupported_required -= {"ts_code", "symbol", "code"}
    automatic_safe = (
        contract.collectable
        and bool(contract.document_ids)
        and strategy in {
            "snapshot",
            "trade_date",
            "date_window",
            "month",
            "report_period",
            "week",
        }
        and (
            contract.api_name not in _RATE_LIMIT_SECONDS
            or contract.api_name in _SAFE_LOW_FREQUENCY_APIS
        )
        and not unsupported_required
    )
    if not contract.collectable:
        reason = "interface is not collectable"
    elif not contract.document_ids:
        reason = "project extension lacks a complete official input contract"
    elif contract.api_name in _SAFE_LOW_FREQUENCY_APIS:
        reason = "safe exact-date daily request with distributed low-frequency pacing"
    elif contract.api_name in _RATE_LIMIT_SECONDS:
        reason = "requires dedicated low-frequency scheduling"
    elif strategy in {"ts_code_fanout", "dependency_fanout"}:
        reason = f"requires {strategy} orchestration"
    elif strategy == "manual":
        reason = "required parameters need an explicit policy"
    elif unsupported_required:
        reason = "unsupported required parameters: " + ", ".join(sorted(unsupported_required))
    else:
        reason = "safe for policy-driven scheduling"

    page_size = _PAGE_SIZE_OVERRIDES.get(
        contract.api_name, min(row_limit or 1000, 5000)
    )
    return TushareCollectionPolicy(
        api_name=contract.api_name,
        cadence=_cadence(contract, strategy),
        parameter_strategy=strategy,
        pagination_mode=pagination,
        page_size=max(page_size, 1),
        max_pages=100,
        documented_row_limit=row_limit,
        min_interval_seconds=_RATE_LIMIT_SECONDS.get(contract.api_name, 0.25),
        automatic_safe=automatic_safe,
        automatic_reason=reason,
    )


@lru_cache(maxsize=1)
def load_policies() -> tuple[TushareCollectionPolicy, ...]:
    return tuple(derive_policy(item) for item in TushareInterfaceCatalog().list())


class TusharePolicyRegistry:
    def __init__(self, policies: tuple[TushareCollectionPolicy, ...] | None = None):
        values = policies if policies is not None else load_policies()
        self._policies = {item.api_name: item for item in values}

    def get(self, api_name: str) -> TushareCollectionPolicy:
        try:
            return self._policies[api_name]
        except KeyError as exc:
            raise ValueError(f"Tushare collection policy is missing: {api_name}") from exc

    def list(self) -> tuple[TushareCollectionPolicy, ...]:
        return tuple(sorted(self._policies.values(), key=lambda item: item.api_name))
