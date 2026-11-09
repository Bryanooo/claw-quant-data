"""Locally calculated non-financial members of the 272-factor product."""

from __future__ import annotations

from dataclasses import dataclass
from math import ceil

import numpy as np
import pandas as pd

from .alpha101 import Alpha101Evaluator, Alpha101Panel, minimum_history


# The longest Alpha101 primitive is 250 bars.  A 512-bar buffer covers nested
# delay/rolling expressions without making those 101 formulas carry the 1,325
# bars required only by long-horizon risk factors.
ALPHA101_LOOKBACK = 512


def _last_rolling_mean(values: pd.DataFrame, window: int) -> pd.Series:
    selected = values.tail(window).astype(float).replace([np.inf, -np.inf], np.nan)
    return selected.mean().where(selected.count().eq(window))


def _last_rolling_std(values: pd.DataFrame, window: int) -> pd.Series:
    selected = values.tail(window).astype(float).replace([np.inf, -np.inf], np.nan)
    return selected.std(ddof=1).where(selected.count().eq(window))


def _cumulative_return(returns: pd.DataFrame, window: int) -> pd.Series:
    selected = returns.tail(window).add(1).astype(float).replace([np.inf, -np.inf], np.nan)
    return selected.prod().sub(1).where(selected.count().eq(window))


