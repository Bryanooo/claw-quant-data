"""Coverage classification and audit rules for every public dataset."""

from collections.abc import Iterable
from datetime import time

from service.data_coverage.models import (
    CoverageRule,
    CoverageRuleNotFoundError,
    CoverageStrategy,
)
from service.data_service.models import DateStorage
from service.data_service.registry import DATASETS


class CoverageRuleRegistry:
    def __init__(self, rules: Iterable[CoverageRule]):
        by_name: dict[str, CoverageRule] = {}
        for rule in rules:
            if rule.dataset_name in by_name:
                raise ValueError(f"duplicate coverage rule: {rule.dataset_name}")
            dataset = DATASETS.get(rule.dataset_name)
            if dataset.table != rule.table or dataset.date_column != rule.date_column:
                raise ValueError(f"coverage rule disagrees with dataset: {rule.dataset_name}")
            by_name[rule.dataset_name] = rule
        self._rules = by_name

    def get(self, name: str) -> CoverageRule:
        try:
            return self._rules[name]
        except KeyError as exc:
            raise CoverageRuleNotFoundError(
                f"dataset does not support coverage auditing: {name}"
            ) from exc

    def list(self) -> tuple[CoverageRule, ...]:
        return tuple(sorted(self._rules.values(), key=lambda item: item.dataset_name))

    def scheduled(self) -> tuple[CoverageRule, ...]:
        return tuple(rule for rule in self.list() if rule.scheduled)


def _rule(
    dataset_name: str,
    strategy: CoverageStrategy,
    *,
    entity_column: str | None = "ts_code",
    grace_days: int = 1,
    release_after: time | None = None,
    default_lookback_days: int = 120,
    description: str,
    entity_reference: str | None = None,
    min_entity_ratio: float | None = None,
    scheduled: bool = True,
    accept_verified_empty: bool = False,
) -> CoverageRule:
    dataset = DATASETS.get(dataset_name)
    if not dataset.date_column:
        raise ValueError(f"coverage dataset has no date column: {dataset_name}")
    return CoverageRule(
        dataset_name=dataset_name,
        table=dataset.table,
        date_column=dataset.date_column,
        date_storage=dataset.date_storage,
        strategy=strategy,
        entity_column=entity_column,
        grace_days=grace_days,
        release_after=release_after,
        default_lookback_days=default_lookback_days,
        description=description,
        entity_reference=entity_reference,
        min_entity_ratio=min_entity_ratio,
        scheduled=scheduled,
        accept_verified_empty=accept_verified_empty,
    )


def _classified_rule(dataset_name: str) -> CoverageRule:
    dataset = DATASETS.get(dataset_name)
    if dataset.date_column:
        strategy = CoverageStrategy.OBSERVED_ONLY
        description = (
            "未配置可证明的预期日历；展示实际采集到的日期分区，不推断缺口"
        )
    else:
        strategy = CoverageStrategy.NON_TEMPORAL
        description = "数据没有日期分区，日期覆盖审计不适用"
    return CoverageRule(
        dataset_name=dataset.name,
        table=dataset.table,
        date_column=dataset.date_column,
        date_storage=dataset.date_storage,
        strategy=strategy,
        entity_column=(
            "ts_code"
            if "ts_code" in dataset.primary_keys or "ts_code" in dataset.exact_filters
            else None
        ),
        description=description,
        scheduled=False,
    )


SSE_TRADING_DAILY_DATASETS = (
    "adj_factor",
    "bak_daily",
    "cb_daily",
    "ci_daily",
    "daily_info",
    "dc_daily",
    "etf_share_size",
    "fund_adj",
    "fund_daily",
    "fund_share",
    "idx_factor_pro",
    "index_dailybasic",
    "kpl_concept_cons",
    "moneyflow_cnt_ths",
    "moneyflow_ind_dc",
    "moneyflow_ind_ths",
    "moneyflow_mkt_dc",
    "moneyflow_ths",
    "stk_auction",
    "stk_factor",
    "stk_factor_pro",
    "sw_daily",
    "sz_daily_info",
    "tdx_daily",
    "tdx_index",
    "ths_hot",
)

NEXT_MORNING_RELEASE_DATASETS = {
    # Tushare documents these partitions as next-morning publications; 09:15
    # includes the latest stated 09:05 release while retaining a small buffer.
    "etf_share_size": time(9, 15),
    "margin": time(9, 15),
    "margin_detail": time(9, 15),
}


