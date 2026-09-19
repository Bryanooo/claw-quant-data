"""Deterministic research calculations over governed standard datasets."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from math import sqrt
from statistics import mean, median, pstdev
from typing import Any, Iterable

from service.data_service.models import InvalidQueryError, RecordNotFoundError
from service.clock import business_now
from service.research.catalog import capability_catalog


def _number(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_div(numerator: Any, denominator: Any) -> float | None:
    top = _number(numerator)
    bottom = _number(denominator)
    if top is None or bottom in (None, 0):
        return None
    return top / bottom


def _pct_change(current: Any, previous: Any) -> float | None:
    ratio = _safe_div(current, previous)
    return None if ratio is None else (ratio - 1) * 100


def _round(value: float | None, digits: int = 4) -> float | None:
    return None if value is None else round(value, digits)


def _day(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value or "").strip()
    if not text:
        return None
    try:
        if len(text) >= 10 and text[4] == "-":
            return date.fromisoformat(text[:10])
        if len(text) >= 8 and text[:8].isdigit():
            return date(int(text[:4]), int(text[4:6]), int(text[6:8]))
    except ValueError:
        return None
    return None


def _percentile_rank(values: Iterable[Any], current: Any) -> float | None:
    clean = sorted(value for value in (_number(item) for item in values) if value is not None)
    target = _number(current)
    if not clean or target is None:
        return None
    below = sum(value < target for value in clean)
    equal = sum(value == target for value in clean)
    return round((below + equal * 0.5) / len(clean) * 100, 2)


def _moving_average(values: list[float], window: int) -> float | None:
    if len(values) < window:
        return None
    return mean(values[-window:])


def _ema_series(values: list[float], window: int) -> list[float]:
    if not values:
        return []
    alpha = 2 / (window + 1)
    output = [values[0]]
    for value in values[1:]:
        output.append(alpha * value + (1 - alpha) * output[-1])
    return output


def _rsi(values: list[float], window: int = 14) -> float | None:
    if len(values) <= window:
        return None
    changes = [right - left for left, right in zip(values[-window - 1:-1], values[-window:])]
    gains = sum(max(change, 0) for change in changes) / window
    losses = sum(max(-change, 0) for change in changes) / window
    if losses == 0:
        return 100.0 if gains > 0 else 50.0
    return 100 - 100 / (1 + gains / losses)


def _max_drawdown(values: list[float]) -> float | None:
    if not values:
        return None
    peak = values[0]
    worst = 0.0
    for value in values:
        peak = max(peak, value)
        if peak:
            worst = min(worst, value / peak - 1)
    return worst * 100


def _prior_year(value: date) -> date:
    """Return the same reporting date a year earlier, including leap days."""
    try:
        return value.replace(year=value.year - 1)
    except ValueError:
        return value.replace(year=value.year - 1, day=28)


class ResearchService:
    """High-level calculations whose formulas remain stable across clients."""

    def __init__(self, data_service, repository):
        self._data = data_service
        self._repository = repository

    def capabilities(self) -> dict[str, Any]:
        return capability_catalog(self._repository.backfill_statuses())

    def _load(
        self,
        name: str,
        *,
        filters: dict[str, str] | None = None,
        start: date | None = None,
        end: date | None = None,
        as_of: date | None = None,
        limit: int = 1000,
    ) -> list[dict]:
        return self._data.query_dataset(
            name,
            exact_filters=filters or {},
            date_value=None,
            start_date=start.isoformat() if start else None,
            end_date=end.isoformat() if end else None,
            as_of=as_of.isoformat() if as_of else None,
            limit=limit,
            offset=0,
            include_total=False,
        )["data"]

    def _ensure_stock(self, ts_code: str) -> dict:
        rows = self._load("stock_basic", filters={"ts_code": ts_code}, limit=1)
        if not rows:
            raise RecordNotFoundError(f"stock not found: {ts_code}")
        return rows[0]

    @staticmethod
    def _latest_by_date(rows: list[dict], column: str) -> dict[str, dict]:
        selected: dict[str, dict] = {}
        for row in rows:
            observed = _day(row.get(column))
            if observed is None:
                continue
            selected.setdefault(observed.isoformat(), row)
        return selected

    @staticmethod
    def _provenance(data: dict[str, list[dict]]) -> list[dict]:
        return [
            {"dataset": name, "returned": len(rows), "state": "available" if rows else "missing"}
            for name, rows in data.items()
        ]

    def fundamentals(
        self,
        ts_code: str,
        *,
        periods: int = 12,
        as_of: date | None = None,
    ) -> dict[str, Any]:
        effective_as_of = as_of or business_now().date()
        basic = self._ensure_stock(ts_code)
        loaded = {
            "financial_indicator": self._load(
                "financial_indicator", filters={"ts_code": ts_code},
                end=effective_as_of, as_of=effective_as_of, limit=min(periods * 4, 48),
            ),
            "income": self._load(
                "income", filters={"ts_code": ts_code}, end=effective_as_of,
                as_of=effective_as_of, limit=min(periods * 4, 48),
            ),
            "balancesheet": self._load(
                "balancesheet", filters={"ts_code": ts_code}, end=effective_as_of,
                as_of=effective_as_of, limit=min(periods * 4, 48),
            ),
            "cashflow": self._load(
                "cashflow", filters={"ts_code": ts_code}, end=effective_as_of,
                as_of=effective_as_of, limit=min(periods * 4, 48),
            ),
            "fina_mainbz": self._load(
                "fina_mainbz", filters={"ts_code": ts_code}, end=effective_as_of,
                limit=1000,
            ),
        }
        indicators = self._latest_by_date(loaded["financial_indicator"], "end_date")
        incomes = self._latest_by_date(loaded["income"], "end_date")
        balances = self._latest_by_date(loaded["balancesheet"], "end_date")
        cashflows = self._latest_by_date(loaded["cashflow"], "end_date")
        dates = sorted(set(indicators) | set(incomes) | set(balances) | set(cashflows))[-periods:]
        series: list[dict[str, Any]] = []
        for observed in dates:
            indicator = indicators.get(observed, {})
            income = incomes.get(observed, {})
            balance = balances.get(observed, {})
            cashflow = cashflows.get(observed, {})
            prior_day = _prior_year(date.fromisoformat(observed)).isoformat()
            prior_income = incomes.get(prior_day, {})
            prior_cashflow = cashflows.get(prior_day, {})
            equity = balance.get("total_hldr_eqy_inc_min_int")
            equity_multiplier = _safe_div(balance.get("total_assets"), equity)
            net_margin = _number(indicator.get("netprofit_margin"))
            asset_turnover = _number(indicator.get("assets_turn"))
            dupont_roe = (
                net_margin / 100 * asset_turnover * equity_multiplier * 100
                if None not in (net_margin, asset_turnover, equity_multiplier)
                else None
            )
            series.append(
                {
                    "period": observed,
                    "announced_at": max(
                        (value for value in (
                            _day(indicator.get("ann_date")), _day(income.get("ann_date")),
                            _day(balance.get("ann_date")), _day(cashflow.get("ann_date")),
                        ) if value is not None),
                        default=None,
                    ),
                    "profitability": {
                        "gross_margin_pct": _number(indicator.get("grossprofit_margin")),
                        "net_margin_pct": net_margin,
                        "roe_pct": _number(indicator.get("roe")),
                        "roa_pct": _number(indicator.get("roa")),
                        "roic_pct": _number(indicator.get("roic")),
                    },
                    "growth": {
                        "revenue_yoy_pct": _round(_pct_change(income.get("revenue"), prior_income.get("revenue"))),
                        "net_income_yoy_pct": _round(_pct_change(income.get("n_income_attr_p"), prior_income.get("n_income_attr_p"))),
                        "operating_cashflow_yoy_pct": _round(_pct_change(cashflow.get("n_cashflow_act"), prior_cashflow.get("n_cashflow_act"))),
                    },
                    "quality": {
                        "operating_cash_to_net_income": _round(_safe_div(cashflow.get("n_cashflow_act"), income.get("n_income_attr_p"))),
                        "sales_cash_to_revenue": _round(_safe_div(cashflow.get("c_fr_sale_sg"), income.get("revenue"))),
                        "accrual_to_assets": _round(
                            _safe_div(
                                net_income - operating_cashflow,
                                balance.get("total_assets"),
                            )
                            if (
                                (net_income := _number(income.get("n_income_attr_p")))
                                is not None
                                and (
                                    operating_cashflow := _number(
                                        cashflow.get("n_cashflow_act")
                                    )
                                )
                                is not None
                            )
                            else None
                        ),
                        "free_cashflow": _number(cashflow.get("free_cashflow") or indicator.get("fcff")),
                    },
                    "solvency": {
                        "current_ratio": _number(indicator.get("current_ratio")),
                        "quick_ratio": _number(indicator.get("quick_ratio")),
                        "debt_to_assets_pct": _number(indicator.get("debt_to_assets")),
                        "interest_coverage": _number(indicator.get("ebit_to_interest")),
                    },
                    "efficiency": {
                        "receivables_turnover": _number(indicator.get("ar_turn")),
                        "inventory_turnover": _number(indicator.get("inv_turn")),
                        "asset_turnover": asset_turnover,
                        "turnover_days": _number(indicator.get("turn_days")),
                    },
                    "dupont": {
                        "net_margin_pct": net_margin,
                        "asset_turnover": asset_turnover,
                        "equity_multiplier": _round(equity_multiplier),
                        "derived_roe_pct": _round(dupont_roe),
                        "reported_roe_pct": _number(indicator.get("roe")),
                    },
                }
            )

        segment_rows = loaded["fina_mainbz"]
        latest_segment_period = max(
            (
                observed
                for row in segment_rows
                if (observed := _day(row.get("end_date"))) is not None
            ),
            default=None,
        )
        latest_segments = [
            row for row in segment_rows if _day(row.get("end_date")) == latest_segment_period
        ]
        latest_segments.sort(key=lambda row: _number(row.get("bz_sales")) or 0, reverse=True)
        total_segment_sales = sum(_number(row.get("bz_sales")) or 0 for row in latest_segments)
        segments = [
            {
                "item": row.get("bz_item"),
                "code": row.get("bz_code"),
                "sales": _number(row.get("bz_sales")),
                "profit": _number(row.get("bz_profit")),
                "cost": _number(row.get("bz_cost")),
                "sales_share_pct": _round(
                    (_number(row.get("bz_sales")) or 0) / total_segment_sales * 100
                    if total_segment_sales else None
                ),
            }
            for row in latest_segments[:20]
        ]
        missing = [item["dataset"] for item in self._provenance(loaded) if item["state"] == "missing"]
        historical_view = effective_as_of < business_now().date()
        return {
            "data": {
                "profile": basic,
                "periods": series,
                "latest": series[-1] if series else None,
                "segments": {"period": latest_segment_period, "items": segments},
            },
            "meta": {
                "ts_code": ts_code,
                "as_of": effective_as_of,
                "generated_at": datetime.now(timezone.utc),
                "methodology": {
                    "growth": "same fiscal period one year earlier",
                    "dupont": "net margin × asset turnover × equity multiplier",
                    "segment_share": "share of latest returned segment sales",
                },
                "provenance": self._provenance(loaded),
                "quality": {
                    "status": "warning" if missing or historical_view else "ready",
                    "missing_datasets": missing,
                    "point_in_time_safe": not historical_view,
                    "warnings": ([
                        "fina_mainbz has no announcement-date contract; segment data is current-only in historical views"
                    ] if historical_view else []),
                },
            },
        }

    def valuation(
        self,
        ts_code: str,
        *,
        lookback_days: int = 730,
        peer_limit: int = 20,
        as_of: date | None = None,
    ) -> dict[str, Any]:
        effective_as_of = as_of or business_now().date()
        self._ensure_stock(ts_code)
        start = effective_as_of - timedelta(days=lookback_days - 1)
        valuations = self._load(
            "stock_daily_basic", filters={"ts_code": ts_code}, start=start,
            end=effective_as_of, as_of=effective_as_of, limit=min(lookback_days, 1000),
        )
        valuations.sort(key=lambda row: _day(row.get("trade_date")) or date.min)
        indicators = self._load(
            "financial_indicator", filters={"ts_code": ts_code}, end=effective_as_of,
            as_of=effective_as_of, limit=8,
        )
        latest = valuations[-1] if valuations else None
        metrics: dict[str, Any] = {}
        for field in ("pe", "pe_ttm", "pb", "ps", "ps_ttm", "dv_ratio", "dv_ttm"):
            current = latest.get(field) if latest else None
            history = [row.get(field) for row in valuations if _number(row.get(field)) is not None]
            if field.startswith("pe"):
                history = [value for value in history if (_number(value) or 0) > 0]
            metrics[field] = {
                "value": _number(current),
                "history_percentile": _percentile_rank(history, current),
                "history_low": min((_number(value) for value in history), default=None),
                "history_high": max((_number(value) for value in history), default=None),
                "observations": len(history),
            }

        peers = (
            self._data.stock_peers(
                ts_code,
                provider=None,
                as_of=effective_as_of,
                max_sectors=3,
                limit=peer_limit,
            ).get("data", [])
            if peer_limit
            else []
        )
        peer_rows: list[dict[str, Any]] = []
        for peer in peers[:peer_limit]:
            peer_code = peer.get("ts_code")
            if not peer_code or peer_code == ts_code:
                continue
            rows = self._load(
                "stock_daily_basic", filters={"ts_code": peer_code},
                end=effective_as_of, as_of=effective_as_of, limit=1,
            )
            if rows:
                peer_rows.append({
                    "ts_code": peer_code,
                    "shared_sector_count": peer.get("shared_sector_count"),
                    "trade_date": rows[0].get("trade_date"),
                    "pe_ttm": _number(rows[0].get("pe_ttm")),
                    "pb": _number(rows[0].get("pb")),
                    "ps_ttm": _number(rows[0].get("ps_ttm")),
                })
        latest_indicator = indicators[0] if indicators else {}
        peer_medians = {
            field: _round(median(values)) if (values := [
                row[field] for row in peer_rows if row.get(field) is not None
            ]) else None
            for field in ("pe_ttm", "pb", "ps_ttm")
        }
        return {
            "data": {
                "latest": latest,
                "historical_distribution": metrics,
                "peers": {"items": peer_rows, "medians": peer_medians},
                "intrinsic_value_inputs": {
                    "fcff": _number(latest_indicator.get("fcff")),
                    "fcfe": _number(latest_indicator.get("fcfe")),
                    "roe_pct": _number(latest_indicator.get("roe")),
                    "roic_pct": _number(latest_indicator.get("roic")),
                    "dividend_yield_ttm_pct": _number(latest.get("dv_ttm")) if latest else None,
                    "fair_value": None,
                    "required_assumptions": ["forecast horizon", "terminal growth", "discount rate"],
                },
            },
            "meta": {
                "ts_code": ts_code,
                "as_of": effective_as_of,
                "lookback_days": lookback_days,
                "generated_at": datetime.now(timezone.utc),
                "provenance": [
                    {"dataset": "stock_daily_basic", "returned": len(valuations)},
                    {"dataset": "financial_indicator", "returned": len(indicators)},
                    {"dataset": "stock peers", "returned": len(peer_rows)},
                ],
                "quality": {
                    "status": "ready" if latest else "warning",
                    "warnings": [] if latest else ["no valuation observations in requested window"],
                },
            },
        }

    def technicals(
        self,
        ts_code: str,
        *,
        lookback_days: int = 400,
        benchmark: str = "399006.SZ",
        as_of: date | None = None,
    ) -> dict[str, Any]:
        effective_as_of = as_of or business_now().date()
        self._ensure_stock(ts_code)
        start = effective_as_of - timedelta(days=max(lookback_days * 2, 500))
        prices = self._load(
            "stock_daily", filters={"ts_code": ts_code}, start=start,
            end=effective_as_of, as_of=effective_as_of, limit=min(lookback_days, 1000),
        )
        benchmark_rows = self._load(
            "index_daily", filters={"ts_code": benchmark}, start=start,
            end=effective_as_of, as_of=effective_as_of, limit=min(lookback_days, 1000),
        )
        adjustments = self._load(
            "adj_factor", filters={"ts_code": ts_code}, start=start,
            end=effective_as_of, limit=min(lookback_days, 1000),
        )
        prices.sort(key=lambda row: _day(row.get("trade_date")) or date.min)
        benchmark_rows.sort(key=lambda row: _day(row.get("trade_date")) or date.min)
        factor_by_day = {
            _day(row.get("trade_date")): _number(row.get("adj_factor"))
            for row in adjustments if _day(row.get("trade_date"))
        }
        closes = [_number(row.get("close")) for row in prices]
        closes = [value for value in closes if value is not None]
        highs = [_number(row.get("high")) for row in prices]
        lows = [_number(row.get("low")) for row in prices]
        volumes = [_number(row.get("vol")) or 0 for row in prices]
        if not closes:
            raise RecordNotFoundError(f"no daily prices found for {ts_code}")

        ema12 = _ema_series(closes, 12)
        ema26 = _ema_series(closes, 26)
        macd_line = [left - right for left, right in zip(ema12, ema26)]
        signal_line = _ema_series(macd_line, 9)
        true_ranges: list[float] = []
        for index, row in enumerate(prices):
            high = _number(row.get("high"))
            low = _number(row.get("low"))
            previous = _number(prices[index - 1].get("close")) if index else None
            if high is None or low is None:
                continue
            true_ranges.append(max(high - low, abs(high - previous) if previous else 0, abs(low - previous) if previous else 0))
        returns = [
            current / previous - 1
            for previous, current in zip(closes[:-1], closes[1:]) if previous
        ]
        latest_close = closes[-1]
        ma = {str(window): _round(_moving_average(closes, window)) for window in (5, 10, 20, 60, 120, 250)}
        window20 = closes[-20:] if len(closes) >= 20 else closes
        boll_mid = mean(window20) if window20 else None
        boll_std = pstdev(window20) if len(window20) > 1 else None
        momentum = {
            f"return_{window}d_pct": _round(_pct_change(latest_close, closes[-window - 1]) if len(closes) > window else None)
            for window in (20, 60, 120, 250)
        }
        benchmark_by_day = {
            _day(row.get("trade_date")): _number(row.get("close"))
            for row in benchmark_rows if _day(row.get("trade_date")) and _number(row.get("close")) is not None
        }
        stock_by_day = {
            _day(row.get("trade_date")): _number(row.get("close"))
            for row in prices if _day(row.get("trade_date")) and _number(row.get("close")) is not None
        }
        common_days = sorted(set(stock_by_day) & set(benchmark_by_day))
        relative: dict[str, float | None] = {}
        for window in (20, 60, 120):
            if len(common_days) > window:
                first, last = common_days[-window - 1], common_days[-1]
                stock_return = _pct_change(stock_by_day[last], stock_by_day[first])
                benchmark_return = _pct_change(benchmark_by_day[last], benchmark_by_day[first])
                relative[f"excess_return_{window}d_pct"] = _round(
                    stock_return - benchmark_return
                    if stock_return is not None and benchmark_return is not None else None
                )
            else:
                relative[f"excess_return_{window}d_pct"] = None

        adjusted_closes: list[float] = []
        latest_factor = factor_by_day.get(_day(prices[-1].get("trade_date")))
        if latest_factor:
            for row in prices:
                close = _number(row.get("close"))
                factor = factor_by_day.get(_day(row.get("trade_date")))
                if close is not None and factor is not None:
                    adjusted_closes.append(close * factor / latest_factor)
        volume_5 = mean(volumes[-5:]) if len(volumes) >= 5 else None
        volume_20 = mean(volumes[-20:]) if len(volumes) >= 20 else None
        trend_score = sum(
            latest_close > value for value in (ma["20"], ma["60"], ma["120"]) if value is not None
        )
        latest_rsi = _rsi(closes)
        return {
            "data": {
                "observation": {"trade_date": prices[-1].get("trade_date"), "close": latest_close},
                "trend": {
                    "moving_averages": ma,
                    "ema_12": _round(ema12[-1]),
                    "ema_26": _round(ema26[-1]),
                    "macd": _round(macd_line[-1]),
                    "macd_signal": _round(signal_line[-1]),
                    "regime": "bullish" if trend_score == 3 else "bearish" if trend_score == 0 else "mixed",
                },
                "momentum": {**momentum, "rsi_14": _round(latest_rsi)},
                "volatility": {
                    "atr_14": _round(mean(true_ranges[-14:]) if len(true_ranges) >= 14 else None),
                    "annualized_volatility_20d_pct": _round(pstdev(returns[-20:]) * sqrt(252) * 100 if len(returns) >= 20 else None),
                    "bollinger_20": {
                        "lower": _round(boll_mid - 2 * boll_std if boll_mid is not None and boll_std is not None else None),
                        "middle": _round(boll_mid),
                        "upper": _round(boll_mid + 2 * boll_std if boll_mid is not None and boll_std is not None else None),
                    },
                    "max_drawdown_pct": _round(_max_drawdown(closes)),
                },
                "volume_price": {
                    "volume_5d_average": _round(volume_5),
                    "volume_20d_average": _round(volume_20),
                    "volume_5_to_20_ratio": _round(_safe_div(volume_5, volume_20)),
                },
                "levels": {
                    f"high_{window}d": _round(max(value for value in highs[-window:] if value is not None)) if len(highs) >= window else None
                    for window in (20, 60, 250)
                } | {
                    f"low_{window}d": _round(min(value for value in lows[-window:] if value is not None)) if len(lows) >= window else None
                    for window in (20, 60, 250)
                },
                "relative_strength": {"benchmark": benchmark, **relative},
                "total_return": {
                    "adjusted_observations": len(adjusted_closes),
                    "adjusted_return_pct": _round(_pct_change(adjusted_closes[-1], adjusted_closes[0])) if len(adjusted_closes) > 1 else None,
                },
            },
            "meta": {
                "ts_code": ts_code,
                "as_of": effective_as_of,
                "benchmark": benchmark,
                "generated_at": datetime.now(timezone.utc),
                "provenance": [
                    {"dataset": "stock_daily", "returned": len(prices)},
                    {"dataset": "index_daily", "returned": len(benchmark_rows)},
                    {"dataset": "adj_factor", "returned": len(adjustments)},
                ],
                "quality": {
                    "status": "ready" if len(prices) >= 250 else "warning",
                    "warnings": [] if len(prices) >= 250 else ["fewer than 250 daily observations"],
                },
            },
        }

    def capital_flow(
        self,
        ts_code: str,
        *,
        lookback_days: int = 60,
        as_of: date | None = None,
    ) -> dict[str, Any]:
        effective_as_of = as_of or business_now().date()
        self._ensure_stock(ts_code)
        start = effective_as_of - timedelta(days=lookback_days * 2)
        loaded = {
            "moneyflow": self._load("moneyflow", filters={"ts_code": ts_code}, start=start, end=effective_as_of, limit=lookback_days),
            "margin_detail": self._load("margin_detail", filters={"ts_code": ts_code}, start=start, end=effective_as_of, limit=lookback_days),
            "hk_hold": self._load("hk_hold", filters={"ts_code": ts_code}, start=start, end=effective_as_of, limit=lookback_days),
            "block_trade": self._load("block_trade", filters={"ts_code": ts_code}, start=start, end=effective_as_of, limit=500),
            "cyq_perf": self._load("cyq_perf", filters={"ts_code": ts_code}, start=start, end=effective_as_of, limit=lookback_days),
        }
        money = loaded["moneyflow"]
        net_amounts = [_number(row.get("net_mf_amount")) for row in money]
        clean_net = [value for value in net_amounts if value is not None]
        margin = loaded["margin_detail"]
        northbound = loaded["hk_hold"]
        blocks = loaded["block_trade"]
        chips = loaded["cyq_perf"]
        return {
            "data": {
                "moneyflow": {
                    "observations": len(clean_net),
                    "net_amount_sum": _round(sum(clean_net)) if clean_net else None,
                    "net_amount_average": _round(mean(clean_net)) if clean_net else None,
                    "positive_days": sum(value > 0 for value in clean_net),
                    "latest": money[0] if money else None,
                },
                "margin": {
                    "observations": len(margin),
                    "latest": margin[0] if margin else None,
                    "financing_buy_sum": _round(sum(_number(row.get("rzmre")) or 0 for row in margin)) if margin else None,
                    "financing_repay_sum": _round(sum(_number(row.get("rzche")) or 0 for row in margin)) if margin else None,
                },
                "northbound": {"observations": len(northbound), "latest": northbound[0] if northbound else None},
                "block_trades": {
                    "count": len(blocks),
                    "amount_sum": _round(sum(_number(row.get("amount")) or 0 for row in blocks)),
                    "latest": blocks[0] if blocks else None,
                },
                "chips": {"observations": len(chips), "latest": chips[0] if chips else None},
            },
            "meta": {
                "ts_code": ts_code,
                "as_of": effective_as_of,
                "lookback_days": lookback_days,
                "generated_at": datetime.now(timezone.utc),
                "provenance": self._provenance(loaded),
                "quality": {
                    "status": "warning" if not money else "ready",
                    "warnings": [
                        "event-like sources can legitimately be empty; absence is not treated as zero"
                    ],
                },
            },
        }

    def event_study(
        self,
        ts_code: str,
        *,
        event_date: date,
        pre_days: int = 5,
        post_days: int = 10,
        benchmark: str = "399006.SZ",
    ) -> dict[str, Any]:
        self._ensure_stock(ts_code)
        padding = max((pre_days + post_days) * 3, 30)
        start, end = event_date - timedelta(days=padding), event_date + timedelta(days=padding)
        stock_rows = self._load("stock_daily", filters={"ts_code": ts_code}, start=start, end=end, limit=200)
        benchmark_rows = self._load("index_daily", filters={"ts_code": benchmark}, start=start, end=end, limit=200)
        stock = {_day(row.get("trade_date")): row for row in stock_rows if _day(row.get("trade_date"))}
        index = {_day(row.get("trade_date")): row for row in benchmark_rows if _day(row.get("trade_date"))}
        common = sorted(set(stock) & set(index))
        anchor_candidates = [observed for observed in common if observed >= event_date]
        if not anchor_candidates:
            raise RecordNotFoundError("no trading observation on or after event_date")
        anchor = anchor_candidates[0]
        anchor_index = common.index(anchor)
        selected = common[max(0, anchor_index - pre_days):anchor_index + post_days + 1]
        observations = []
        car = 0.0
        for observed in selected:
            stock_return = _number(stock[observed].get("pct_chg"))
            benchmark_return = _number(index[observed].get("pct_chg"))
            abnormal = (
                stock_return - benchmark_return
                if stock_return is not None and benchmark_return is not None else None
            )
            if abnormal is not None:
                car += abnormal
            observations.append({
                "relative_day": common.index(observed) - anchor_index,
                "trade_date": observed,
                "stock_return_pct": stock_return,
                "benchmark_return_pct": benchmark_return,
                "abnormal_return_pct": _round(abnormal),
                "cumulative_abnormal_return_pct": _round(car),
            })
        return {
            "data": {"event_trade_date": anchor, "observations": observations, "car_pct": _round(car)},
            "meta": {
                "ts_code": ts_code,
                "event_date": event_date,
                "benchmark": benchmark,
                "pre_days": pre_days,
                "post_days": post_days,
                "methodology": "market-adjusted return: stock daily return minus benchmark daily return",
                "generated_at": datetime.now(timezone.utc),
                "quality": {"status": "ready" if len(observations) == pre_days + post_days + 1 else "warning"},
            },
        }

    def market_breadth(self, *, as_of: date | None = None) -> dict[str, Any]:
        effective_as_of = as_of or business_now().date()
        row = self._repository.market_breadth(effective_as_of)
        if not row:
            raise RecordNotFoundError("no market breadth observation found")
        securities = int(row.get("securities") or 0)
        advancing = int(row.get("advancing") or 0)
        declining = int(row.get("declining") or 0)
        normalized = {
            **row,
            "securities": securities,
            "advancing": advancing,
            "declining": declining,
            "unchanged": int(row.get("unchanged") or 0),
            "average_return_pct": _round(_number(row.get("average_return_pct"))),
            "median_return_pct": _round(_number(row.get("median_return_pct"))),
            "amount": _round(_number(row.get("amount"))),
            "above_ma20": int(row.get("above_ma20") or 0),
            "above_ma60": int(row.get("above_ma60") or 0),
            "limit_up": int(row.get("limit_up") or 0),
            "limit_down": int(row.get("limit_down") or 0),
            "opened_limits": int(row.get("opened_limits") or 0),
        }
        return {
            "data": {
                **normalized,
                "advance_decline_ratio": _round(_safe_div(advancing, declining)),
                "advance_share_pct": _round(advancing / securities * 100 if securities else None),
                "above_ma20_share_pct": _round((row.get("above_ma20") or 0) / securities * 100 if securities else None),
                "above_ma60_share_pct": _round((row.get("above_ma60") or 0) / securities * 100 if securities else None),
            },
            "meta": {
                "as_of": effective_as_of,
                "generated_at": datetime.now(timezone.utc),
                "methodology": "latest market date not later than as_of; moving averages use the latest 20/60 observations",
                "provenance": ["stock_daily", "limit_list_d"],
            },
        }

    def sector_rotation(
        self,
        provider: str,
        *,
        lookback_days: int = 60,
        as_of: date | None = None,
        limit: int = 20,
    ) -> dict[str, Any]:
        if provider not in {"ths", "dc", "tdx"}:
            raise InvalidQueryError("provider must be one of ths, dc or tdx")
        effective_as_of = as_of or business_now().date()
        catalog = self._data.list_sectors(
            provider=provider,
            as_of=effective_as_of,
            limit=1000,
        ).get("data", [])
        names = {item.get("sector_code"): item.get("name") for item in catalog}
        allowed_codes = [code for code in names if code]
        rows = (
            self._repository.sector_rotation(
                provider,
                as_of=effective_as_of,
                lookback_days=lookback_days,
                limit=max(len(allowed_codes), limit * 2),
                allowed_codes=allowed_codes,
            )
            if allowed_codes
            else []
        )
        enriched = [
            {
                **row,
                "name": names.get(row.get("ts_code")),
                "close": _number(row.get("close")),
                "start_close": _number(row.get("start_close")),
                "average_volume": _number(row.get("average_volume")),
                "average_daily_return": _number(row.get("average_daily_return")),
                "observations": int(row.get("observations") or 0),
                "period_return_pct": _round(_number(row.get("period_return_pct"))),
            }
            for row in rows
        ]
        effective_dates = [
            observed
            for row in rows
            if (observed := _day(row.get("trade_date"))) is not None
        ]
        effective_date = max(effective_dates, default=None)
        lag_days = (
            (effective_as_of - effective_date).days
            if effective_date is not None
            else None
        )
        leaders = enriched[:limit]
        laggards = list(reversed(enriched[-limit:]))
        return {
            "data": {"leaders": leaders, "laggards": laggards},
            "meta": {
                "provider": provider,
                "as_of": effective_as_of,
                "effective_date": effective_date,
                "lag_days": lag_days,
                "lookback_days": lookback_days,
                "generated_at": datetime.now(timezone.utc),
                "methodology": (
                    "compounded provider daily returns ranked within the active "
                    "provider sector catalog"
                ),
                "provenance": [f"{provider} sector catalog", f"{provider} sector daily"],
                "quality": {
                    "status": (
                        "ready"
                        if rows and lag_days is not None and lag_days <= 7
                        else "warning"
                    ),
                    "warnings": (
                        []
                        if rows and lag_days is not None and lag_days <= 7
                        else [
                            "provider sector data is missing or more than seven days behind as_of"
                        ]
                    ),
                },
            },
        }
