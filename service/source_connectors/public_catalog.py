"""Explicit public-source contracts; registration is not live availability."""
from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from service.source_connectors.contracts import AcquisitionMode, EndpointSpec, SourceKind, SourceSpec


class Parameters(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Questions(Parameters):
    code: str = Field(pattern=r"^(00|30)\d{4}$")
    page: int = Field(default=1, ge=1, le=1000)
    page_size: int = Field(default=20, ge=1, le=50)


class ShanghaiQuestions(Parameters):
    code: str | None = Field(default=None, pattern=r"^(60|68|90)\d{4}$")
    kind: Literal["answered", "questions"] = "answered"
    page: int = Field(default=1, ge=1, le=1000)
    page_size: int = Field(default=20, ge=1, le=50)


class OptionContracts(Parameters):
    underlying: Literal["510050", "510300", "588000", "510500"] = "510050"
    side: Literal["call", "put"] = "call"


class OptionCode(Parameters):
    code: str = Field(pattern=r"^\d{8}$")


class YieldCurve(Parameters):
    start: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    end: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    curve: Literal["all", "treasury", "bank_aaa", "mtn_aaa"] = "all"

    @model_validator(mode="after")
    def bounded_dates(self):
        first, last = date.fromisoformat(self.start), date.fromisoformat(self.end)
        if not 0 <= (last - first).days <= 359:
            raise ValueError("query at most 360 days; split longer history explicitly")
        if first < date(2006, 3, 1):
            raise ValueError("earliest declared curve date is 2006-03-01")
        if last > date.today():
            raise ValueError("future curve dates are unsupported")
        return self


class RepoFixing(Parameters):
    kind: Literal["FR", "FDR"] = "FR"


class SocialFinancing(Parameters):
    year: int = Field(ge=2021, le=2100)


MODE = AcquisitionMode.QUERY_THROUGH
PUBLIC_SOURCES = tuple(SourceSpec(
    source_id=key, display_name=name, kind=SourceKind.HYBRID,
    acquisition_modes=(MODE,), timezone="Asia/Shanghai", base_url=url,
    license_policy={"persist_raw_records": False, "query_through_only": True},
    configuration={"adapter": "public_web", "business_scope": scope,
                   "availability": "requires_live_probe", "origin": origin},
) for key, name, url, scope, origin in [
    ("cninfo", "巨潮互动易", "https://irm.cninfo.com.cn", "深市投资者问答", "SZSE/CNINFO"),
    ("sse", "上证 e 互动", "https://sns.sseinfo.com", "沪市投资者问答", "SSE"),
    ("sina", "新浪财经", "https://stock.finance.sina.com.cn", "ETF 期权合约、报价、Greeks", "Sina"),
    ("pboc", "中国人民银行", "https://www.pbc.gov.cn", "社会融资规模增量分项", "PBOC"),
])

SOCIAL_FIELDS = "month afre_total rmb_loans fx_loans entrusted_loans trust_loans undiscounted_bankers_acceptance corporate_bonds government_bonds equity_financing abs_by_depository loans_written_off".split()
QUOTE_FIELDS = "code bid_vol bid last ask ask_vol open_interest pct strike prev_close open limit_up limit_down name amplitude high low volume amount".split()
GREEKS_FIELDS = "code name volume delta gamma theta vega iv high low trade_code strike last theory".split()

# Fields describe returned business values, not arbitrary transport columns.
DEFINITIONS = [
    ("cninfo", "investor_questions", "深市互动问答", Questions, "code company question answer answerer question_time".split(), "recent_pages", "text", 300),
    ("sse", "investor_questions", "沪市互动问答", ShanghaiQuestions, "id code name asker question question_time answer answer_time".split(), "recent_about_one_month_upstream_observation", "text", 300),
    ("sina", "option_contracts", "ETF 期权合约清单", OptionContracts, "underlying side month code".split(), "current_contracts", "identifiers", 300),
    ("sina", "option_quote", "ETF 期权 T 型报价", OptionCode, QUOTE_FIELDS, "snapshot_only", "upstream_native", 15),
    ("sina", "option_greeks", "ETF 期权 Greeks 与隐含波动率", OptionCode, GREEKS_FIELDS, "snapshot_only", "iv_decimal_other_fields_upstream_native", 15),
    ("chinabond", "yield_curve", "中债收益率曲线", YieldCurve, "date curve 3m 6m 1y 3y 5y 7y 10y 30y".split(), "treasury_2006-03-01_mtn_2006-12-25_bank_2009-12-24", "percent", 3600),
    ("chinamoney", "repo_fixing", "银行间 FR/FDR 回购定盘利率", RepoFixing, "date FR001 FR007 FR014 FDR001 FDR007 FDR014".split(), "rolling_FR_about_3y_FDR_about_1y_upstream_observation", "percent", 3600),
    ("pboc", "social_financing", "社会融资规模增量分项", SocialFinancing, SOCIAL_FIELDS, "2021_onwards_parser_support", "CNY_100million", 3600),
]
PARAMETER_MODELS = {(s, e): model for s, e, _, model, *_ in DEFINITIONS}
PUBLIC_ENDPOINTS = tuple(EndpointSpec(
    source_id=s, endpoint_key=e, title=title, acquisition_mode=MODE,
    resource_class="public_query", parser_name=f"{s}_{e}", parser_version="1",
    cache_ttl_seconds=ttl, request_contract=model.model_json_schema(),
    completeness_policy={"scope": "requested_page" if e == "investor_questions" else "source_response",
                         "full_history_verified": False, "calendar_completeness_verified": False},
    capabilities={"fields": fields, "units": units, "history_declared": history,
                  "history_verified": None, "point_in_time": False,
                  "adapter_ready": True, "permission": "public_endpoint",
                  "live_availability": "unverified", "failure_domain": s,
                  "fallback_equivalence": "not_asserted", "timezone": "Asia/Shanghai",
                  "business_timestamp_available": e not in ("option_contracts", "option_quote", "option_greeks"),
                  "timestamp_note": "fetch time is never a publication/trade time",
                  "conditional_fields": {"FR": ["FR001", "FR007", "FR014"], "FDR": ["FDR001", "FDR007", "FDR014"]} if e == "repo_fixing" else {}},
) for s, e, title, model, fields, history, units, ttl in DEFINITIONS)


def validate_public_request(source_id, endpoint_key, parameters):
    model = PARAMETER_MODELS.get((source_id, endpoint_key))
    if model is None:
        raise ValueError("not a public query endpoint")
    return model.model_validate(dict(parameters)).model_dump()