_EXPLICIT_RULES = [
        _rule("stock_daily", CoverageStrategy.TRADING_DAILY, entity_reference="stock_basic", min_entity_ratio=0.90, description="按交易日及当期上市股票截面检查完整性"),
        _rule("stock_daily_basic", CoverageStrategy.TRADING_DAILY, entity_reference="stock_basic", min_entity_ratio=0.90, description="按交易日及当期上市股票截面检查完整性"),
        _rule("stock_limit", CoverageStrategy.TRADING_DAILY, entity_reference="stock_basic", min_entity_ratio=0.90, description="按交易日及当期上市股票截面检查完整性"),
        _rule("moneyflow", CoverageStrategy.TRADING_DAILY, entity_reference="stock_basic", min_entity_ratio=0.85, description="按交易日及当期上市股票截面检查完整性"),
        _rule(
            "index_daily",
            CoverageStrategy.TRADING_DAILY,
            entity_reference="index_basic",
            min_entity_ratio=0.90,
            description="按交易日及已上市指数基准截面检查全市场完整性",
        ),
        _rule(
            "industry_daily",
            CoverageStrategy.TRADING_DAILY,
            entity_column=None,
            description=(
                "按交易日检查分区；ths_index 没有退市/失效字段，不能把全部历史指数"
                "误作当日活跃截面"
            ),
        ),
        _rule(
            "margin",
            CoverageStrategy.TRADING_DAILY,
            entity_column="exchange_id",
            entity_reference="margin_exchanges",
            min_entity_ratio=1.0,
            release_after=NEXT_MORNING_RELEASE_DATASETS["margin"],
            description="按交易日检查沪深北三所汇总是否全部发布",
        ),
        _rule(
            "margin_detail",
            CoverageStrategy.TRADING_DAILY,
            entity_column="ts_code",
            entity_reference="margin_secs",
            min_entity_ratio=0.98,
            release_after=NEXT_MORNING_RELEASE_DATASETS["margin_detail"],
            description="按交易日及当日两融标的池识别交易所分批发布或截断",
        ),
        _rule("index_weekly", CoverageStrategy.TRADING_WEEKLY, grace_days=2, description="检查每个完整交易周；指数研究池尚未配置"),
        _rule("index_monthly", CoverageStrategy.TRADING_MONTHLY, grace_days=2, default_lookback_days=730, description="检查每个完整月份；指数研究池尚未配置"),
        _rule("income", CoverageStrategy.REPORT_QUARTERLY, entity_reference="stock_basic", min_entity_ratio=0.60, grace_days=0, default_lookback_days=730, description="按披露截止日和上市公司截面检查季度报告期"),
        _rule("balancesheet", CoverageStrategy.REPORT_QUARTERLY, entity_reference="stock_basic", min_entity_ratio=0.60, grace_days=0, default_lookback_days=730, description="按披露截止日和上市公司截面检查季度报告期"),
        _rule("cashflow", CoverageStrategy.REPORT_QUARTERLY, entity_reference="stock_basic", min_entity_ratio=0.60, grace_days=0, default_lookback_days=730, description="按披露截止日和上市公司截面检查季度报告期"),
        _rule("financial_indicator", CoverageStrategy.REPORT_QUARTERLY, entity_reference="stock_basic", min_entity_ratio=0.60, grace_days=0, default_lookback_days=730, description="按披露截止日和上市公司截面检查季度报告期"),
        _rule("forex_daily", CoverageStrategy.OBSERVED_ONLY, description="无可靠外汇日历，仅列出实际存在日期"),
        _rule("ccass_hold", CoverageStrategy.OBSERVED_ONLY, entity_column="ts_code", description="中央结算持股按香港交易日发布；当前仅审计已观测日期，避免用 SSE 日历制造假缺口"),
        _rule("ccass_hold_detail", CoverageStrategy.OBSERVED_ONLY, entity_column="ts_code", scheduled=False, description="单日超过百万行且需要显式范围；仅审计人工采集到的日期"),
        _rule("fut_index_daily", CoverageStrategy.OBSERVED_ONLY, description="南华商品指数缺少独立且完整的本地发布日历，仅审计静态指数全集的已观测日期"),
        _rule("hk_daily", CoverageStrategy.OBSERVED_ONLY, description="港股日线使用独立港股交易日历且接口限频一小时；仅审计已观测日期"),
        _rule("hk_hold", CoverageStrategy.OBSERVED_ONLY, description="沪深港股通持股披露制度曾调整，不能用 SSE 日历反推历史日频缺口"),
        _rule("moneyflow_hsgt", CoverageStrategy.OBSERVED_ONLY, entity_column=None, description="沪深港通资金流混合多个市场日历，仅审计已观测日期"),
        _rule("sge_daily", CoverageStrategy.OBSERVED_ONLY, description="无独立 SGE 日历，仅列出实际存在日期"),
        _rule("stock_suspend", CoverageStrategy.OBSERVED_ONLY, description="事件型数据，仅列出实际发生日期"),
        _rule("trade_calendar", CoverageStrategy.OBSERVED_ONLY, entity_column="exchange", description="日历本身只展示已保存日期，不反向推断缺口"),
        *[
            _rule(
                dataset_name,
                CoverageStrategy.TRADING_DAILY,
                entity_column=None,
                release_after=NEXT_MORNING_RELEASE_DATASETS.get(dataset_name),
                description="按 SSE 交易日检查每日稳定发布的数据分区",
                accept_verified_empty=(dataset_name == "kpl_concept_cons"),
            )
            for dataset_name in SSE_TRADING_DAILY_DATASETS
        ],
]
_EXPLICIT_NAMES = {rule.dataset_name for rule in _EXPLICIT_RULES}

COVERAGE_RULES = CoverageRuleRegistry(
    [
        *_EXPLICIT_RULES,
        *(
            _classified_rule(dataset.name)
            for dataset in DATASETS.list()
            if dataset.name not in _EXPLICIT_NAMES
        ),
    ]
)
