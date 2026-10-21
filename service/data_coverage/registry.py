"""Coverage classification and audit rules for every public dataset."""

from collections.abc import Iterable
from datetime import date, time

from service.data_coverage.models import (
    CoverageRule,
    CoverageRuleNotFoundError,
    CoverageStrategy,
)
from service.data_service.models import DateStorage
from service.data_service.registry import DATASETS
from service.history_baselines import (
    CATALOG_WINDOW_HISTORY,
    ETF_SHARE_SIZE_HISTORY_START,
    FINANCIAL_ENTITY_REFERENCE_MAX_AGE_DAYS,
    UPSTREAM_HISTORY_STARTS,
)


class CoverageRuleRegistry:
    def __init__(self, rules: Iterable[CoverageRule]):
        by_name: dict[str, CoverageRule] = {}
        for rule in rules:
            if rule.dataset_name in by_name:
                raise ValueError(f"duplicate coverage rule: {rule.dataset_name}")
            dataset = DATASETS.get(rule.dataset_name)
            if (
                dataset.read_table != rule.table
                or dataset.date_column != rule.date_column
            ):
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
    collection_api_name: str | None = None,
    entity_column: str | None = "ts_code",
    grace_days: int = 1,
    release_after: time | None = None,
    release_on_next_trade_day: bool = False,
    default_lookback_days: int = 120,
    availability_start: date | None = None,
    description: str,
    entity_reference: str | None = None,
    min_entity_ratio: float | None = None,
    scheduled: bool = True,
    accept_verified_empty: bool = False,
    require_transport_proof: bool = False,
    verified_empty_min_age_days: int | None = None,
    revision: int = 1,
    entity_reference_max_age_days: int | None = None,
    calendar_exchange: str = "SSE",
    required_values: tuple[tuple[str, str], ...] = (),
) -> CoverageRule:
    dataset = DATASETS.get(dataset_name)
    if not dataset.date_column:
        raise ValueError(f"coverage dataset has no date column: {dataset_name}")
    return CoverageRule(
        dataset_name=dataset_name,
        table=dataset.read_table,
        date_column=dataset.date_column,
        date_storage=dataset.date_storage,
        strategy=strategy,
        collection_api_name=collection_api_name,
        entity_column=entity_column,
        grace_days=grace_days,
        release_after=release_after,
        release_on_next_trade_day=release_on_next_trade_day,
        default_lookback_days=default_lookback_days,
        availability_start=availability_start,
        description=description,
        entity_reference=entity_reference,
        min_entity_ratio=min_entity_ratio,
        scheduled=scheduled,
        accept_verified_empty=accept_verified_empty,
        require_transport_proof=require_transport_proof,
        verified_empty_min_age_days=verified_empty_min_age_days,
        revision=revision,
        entity_reference_max_age_days=entity_reference_max_age_days,
        calendar_exchange=calendar_exchange,
        required_values=required_values,
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
        table=dataset.read_table,
        date_column=dataset.date_column,
        date_storage=dataset.date_storage,
        strategy=strategy,
        collection_api_name=dataset_name,
        entity_column=(
            "ts_code"
            if "ts_code" in dataset.primary_keys or "ts_code" in dataset.exact_filters
            else None
        ),
        description=description,
        scheduled=False,
        # Sparse/event datasets are certified at their declared collection
        # scope. A single exhaustive range job can cover thousands of stored
        # event dates, so demanding one exact-date job per row date is a false
        # completeness failure.
        require_transport_proof=False,
    )