def _rolling_regression(
    stock_returns: pd.DataFrame,
    market_returns: pd.Series,
    window: int,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    selected_stock = stock_returns.tail(window)
    selected_market = market_returns.reindex(selected_stock.index).tail(window)
    if len(selected_market.dropna()) < window:
        empty = pd.Series(np.nan, index=stock_returns.columns, dtype=float)
        return empty, empty.copy(), empty.copy()
    market_mean = selected_market.mean()
    market_variance = selected_market.var(ddof=1)
    stock_mean = selected_stock.mean()
    complete = selected_stock.notna().sum().eq(window)
    if not market_variance or not np.isfinite(market_variance):
        empty = pd.Series(np.nan, index=stock_returns.columns, dtype=float)
        return empty, empty.copy(), empty.copy()
    # Every security uses the same benchmark.  Computing the covariance as a
    # matrix operation is mathematically identical for complete windows and
    # avoids one Python callback per security per regression window.
    market_centered = selected_market - market_mean
    stock_centered = selected_stock.sub(stock_mean, axis=1)
    covariance = stock_centered.mul(market_centered, axis=0).sum(axis=0) / (
        window - 1
    )
    beta = (covariance / market_variance).where(complete)
    alpha = stock_mean - beta * market_mean
    residual = selected_stock.sub(
        selected_market.to_numpy()[:, None] * beta.to_numpy()[None, :], axis=None
    ).sub(alpha, axis=1)
    sigma = residual.std(ddof=1).where(complete)
    return alpha, beta, sigma


def _price_distance(value: float) -> float:
    if not np.isfinite(value):
        return np.nan
    scale = 1.0 if value < 10 else 10.0 if value < 100 else 100.0
    normalized = value / scale
    return ceil(normalized) - normalized


@dataclass(slots=True)
class MarketFactorPanel:
    alpha101: Alpha101Panel
    turnover_rate: pd.DataFrame
    total_mv: pd.DataFrame
    circ_mv: pd.DataFrame
    benchmark_close_000300: pd.Series
    benchmark_close_000001: pd.Series
    benchmark_volume_000300: pd.Series
    benchmark_volume_000001: pd.Series
    traded_amount_cny: pd.DataFrame | None = None
    listing_dates: pd.Series | None = None
    unexplained_market_gaps: pd.Series | None = None


class MarketFactorEvaluator:
    """Compute all 187 price/volume/risk/size factors in one shared pass."""

    def __init__(
        self,
        panel: MarketFactorPanel,
        *,
        exact_overlaps: dict[str, pd.Series] | None = None,
    ):
        self.panel = panel
        self.price = panel.alpha101.close
        self.returns = self.price.pct_change(fill_method=None)
        self.exact_overlaps = exact_overlaps or {}
        self._price_regression_cache = {}

    def _price_regression(self, window: int, code: str):
        key = (window, code)
        if key not in self._price_regression_cache:
            benchmark = getattr(self.panel, f"benchmark_close_{code}").pct_change(fill_method=None)
            self._price_regression_cache[key] = _rolling_regression(self.returns, benchmark, window)
        return self._price_regression_cache[key]

    def _turnover_factors(self) -> dict[str, pd.Series]:
        turnover = self.panel.turnover_rate / 100.0
        # Turnover liquidity metrics use actual cash turnover in CNY, not
        # price-adjusted pseudo-turnover used to construct Alpha101 VWAP.
        amount = (self.panel.traded_amount_cny if self.panel.traded_amount_cny is not None
                  else self.panel.alpha101.amount * 1000.0)
        output: dict[str, pd.Series] = {}
        means, stds = {}, {}
        def mean(window):
            if window not in means:
                means[window] = _last_rolling_mean(turnover, window)
            return means[window]
        def std(window):
            if window not in stds:
                stds[window] = _last_rolling_std(turnover, window)
            return stds[window]
        for window in (5, 10, 20, 21, 42, 63, 126, 252):
            name = f"avg_turnover_{window}d"
            if name in {"avg_turnover_5d", "avg_turnover_10d", "avg_turnover_20d", "avg_turnover_21d", "avg_turnover_42d", "avg_turnover_63d", "avg_turnover_126d", "avg_turnover_252d"}:
                output[name] = mean(window)
        for window in (21, 42, 63, 126, 252):
            output[f"std_turnover_{window}d"] = std(window)
        for short in (21, 42, 63, 126):
            for long in (252, 504):
                output[f"bias_turn_{short}d_{long}d"] = (
                    mean(short) / mean(long) - 1
                )
                output[f"bias_std_turn_{short}d_{long}d"] = (
                    std(short) / std(long) - 1
                )
        output["amount_ma_20d"] = _last_rolling_mean(amount, 20)
        output["turnover_ma_20d"] = -mean(20)
        output["turnover_ma_20d_120d"] = -(
            mean(20) / mean(120)
        )
        output["sum_abs_rtn_amount_20d"] = (
            self.returns.abs().rolling(20, min_periods=20).sum().iloc[-1]
            / amount.rolling(20, min_periods=20).sum().iloc[-1]
        )

        stock_momentum = self.panel.alpha101.volume.rolling(
            5, min_periods=5
        ).sum().pct_change(fill_method=None)
        for code, benchmark_volume in (
            ("000001", self.panel.benchmark_volume_000001),
            ("000300", self.panel.benchmark_volume_000300),
        ):
            market_momentum = benchmark_volume.rolling(
                5, min_periods=5
            ).sum().pct_change(fill_method=None)
            alpha, _beta, _sigma = _rolling_regression(
                stock_momentum, market_momentum, 300
            )
            output[f"volume_alpha_300d_{code}"] = alpha
        return output

    def _momentum_factors(self) -> dict[str, pd.Series]:
        output: dict[str, pd.Series] = {}
        for window in (5, 21, 42, 63, 126, 252):
            name = f"return_{window}d"
            output[name] = (
                self.exact_overlaps[name] if name in self.exact_overlaps
                else _cumulative_return(self.returns, window)
            )
        output["ma_20d"] = (
            self.exact_overlaps["ma_20d"]
            if "ma_20d" in self.exact_overlaps
            else _last_rolling_mean(self.price, 20)
        )
        intraday = (
            (self.panel.alpha101.close - self.panel.alpha101.open)
            / (self.panel.alpha101.high - self.panel.alpha101.low).replace(0, np.nan)
        )
        output["price_position_ir_60d"] = (
            _last_rolling_mean(intraday, 60) / _last_rolling_std(intraday, 60)
        )
        for window, code in ((125, "000300"), (250, "000300"), (500, "000300"), (528, "000001"), (792, "000001"), (1000, "000300"), (1320, "000001")):
            alpha, _beta, _sigma = self._price_regression(window, code)
            output[f"alpha_{window}d_{code}"] = alpha

        high = self.panel.alpha101.high
        low = self.panel.alpha101.low
        slopes = high.rolling(18, min_periods=18).cov(low).div(
            high.rolling(18, min_periods=18).var(ddof=1)
        )
        output["rsrs"] = (
            (slopes - slopes.rolling(200, min_periods=200).mean())
            / slopes.rolling(200, min_periods=200).std(ddof=1)
        ).iloc[-1]
        if not {"dif", "dea", "MACD"} <= set(self.exact_overlaps):
            ema12 = self.price.ewm(span=12, adjust=False).mean()
            ema26 = self.price.ewm(span=26, adjust=False).mean()
            dif = ema12 - ema26
            dea = dif.ewm(span=9, adjust=False).mean()
            output["dif"] = dif.iloc[-1]
            output["dea"] = dea.iloc[-1]
            output["MACD"] = (2 * (dif - dea)).iloc[-1]
        for name in ("dif", "dea", "MACD"):
            if name in self.exact_overlaps:
                output[name] = self.exact_overlaps[name]

        direction = np.sign(self.price.diff())
        values: dict[str, float] = {}
        for code in self.price.columns:
            consecutive = 0
            last = direction[code].iloc[-1]
            if np.isfinite(last) and last:
                for value in direction[code].iloc[::-1]:
                    if value != last:
                        break
                    consecutive += 1
            up = consecutive if last > 0 else 0
            down = consecutive if last < 0 else 0
            values[code] = abs(up - down - 1)
        output["days_down_up"] = pd.Series(values)
        return output

    def _reversal_factors(self) -> dict[str, pd.Series]:
        reversal = -_cumulative_return(self.returns, 21)
        ranked = reversal.rank(pct=True)
        rsi = self.exact_overlaps.get("rsi")
        if rsi is None:
            delta = self.price.diff()
            gain = delta.clip(lower=0).ewm(com=13, adjust=False, min_periods=14).mean()
            loss = (-delta.clip(upper=0)).ewm(com=13, adjust=False, min_periods=14).mean()
            rsi = (100 - 100 / (1 + gain / loss.replace(0, np.nan))).iloc[-1]
        return {
            "small_cap_reversal_21d": ranked / ranked.sum(),
            "rsi": rsi,
            "price_dist": self.price.iloc[-1].map(_price_distance),
        }

    def _risk_factors(self) -> dict[str, pd.Series]:
        output: dict[str, pd.Series] = {}
        mean21 = self.price.rolling(21, min_periods=21).mean()
        std21 = self.price.rolling(21, min_periods=21).std(ddof=1)
        zscore = (self.price - mean21) / std21
        output["days_beyond_upper_lower_21d"] = (
            (zscore.gt(1).astype(float) - zscore.lt(-1).astype(float))
            .where(np.isfinite(zscore)).rolling(21, min_periods=21).sum()
        ).iloc[-1]
        for window in (21, 42, 63, 126, 252):
            output[f"return_std_{window}d"] = _last_rolling_std(self.returns, window)
            selected = self.price.tail(window)
            output[f"high_low_{window}d"] = (selected.max() / selected.min()).where(
                np.isfinite(selected).sum().eq(window)
            )
        for window in (60, 750):
            output[f"sharpe_{window}d"] = (
                _last_rolling_mean(self.returns, window)
                / _last_rolling_std(self.returns, window)
            )
        std750 = _last_rolling_std(self.returns, 750)
        output["adjusted_sharpe_750d"] = (
            _last_rolling_mean(self.returns, 750) / std750.pow(4)
        )
        benchmarks = {
            "000300": self.panel.benchmark_close_000300.pct_change(fill_method=None),
            "000001": self.panel.benchmark_close_000001.pct_change(fill_method=None),
        }
        for window, code in ((60, "000300"), (125, "000300"), (250, "000300"), (500, "000300"), (1000, "000300"), (1320, "000001")):
            _alpha, beta, sigma = self._price_regression(window, code)
            output[f"beta_{window}d_{code}"] = beta
            if window == 1320:
                output[f"sigma_{window}d_{code}"] = sigma
        alpha300, volume_beta, _ = _rolling_regression(
                self.panel.alpha101.volume.rolling(
                    5, min_periods=5
                ).sum().pct_change(fill_method=None),
            self.panel.benchmark_volume_000300.rolling(5, min_periods=5).sum().pct_change(fill_method=None),
            120,
        )
        del alpha300
        output["volume_beta_120d_000300"] = volume_beta
        _alpha, beta300, sigma300 = self._price_regression(1320, "000300")
        output["sigma_1320d_000300"] = sigma300
        selected = self.returns.tail(1320)
        market = benchmarks["000300"].reindex(selected.index)
        residual = selected.sub(market.to_numpy()[:, None] * beta300.to_numpy()[None, :], axis=None)
        output["beta_consistency_1320d_000300"] = residual.mul(beta300, axis=1).std(ddof=1)
        output["log_price"] = np.log(self.price.iloc[-1].where(self.price.iloc[-1] > 0))
        return output

    def _size_factors(self) -> dict[str, pd.Series]:
        size = -np.log(self.panel.total_mv.iloc[-1] / 100.0)
        float_size = -np.log(self.panel.circ_mv.iloc[-1] / 100.0)
        valid = size.dropna()
        residual = pd.Series(np.nan, index=size.index, dtype=float)
        if len(valid) >= 2 and valid.var() > 0:
            slope = valid.cov(valid.pow(3)) / valid.var()
            intercept = valid.pow(3).mean() - slope * valid.mean()
            residual.loc[valid.index] = valid.pow(3) - (intercept + slope * valid)
        return {"size": size, "float_size": float_size, "nl_size": residual}

    def evaluate_latest(self) -> dict[str, pd.Series]:
        self._price_regression_cache.clear()
        alpha_exact = {
            name: value for name, value in self.exact_overlaps.items()
            if name.startswith("alpha101_")
        }
        excluded = frozenset(
            int(name.removeprefix("alpha101_")) for name in alpha_exact
        )
        values = Alpha101Evaluator(
            self.panel.alpha101.tail(ALPHA101_LOOKBACK)
        ).evaluate_latest(
            exclude=excluded
        )
        values.update(alpha_exact)
        if self.panel.listing_dates is not None:
            listed = pd.to_datetime(self.panel.listing_dates.reindex(self.price.columns),
                                    format="%Y%m%d", errors="coerce")
            calendar = self.price.index
            sessions = pd.Series(len(calendar) - calendar.searchsorted(listed), index=listed.index)
            for name in values:
                number = int(name.rsplit('_', 1)[1])
                values[name] = values[name].mask(listed.notna() & (sessions < minimum_history(number)))
        for group in (
            self._turnover_factors(), self._momentum_factors(),
            self._reversal_factors(), self._risk_factors(), self._size_factors(),
        ):
            duplicate = set(values).intersection(group)
            if duplicate:
                raise RuntimeError(f"duplicate local factor producer: {sorted(duplicate)}")
            values.update(group)
        return {name: value.replace([np.inf, -np.inf], np.nan) for name, value in values.items()}