SSE_TRADING_DAILY_DATASETS = (
    "bak_daily",
    "cb_daily",
    "ci_daily",
    "daily_info",
    "dc_daily",
    "etf_share_size",
    "fund_adj",
    "fund_daily",
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

# ths_hot belongs to the current trade date, but its final snapshot can arrive
# after 22:30.  With zero base grace, release_after excludes today's partition
# until the 23:15 final patrol and includes yesterday immediately after
# midnight.  This differs intentionally from the T+1 datasets above.
SAME_DAY_RELEASE_DATASETS = {
    "ths_hot": time(23, 15),
}


_EXPLICIT_RULES = [
        _rule(
            "adj_factor",
            CoverageStrategy.TRADING_DAILY,
            collection_api_name="adj_factor",
            entity_column="ts_code",
            # An adjustment factor is required for every security that has a
            # daily bar on the same date.  Checking only that the date exists
            # allowed a nearly eight-year cross-sectional hole to look
            # complete as soon as one symbol was present.
            entity_reference="stock_daily",
            min_entity_ratio=1.0,
            availability_start=date(1991, 1, 3),
            revision=3,
            description=(
                "自上游可用边界起按 stock_daily 的生命周期有效日期审计（包含"
                "早期交易日历未标开的真实行情日），并要求当日实际成交证券"
                "全集一一覆盖；任一证券缺复权因子即判为部分"
            ),
        ),
        _rule(
            "technical_factor_snapshot",
            CoverageStrategy.TRADING_DAILY,
            collection_api_name=None,
            entity_reference="stock_basic",
            min_entity_ratio=1.0,
            # This is a forward-maintained research snapshot introduced with
            # the V2 derived workflow, not a historical price table.  The
            # chart/research APIs reproduce historical factors directly from
            # daily bars; manufacturing one persisted snapshot for every day
            # since 1990 would duplicate that data and turn pre-launch dates
            # into false coverage incidents.
            availability_start=date(2026, 10, 9),
            grace_days=1,
            default_lookback_days=120,
            scheduled=False,
            require_transport_proof=False,
            revision=2,
            description=(
                "自派生快照功能启用日开始，由 stock_daily 与 adj_factor 的同一"
                "交易日就绪状态触发；"
                "必须为当日上市股票全集写入一行，不可计算也必须记录明确原因"
            ),
        ),
        _rule(
            "fama_french_daily",
            CoverageStrategy.TRADING_DAILY,
            collection_api_name=None,
            entity_column=None,
            # A single market-level row per trading day, not one row per
            # security.  The universe is the whole cross-section, so there is
            # no entity reference to reconcile against.
            entity_reference=None,
            min_entity_ratio=None,
            # Historical reconstruction starts where the governed daily,
            # daily-basic and announcement-bounded balance-sheet inputs have
            # been verified together. Earlier dates remain outside this
            # contract rather than being silently marked complete.
            availability_start=date(2020, 1, 2),
            grace_days=1,
            default_lookback_days=120,
            scheduled=False,
            require_transport_proof=False,
            revision=3,
            required_values=(("formula_version", "ff3-sh-sz-v2"),),
            description=(
                "自2020年起回溯并前向维护，由 stock_daily、daily_basic 与 stock_st "
                "的同一交易日数据生成，按公告日读取当时可见财报，并严格核对日线与市值行；"
                "每个交易日写入一行 "
                "MKT/SMB/HML，横截面过薄时以 insufficient_universe 状态显式留空"
            ),
        ),
        _rule(
            "fund_share",
            CoverageStrategy.OBSERVED_ONLY,
            collection_api_name="fund_share",
            scheduled=False,
            require_transport_proof=False,
            revision=2,
            description=(
                "基金份额按不规则披露日发布；只审计已观察分区与有界请求的"
                "传输穷尽证据，不按每个 SSE 交易日虚构预期分区"
            ),
        ),
        _rule(
            "stock_daily",
            CoverageStrategy.TRADING_DAILY,
            collection_api_name="daily",
            entity_reference="stock_basic",
            min_entity_ratio=0.90,
            entity_reference_max_age_days=1825,
            revision=2,
            description=(
                "近五年按交易日及当期上市股票截面检查；更早历史无法从"
                "现存基础表还原停牌/分市场交易状态，按精确日期传输穷尽验证"
            ),
        ),
        _rule(
            "us_daily",
            CoverageStrategy.TRADING_DAILY,
            collection_api_name="us_daily",
            entity_column="ts_code",
            calendar_exchange="US",
            availability_start=date(1980, 1, 2),
            default_lookback_days=120,
            require_transport_proof=True,
            scheduled=False,
            revision=1,
            description=(
                "按独立的美股交易日历审计每个行情日期；完整状态必须同时具备"
                "物理数据和 us_daily 限频分页穷尽证据"
            ),
        ),
        _rule(
            "stock_daily_basic",
            CoverageStrategy.TRADING_DAILY,
            collection_api_name="daily_basic",
            entity_reference="stock_basic",
            min_entity_ratio=0.90,
            entity_reference_max_age_days=1825,
            revision=2,
            description=(
                "近五年按交易日及当期上市股票截面检查；更早历史无法从"
                "现存基础表还原停牌/分市场交易状态，按精确日期传输穷尽验证"
            ),
        ),
        _rule(
            "stock_limit",
            CoverageStrategy.TRADING_DAILY,
            collection_api_name="stk_limit",
            entity_reference="stock_basic",
            min_entity_ratio=0.90,
            availability_start=date(2007, 1, 4),
            description="按交易日及当期上市股票截面检查完整性；上游可靠历史始于 2007-01-04",
            revision=2,
        ),
        _rule(
            "moneyflow",
            CoverageStrategy.TRADING_DAILY,
            entity_reference="stock_basic",
            min_entity_ratio=0.85,
            availability_start=date(2007, 1, 4),
            entity_reference_max_age_days=1825,
            revision=3,
            description=(
                "自相邻探针确认的 2007-01-04 起，近五年按交易日及当期"
                "上市股票截面检查；更早历史使用"
                "精确日期传输穷尽证据，避免用当前股票全集制造假缺口"
            ),
        ),
        _rule(
            "index_daily",
            CoverageStrategy.TRADING_DAILY,
            entity_reference="index_daily_adjacent",
            # index_basic is a discovery catalogue, not the point-in-time
            # publication universe of index_daily.  It includes CNI series,
            # inactive series and categories that index_daily does not return,
            # and it has no delisting/status field.  Compare with nearby
            # observed index_daily cross-sections instead.  A missing 5,000-row
            # page still falls far below this floor.
            min_entity_ratio=0.85,
            description=(
                "按交易日及相邻已观测 index_daily 截面检查完整性；index_basic "
                "仅作发现目录且缺少失效日期，不能作为当日发布全集；申万行情由 "
                "sw_daily 独立采集"
            ),
            revision=5,
            entity_reference_max_age_days=120,
        ),
        _rule(
            "industry_daily",
            CoverageStrategy.TRADING_DAILY,
            entity_column=None,
            availability_start=date(2020, 1, 1),
            description=(
                "按交易日检查分区；ths_index 没有退市/失效字段，不能把全部历史指数"
                "误作当日活跃截面"
            ),
            revision=2,
        ),
        _rule(
            "margin",
            CoverageStrategy.TRADING_DAILY,
            entity_column="exchange_id",
            entity_reference="margin_exchanges",
            min_entity_ratio=1.0,
            grace_days=1,
            availability_start=date(2010, 3, 31),
            release_after=NEXT_MORNING_RELEASE_DATASETS["margin"],
            release_on_next_trade_day=True,
            description=(
                "自 2010-03-31 融资融券业务启动日起，按交易日检查"
                "当期已开展业务的交易所汇总是否全部发布"
            ),
            revision=4,
        ),
        _rule(
            "margin_detail",
            CoverageStrategy.TRADING_DAILY,
            entity_column="ts_code",
            entity_reference="margin_secs",
            min_entity_ratio=0.98,
            grace_days=1,
            availability_start=date(2010, 3, 31),
            release_after=NEXT_MORNING_RELEASE_DATASETS["margin_detail"],
            release_on_next_trade_day=True,
            description=(
                "自 2010-03-31 融资融券业务启动日起，按交易日及当日"
                "两融标的池识别交易所分批发布或截断"
            ),
            revision=4,
        ),
        _rule(
            "cyq_perf",
            CoverageStrategy.TRADING_DAILY,
            entity_column="ts_code",
            # A chip-distribution observation exists only for a security with
            # a market bar on that date. Using every lifecycle-listed symbol
            # as the denominator incorrectly classifies suspended/non-trading
            # securities as missing provider rows.
            entity_reference="stock_daily",
            min_entity_ratio=0.90,
            grace_days=1,
            default_lookback_days=365,
            availability_start=date(2018, 1, 1),
            scheduled=False,
            description=(
                "2018 年起按 SSE 交易日和当日实际有行情的证券截面审计筹码胜率；"
                "低于九成覆盖即判为部分采集，停牌及无成交证券不制造假缺口"
            ),
            revision=3,
        ),
        _rule(
            "fina_mainbz",
            CoverageStrategy.REPORT_QUARTERLY,
            collection_api_name="fina_mainbz",
            entity_column="ts_code",
            grace_days=0,
            default_lookback_days=1825,
            scheduled=False,
            accept_verified_empty=True,
            require_transport_proof=True,
            description=(
                "按已到披露期限的报告期审计主营行业/产品构成；稀疏季度"
                "必须由 VIP 全市场分页穷尽证书证明，不能以已有行数代替完整性"
            ),
            revision=2,
        ),
        _rule(
            "report_rc",
            CoverageStrategy.CALENDAR_DAILY,
            collection_api_name="report_rc",
            entity_column=None,
            grace_days=0,
            release_after=time(22, 30),
            default_lookback_days=365,
            availability_start=date(2010, 1, 1),
            scheduled=False,
            accept_verified_empty=True,
            require_transport_proof=True,
            description=(
                "2010 年起按自然日审计卖方研报；每日 19~22 点更新，"
                "有行或权威空结果都必须由精确 report_date 的分页穷尽证书证明"
            ),
            revision=2,
        ),
        _rule(
            "top10_holders",
            CoverageStrategy.REPORT_QUARTERLY,
            collection_api_name="top10_holders",
            entity_column="ts_code",
            grace_days=0,
            default_lookback_days=3650,
            availability_start=date(1990, 12, 31),
            scheduled=False,
            accept_verified_empty=True,
            require_transport_proof=True,
            description=(
                "按已到披露期限的报告期审计前十大股东；一个季度任务在"
                "采集节点内冻结当期上市股票全集并逐股穷尽，不能用已有行数代替"
            ),
            revision=2,
        ),
        _rule(
            "top10_floatholders",
            CoverageStrategy.REPORT_QUARTERLY,
            collection_api_name="top10_floatholders",
            entity_column="ts_code",
            grace_days=0,
            default_lookback_days=3650,
            availability_start=date(2003, 3, 31),
            scheduled=False,
            accept_verified_empty=True,
            require_transport_proof=True,
            description=(
                "按已到披露期限的报告期审计前十大流通股东；2003 年起"
                "由季度任务在采集节点内冻结股票全集并逐股穷尽"
            ),
            revision=2,
        ),
        _rule(
            "index_weekly",
            CoverageStrategy.TRADING_WEEKLY,
            grace_days=2,
            availability_start=date(1991, 7, 5),
            description="从相邻探针确认的首个指数周线周期开始检查完整交易周",
            revision=2,
        ),
        _rule(
            "index_monthly",
            CoverageStrategy.TRADING_MONTHLY,
            grace_days=2,
            default_lookback_days=730,
            availability_start=date(1991, 7, 31),
            description="从相邻探针确认的首个指数月线周期开始检查完整月份",
            revision=2,
        ),
        _rule(
            "ggt_monthly",
            CoverageStrategy.CALENDAR_MONTHLY,
            collection_api_name="ggt_monthly",
            entity_column=None,
            grace_days=2,
            default_lookback_days=5000,
            availability_start=date(2014, 11, 1),
            description="港股通开通后按自然月从 ggt_daily 有界派生",
            revision=2,
        ),
        _rule(
            "cn_gdp",
            CoverageStrategy.REPORT_QUARTERLY,
            entity_column=None,
            grace_days=0,
            default_lookback_days=3650,
            availability_start=date(1992, 3, 31),
            description=(
                "1992Q1 起按季度检查 GDP；更早上游仅提供年度 Q4 值，"
                "保留为观测数据而不制造季度缺口"
            ),
            revision=2,
        ),
        _rule(
            "cn_pmi",
            CoverageStrategy.CALENDAR_MONTHLY,
            entity_column=None,
            grace_days=3,
            default_lookback_days=3650,
            availability_start=date(2005, 1, 1),
            description="按自然月检查 PMI 历史；上游月度序列始于 2005-01",
            revision=2,
        ),
        *[
            _rule(
                dataset_name,
                CoverageStrategy.CALENDAR_MONTHLY,
                entity_column=None,
                grace_days=20,
                default_lookback_days=3650,
                availability_start=(
                    date(1993, 1, 1)
                    if dataset_name == "cn_ppi"
                    else date(2002, 1, 1)
                    if dataset_name == "sf_month"
                    else None
                ),
                description=(
                    "按自然月检查宏观历史；PPI 在 1993 年前仅有年度值，"
                    "社融月度序列始于 2002 年"
                    if dataset_name in {"cn_ppi", "sf_month"}
                    else "按自然月检查宏观历史，保留官方发布缓冲"
                ),
                revision=(2 if dataset_name in {"cn_ppi", "sf_month"} else 1),
            )
            for dataset_name in ("cn_cpi", "cn_m", "cn_ppi", "sf_month")
        ],
        *[
            _rule(
                dataset_name,
                CoverageStrategy.REPORT_QUARTERLY,
                collection_api_name=(
                    "fina_indicator"
                    if dataset_name == "financial_indicator"
                    else None
                ),
                entity_reference="stock_basic",
                min_entity_ratio=0.60,
                grace_days=0,
                default_lookback_days=730,
                # stock_basic describes listing history, not the historical
                # reporting universe retained by Tushare.  Very old reports
                # can be sparse or retroactively populated for companies that
                # listed later.  For those partitions, exhaustive offset
                # pagination plus persisted partition presence is the proof;
                # keep entity-ratio checks for recent research history.
                entity_reference_max_age_days=(
                    FINANCIAL_ENTITY_REFERENCE_MAX_AGE_DAYS
                ),
                accept_verified_empty=True,
                verified_empty_min_age_days=(
                    FINANCIAL_ENTITY_REFERENCE_MAX_AGE_DAYS
                ),
                revision=4,
                description=(
                    "近五年按披露截止日和上市公司截面检查；更早历史按"
                    "分页穷尽和报告期分区存在性检查"
                ),
            )
            for dataset_name in (
                "income",
                "balancesheet",
                "cashflow",
                "financial_indicator",
            )
        ],
        _rule(
            "forex_daily",
            CoverageStrategy.OBSERVED_ONLY,
            collection_api_name="fx_daily",
            description="无可靠外汇日历，仅列出实际存在日期",
        ),
        _rule("ccass_hold", CoverageStrategy.OBSERVED_ONLY, entity_column="ts_code", description="中央结算持股按香港交易日发布；当前仅审计已观测日期，避免用 SSE 日历制造假缺口"),
        _rule("ccass_hold_detail", CoverageStrategy.OBSERVED_ONLY, entity_column="ts_code", scheduled=False, description="单日超过百万行且需要显式范围；仅审计人工采集到的日期"),
        _rule(
            "cyq_chips",
            CoverageStrategy.TRADING_DAILY,
            entity_reference="stock_daily",
            min_entity_ratio=0.90,
            availability_start=date(2018, 1, 2),
            scheduled=False,
            revision=2,
            description=(
                "2018 年起按 SSE 交易日和当日实际有行情的证券截面审计筹码分布；"
                "该接口按股票展开，缺口只进入显式、额度评估后的批量修复"
            ),
        ),
        _rule(
            "cb_factor_pro",
            CoverageStrategy.TRADING_DAILY,
            entity_reference="cb_daily",
            min_entity_ratio=0.90,
            availability_start=date(2026, 8, 27),
            scheduled=True,
            revision=2,
            description="自治理采集启用日起按交易日及同日可转债行情截面检查",
        ),
        _rule(
            "fund_factor_pro",
            CoverageStrategy.TRADING_DAILY,
            entity_reference="fund_daily",
            min_entity_ratio=0.90,
            availability_start=date(2026, 8, 27),
            scheduled=True,
            revision=2,
            description="自治理采集启用日起按交易日及同日基金行情截面检查",
        ),
        _rule(
            "fut_index_daily",
            CoverageStrategy.TRADING_DAILY,
            entity_column="ts_code",
            availability_start=date(2026, 9, 4),
            scheduled=False,
            revision=2,
            description="自治理采集启用日起按 SSE 交易日检查南华商品指数日期分区",
        ),
        *[
            _rule(
                dataset_name,
                CoverageStrategy.TRADING_DAILY,
                entity_column="ts_code",
                availability_start=availability_start,
                scheduled=False,
                revision=2,
                description="自治理采集启用日起按 SSE 交易日检查每日分区；高扇出接口只允许显式修复",
            )
            for dataset_name, availability_start in (
                ("opt_daily", date(2026, 1, 14)),
                ("dc_index", date(2026, 8, 28)),
                ("etf_sh_cons", date(2026, 8, 27)),
                ("etf_sz_cons", date(2026, 8, 27)),
                ("moneyflow_dc", date(2026, 8, 28)),
            )
        ],
        _rule(
            "factor_value",
            CoverageStrategy.TRADING_DAILY,
            entity_column="factor_name",
            entity_reference="factor_catalog",
            min_entity_ratio=1.0,
            availability_start=date(2026, 8, 28),
            scheduled=False,
            revision=3,
            description=(
                "按 SSE 交易日检查完整受控因子集合；日期存在但缺少任一已知因子"
                "仍是部分分区，避免把额度中断后的半成品判为完整"
            ),
        ),
        _rule(
            "stock_st",
            CoverageStrategy.TRADING_DAILY,
            collection_api_name="stock_st",
            entity_column="ts_code",
            availability_start=date(2001, 1, 2),
            accept_verified_empty=True,
            scheduled=True,
            revision=3,
            description=(
                "按 SSE 交易日检查 ST 名单快照；有物理记录即可证明日期存在，"
                "零记录交易日必须有精确请求的权威空结果"
            ),
        ),
        _rule(
            "hk_daily",
            CoverageStrategy.TRADING_DAILY,
            entity_column="ts_code",
            calendar_exchange="HK",
            availability_start=date(2026, 9, 4),
            scheduled=True,
            revision=2,
            description="自治理采集启用日起使用独立港股交易日历检查日线分区",
        ),
        _rule(
            "hk_hold",
            CoverageStrategy.OBSERVED_ONLY,
            require_transport_proof=True,
            description=(
                "沪深港股通持股披露制度曾调整，不能用 SSE 日历反推"
                "历史日频缺口；每个已观察分区仍必须落在分页穷尽的 V2 请求范围内"
            ),
            revision=2,
        ),
        _rule("moneyflow_hsgt", CoverageStrategy.OBSERVED_ONLY, entity_column=None, description="沪深港通资金流混合多个市场日历，仅审计已观测日期"),
        _rule(
            "sge_daily",
            CoverageStrategy.TRADING_DAILY,
            entity_column=None,
            default_lookback_days=1825,
            availability_start=date(2002, 10, 31),
            accept_verified_empty=True,
            description=(
                "SGE 现货日行情以 SSE 开市日作为候选发布日历；"
                "SGE 独立休市日只有在 V2 对精确日期完成有界请求、"
                "分页穷尽并返回 0 行时，才认定为经验证为空"
            ),
            revision=4,
        ),
        _rule(
            "shibor",
            CoverageStrategy.TRADING_DAILY,
            entity_column=None,
            default_lookback_days=1095,
            availability_start=date(2006, 10, 8),
            description=(
                "从相邻探针确认的 2006-10-08 起按 SSE 开市日检查 "
                "SHIBOR 日度利率分区"
            ),
            revision=3,
        ),
        _rule(
            "cn_lpr",
            CoverageStrategy.CALENDAR_MONTHLY,
            collection_api_name="shibor_lpr",
            entity_column=None,
            grace_days=25,
            default_lookback_days=3650,
            availability_start=CATALOG_WINDOW_HISTORY["shibor_lpr"],
            description=(
                "按自然月检查 LPR 发布，物理发布日归一为月末分区；"
                "不对上游可靠历史起点之前制造缺口"
            ),
            revision=3,
        ),
        _rule(
            "repurchase",
            CoverageStrategy.CALENDAR_MONTHLY,
            entity_column=None,
            grace_days=0,
            default_lookback_days=5000,
            # Tushare's reliable repurchase history starts in 2015.  Asking
            # the monthly auditor to prove earlier partitions creates false
            # gaps even though the collector has exhausted the supported
            # upstream range.
            availability_start=date(2015, 1, 1),
            accept_verified_empty=True,
            require_transport_proof=True,
            description=(
                "稀疏回购事件按自然月审计；有数据不等于完整，"
                "必须同时存在覆盖整月且分页穷尽的传输证书"
            ),
            revision=3,
        ),
        _rule(
            "stock_suspend",
            CoverageStrategy.OBSERVED_ONLY,
            collection_api_name="suspend_d",
            description="事件型数据，仅列出实际发生日期",
        ),
        _rule(
            "trade_calendar",
            CoverageStrategy.OBSERVED_ONLY,
            collection_api_name="trade_cal",
            entity_column="exchange",
            description="日历本身只展示已保存日期，不反向推断缺口",
        ),
        *[
            _rule(
                dataset_name,
                CoverageStrategy.TRADING_DAILY,
                entity_column=None,
                grace_days=(
                    0 if dataset_name in SAME_DAY_RELEASE_DATASETS else 1
                ),
                release_after=(
                    SAME_DAY_RELEASE_DATASETS.get(dataset_name)
                    or NEXT_MORNING_RELEASE_DATASETS.get(dataset_name)
                ),
                release_on_next_trade_day=(
                    dataset_name in NEXT_MORNING_RELEASE_DATASETS
                ),
                entity_reference=(
                    "fund_daily"
                    if dataset_name == "fund_adj"
                    else "stock_daily"
                    if dataset_name in {"stk_factor", "stk_factor_pro"}
                    else None
                ),
                min_entity_ratio=(
                    0.90
                    if dataset_name in {"fund_adj", "stk_factor", "stk_factor_pro"}
                    else None
                ),
                description="按 SSE 交易日检查每日稳定发布的数据分区",
                # These interfaces have rare, provider-authoritative empty open
                # dates. They count only when an exact-date V2 execution
                # exhausted the upstream request and persisted a verified
                # empty completion certificate.
                accept_verified_empty=(
                    dataset_name in {
                        "bak_daily",
                        "cb_daily",
                        "etf_share_size",
                        "kpl_concept_cons",
                        "moneyflow_cnt_ths",
                        "moneyflow_ind_dc",
                        "moneyflow_ind_ths",
                        "moneyflow_ths",
                        "sz_daily_info",
                        "ths_hot",
                    }
                ),
                availability_start=(
                    ETF_SHARE_SIZE_HISTORY_START
                    if dataset_name == "etf_share_size"
                    else UPSTREAM_HISTORY_STARTS.get(dataset_name)
                ),
                revision=(
                    5
                    if dataset_name in {"fund_adj", "stk_factor", "stk_factor_pro"}
                    else 4
                    if dataset_name == "etf_share_size"
                    else 4
                    if dataset_name in {"moneyflow_ind_ths", "sz_daily_info"}
                    else 3
                    if dataset_name in {"bak_daily", "cb_daily"}
                    else 3
                    if dataset_name in {
                        "moneyflow_cnt_ths",
                        "moneyflow_ind_dc",
                        "moneyflow_ind_ths",
                        "moneyflow_ths",
                        "sz_daily_info",
                        "ths_hot",
                    }
                    else 2
                    if dataset_name in UPSTREAM_HISTORY_STARTS
                    else 1
                ),
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
