"""Vectorised WorldQuant Alpha101 evaluator.

The evaluator operates on date-by-security pandas panels.  All rolling windows
are trading bars; fractional windows in the paper are floored as specified by
Appendix A.  Industry neutralisation uses the supplied dated classification,
making the otherwise generic WorldQuant ``IndClass`` choice explicit.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from functools import lru_cache
import re
from types import SimpleNamespace
from typing import Any

import numpy as np
import pandas as pd

from .alpha101_formulas import ALPHA101_FORMULAS


def _window(value: float | int) -> int:
    return max(1, int(float(value)))


def _convert_ternaries(expression: str) -> str:
    """Convert the paper's parenthesised ``c ? a : b`` into ``where`` calls."""

    result = expression
    while "?" in result:
        question = result.rfind("?")
        stack: list[int] = []
        for index, character in enumerate(result[:question]):
            if character == "(":
                stack.append(index)
            elif character == ")":
                stack.pop()
        if not stack:
            raise ValueError(f"ternary has no enclosing parentheses: {expression}")
        opening = stack[-1]
        depth = 0
        colon: int | None = None
        closing: int | None = None
        for index in range(opening, len(result)):
            character = result[index]
            if character == "(":
                depth += 1
            elif character == ")":
                depth -= 1
                if depth == 0:
                    closing = index
                    break
            elif character == ":" and depth == 1 and index > question:
                colon = index
                break
        if colon is None:
            raise ValueError(f"ternary has no matching colon: {expression}")
        # Resume after the colon to find the close of the same expression.
        depth = 1
        for index in range(colon + 1, len(result)):
            character = result[index]
            if character == "(":
                depth += 1
            elif character == ")":
                depth -= 1
                if depth == 0:
                    closing = index
                    break
        if closing is None:
            raise ValueError(f"ternary has no closing parenthesis: {expression}")
        condition = result[opening + 1:question]
        if_true = result[question + 1:colon]
        if_false = result[colon + 1:closing]
        replacement = (
            f"where({_convert_ternaries(condition)},"
            f"{_convert_ternaries(if_true)},{_convert_ternaries(if_false)})"
        )
        result = result[:opening] + replacement + result[closing + 1:]
    return result


def compile_formula(expression: str) -> str:
    """Translate the reviewed paper DSL to the local vector function names."""

    result = _convert_ternaries(expression)
    result = result.replace("^", "**").replace("||", "|")
    aliases = {
        "Ts_ArgMax": "ts_argmax", "Ts_ArgMin": "ts_argmin",
        "Ts_Rank": "ts_rank", "SignedPower": "signedpower",
        "IndNeutralize": "indneutralize", "Log": "log", "Sign": "sign",
    }
    for source, target in aliases.items():
        result = re.sub(rf"\b{source}\b", target, result, flags=re.IGNORECASE)
    result = re.sub(r"\bmin\(", "minimum(", result, flags=re.IGNORECASE)
    result = re.sub(r"\bmax\(", "maximum(", result, flags=re.IGNORECASE)
    result = re.sub(r"\bsum\(", "ts_sum(", result, flags=re.IGNORECASE)
    result = re.sub(r"\bproduct\(", "ts_product(", result, flags=re.IGNORECASE)
    return result


class _FormulaConditions(ast.NodeTransformer):
    """Keep a missing comparison operand distinct from a false comparison."""

    def visit_Compare(self, node):
        self.generic_visit(node)
        if len(node.ops) != 1 or type(node.ops[0]) not in (ast.Lt, ast.Eq):
            raise ValueError('unsupported Alpha101 comparison')
        function = 'less_than' if isinstance(node.ops[0], ast.Lt) else 'equal_to'
        return ast.Call(ast.Name(function, ast.Load()), [node.left, node.comparators[0]], [])

    def visit_BinOp(self, node):
        self.generic_visit(node)
        if isinstance(node.op, ast.Pow):
            return ast.Call(ast.Name('finite_power', ast.Load()), [node.left, node.right], [])
        if isinstance(node.op, ast.BitOr):
            return ast.Call(ast.Name('logical_or', ast.Load()), [node.left, node.right], [])
        return node


@lru_cache(maxsize=202)
def _expression(number, exact_midpoint):
    expression = compile_formula(ALPHA101_FORMULAS[number])
    if number == 66 and exact_midpoint:
        expression = expression.replace("(open - ((high + low) / 2))", "open_minus_midpoint")
    tree = _FormulaConditions().visit(ast.parse(expression, mode='eval'))
    return compile(ast.fix_missing_locations(tree), '<Alpha101>', 'eval')


def _minimum_history(node):
    if isinstance(node, ast.Constant):
        return 0
    if isinstance(node, ast.Attribute):
        return 1  # Dated industry classification.
    if isinstance(node, ast.Name):
        adv = re.fullmatch(r'adv(\d+)', node.id)
        return int(adv[1]) if adv else (2 if node.id == 'returns' else 1)
    if isinstance(node, ast.UnaryOp):
        return _minimum_history(node.operand)
    if isinstance(node, ast.Compare):
        return max(map(_minimum_history, [node.left, *node.comparators]))
    if isinstance(node, ast.BinOp):
        combine = min if isinstance(node.op, ast.BitOr) else max
        return combine(_minimum_history(node.left), _minimum_history(node.right))
    if not isinstance(node, ast.Call):
        raise ValueError('unreviewed Alpha101 syntax')
    name = node.func.id
    bars = [_minimum_history(arg) for arg in node.args]
    if name == 'where':
        return max(bars[0], min(bars[1:]))  # An untaken branch need not exist.
    if name in ('delay', 'delta'):
        return bars[0] + _window(node.args[-1].value)
    rolling = {'correlation', 'covariance', 'decay_linear', 'stddev', 'ts_sum',
               'ts_product', 'ts_max', 'ts_min', 'ts_argmax', 'ts_argmin', 'ts_rank'}
    if name in rolling or (name in ('minimum','maximum') and isinstance(node.args[-1], ast.Constant)):
        return max(bars[:-1]) + _window(node.args[-1].value) - 1
    if name in ('minimum','maximum','signedpower','indneutralize','abs','sign','scale','rank','log'):
        return max(bars)
    raise ValueError(f'unreviewed Alpha101 operator {name}')


@lru_cache(maxsize=101)
def minimum_history(number):
    return _minimum_history(ast.parse(compile_formula(ALPHA101_FORMULAS[number]), mode='eval').body)


def _as_frame(value: Any, template: pd.DataFrame) -> pd.DataFrame:
    if isinstance(value, pd.DataFrame):
        return value
    return pd.DataFrame(value, index=template.index, columns=template.columns)


@dataclass(slots=True)
class Alpha101Panel:
    open: pd.DataFrame
    high: pd.DataFrame
    low: pd.DataFrame
    close: pd.DataFrame
    volume: pd.DataFrame
    amount: pd.DataFrame
    cap: pd.DataFrame
    industry: pd.DataFrame | pd.Series
    sector: pd.DataFrame | pd.Series | None = None
    subindustry: pd.DataFrame | pd.Series | None = None

    # Adjusted (open - midpoint) calculated from exact source quotes before
    # OHLC is compressed to float32. Exact zeros are part of Alpha 66's domain.
    open_minus_midpoint: pd.DataFrame | None = None

    def __post_init__(self) -> None:
        shape = self.close.shape
        axes = (self.close.index, self.close.columns)
        for name in ("open", "high", "low", "volume", "amount", "cap", "open_minus_midpoint"):
            if name == "open_minus_midpoint" and self.open_minus_midpoint is None:
                continue
            value = getattr(self, name)
            if value.shape != shape or not value.index.equals(axes[0]) or not value.columns.equals(axes[1]):
                raise ValueError(f"Alpha101 panel axis mismatch: {name}")

    @property
    def returns(self) -> pd.DataFrame:
        return self.close.pct_change(fill_method=None)

    @property
    def vwap(self) -> pd.DataFrame:
        # Tushare daily: amount is thousand CNY and volume is 100-share lots.
        return self.amount.mul(10.0).div(self.volume.replace(0, np.nan))

    def adv(self, days: int) -> pd.DataFrame:
        # In the Alpha101 DSL ``advN`` is the N-session average of the same
        # ``volume`` primitive used by expressions such as ``volume/adv20``.
        # Using cash amount here made that ratio dimensionally invalid and
        # forced conditional factors (notably Alpha 7) down the wrong branch.
        return self.volume.rolling(days, min_periods=days).mean()

    def tail(self, observations: int) -> "Alpha101Panel":
        """Return a bounded history view while retaining the full universe."""

        def selected(value: pd.DataFrame | pd.Series | None):
            return value.tail(observations) if isinstance(value, pd.DataFrame) else value

        return Alpha101Panel(
            self.open.tail(observations), self.high.tail(observations),
            self.low.tail(observations), self.close.tail(observations),
            self.volume.tail(observations), self.amount.tail(observations),
            self.cap.tail(observations), selected(self.industry),
            selected(self.sector), selected(self.subindustry), selected(self.open_minus_midpoint),
        )


class Alpha101Evaluator:
    def __init__(self, panel: Alpha101Panel):
        self.panel = panel
        self.template = panel.close
        self._namespace_cache: dict[str, Any] | None = None

    @staticmethod
    def rank(value: pd.DataFrame) -> pd.DataFrame:
        return value.replace([np.inf, -np.inf], np.nan).rank(axis=1, pct=True)

    @staticmethod
    def delay(value: pd.DataFrame, days: float) -> pd.DataFrame:
        return value.shift(_window(days))

    @staticmethod
    def delta(value: pd.DataFrame, days: float) -> pd.DataFrame:
        return value - value.shift(_window(days))

    @staticmethod
    def _rolling_comovement(left, right, days, *, correlation):
        # E[XY] - E[X]E[Y] loses the entire covariance for large levels
        # and small fluctuations. Center each complete window before taking
        # products. Bound temporary arrays independently of the universe size.
        window = _window(days)
        if not left.index.equals(right.index) or not left.columns.equals(right.columns):
            left, right = left.align(right)
        x_values = left.to_numpy(dtype=float).T
        y_values = right.to_numpy(dtype=float).T
        result = np.full(x_values.shape, np.nan)
        if window == 1:
            result[np.isfinite(x_values) & np.isfinite(y_values)] = 0.
        elif x_values.shape[1] >= window:
            num_windows = x_values.shape[1] - window + 1
            batch = max(1, 500_000 // (num_windows * window))
            for start in range(0, len(x_values), batch):
                targets = slice(start, start + batch)
                centered = []
                for values in (x_values, y_values):
                    blocks = np.lib.stride_tricks.sliding_window_view(
                        np.ascontiguousarray(values[targets]), window, axis=1)
                    with np.errstate(invalid='ignore'):
                        deltas = blocks - blocks[..., :1]
                        deltas -= deltas.mean(axis=-1, keepdims=True)
                    centered.append(deltas)
                x, y = centered
                xy = np.einsum('ijk,ijk->ij', x, y)
                if correlation:
                    norm = np.sqrt(np.einsum('ijk,ijk->ij', x, x)) * np.sqrt(np.einsum('ijk,ijk->ij', y, y))
                    with np.errstate(invalid='ignore', divide='ignore'):
                        # The DSL assigns zero to complete constant windows.
                        coeff = np.where((norm == 0) & np.isfinite(xy), 0., xy / norm)
                    result[targets, window - 1:] = np.clip(coeff, -1., 1.)
                else:
                    result[targets, window - 1:] = xy / (window - 1)
        return pd.DataFrame(result.T, index=left.index, columns=left.columns).replace([np.inf, -np.inf], np.nan)

    @classmethod
    def correlation(cls, left: pd.DataFrame, right: pd.DataFrame, days: float) -> pd.DataFrame:
        return cls._rolling_comovement(left, right, days, correlation=True)

    @classmethod
    def covariance(cls, left: pd.DataFrame, right: pd.DataFrame, days: float) -> pd.DataFrame:
        return cls._rolling_comovement(left, right, days, correlation=False)

    @staticmethod
    def scale(value: pd.DataFrame, amount: float = 1.0) -> pd.DataFrame:
        value = value.replace([np.inf, -np.inf], np.nan)
        denominator = value.abs().sum(axis=1).replace(0, np.nan)
        return value.div(denominator, axis=0).mul(amount)

    @staticmethod
    def signedpower(value: pd.DataFrame, exponent: Any) -> pd.DataFrame:
        return np.sign(value) * np.power(np.abs(value), exponent)

    @staticmethod
    def decay_linear(value: pd.DataFrame, days: float) -> pd.DataFrame:
        window = _window(days)
        array = value.to_numpy(dtype=float, copy=False)
        result = np.zeros_like(array)
        valid = np.zeros(array.shape, dtype=np.uint16)
        denominator = window * (window + 1) / 2
        # At row t, lag zero is the newest observation and therefore carries
        # weight ``window``.  Looping over at most ~60 lags keeps memory O(T*N)
        # and performs each operation in NumPy instead of millions of Python
        # rolling callbacks.
        for lag in range(min(window, len(array))):
            source = array[: len(array) - lag]
            finite = np.isfinite(source)
            target = result[lag:]
            target[finite] += source[finite] * (window - lag)
            valid[lag:][finite] += 1
        result /= denominator
        result[valid != window] = np.nan
        return pd.DataFrame(result, index=value.index, columns=value.columns)

    @staticmethod
    def ts_min(value: pd.DataFrame, days: float) -> pd.DataFrame:
        window = _window(days)
        return value.rolling(window, min_periods=window).min()

    @staticmethod
    def ts_max(value: pd.DataFrame, days: float) -> pd.DataFrame:
        window = _window(days)
        return value.rolling(window, min_periods=window).max()

    @staticmethod
    def ts_sum(value: pd.DataFrame, days: float) -> pd.DataFrame:
        window = _window(days)
        return value.rolling(window, min_periods=window).sum()

    @staticmethod
    def ts_product(value: pd.DataFrame, days: float) -> pd.DataFrame:
        window = _window(days)
        array = value.to_numpy(dtype=float, copy=False)
        result = np.ones_like(array)
        valid = np.zeros(array.shape, dtype=np.uint16)
        for lag in range(min(window, len(array))):
            source = array[: len(array) - lag]
            finite = np.isfinite(source)
            result[lag:][finite] *= source[finite]
            valid[lag:][finite] += 1
        result[valid != window] = np.nan
        return pd.DataFrame(result, index=value.index, columns=value.columns)

    @staticmethod
    def stddev(value: pd.DataFrame, days: float) -> pd.DataFrame:
        window = _window(days)
        return value.rolling(window, min_periods=window).std(ddof=1)

    @staticmethod
    def ts_rank(value: pd.DataFrame, days: float) -> pd.DataFrame:
        window = _window(days)
        array = value.to_numpy(dtype=float, copy=False)
        less = np.zeros(array.shape, dtype=np.uint16)
        equal = np.zeros(array.shape, dtype=np.uint16)
        valid = np.zeros(array.shape, dtype=np.uint16)
        current = array
        current_finite = np.isfinite(current)
        for lag in range(min(window, len(array))):
            source = array[: len(array) - lag]
            target = current[lag:]
            mask = np.isfinite(source) & current_finite[lag:]
            less[lag:][mask] += source[mask] < target[mask]
            equal[lag:][mask] += source[mask] == target[mask]
            valid[lag:][mask] += 1
        result = (less + (equal + 1) / 2) / np.where(valid, valid, 1)
        result[valid != window] = np.nan
        return pd.DataFrame(result, index=value.index, columns=value.columns)

    @staticmethod
    def ts_argmax(value: pd.DataFrame, days: float) -> pd.DataFrame:
        return Alpha101Evaluator._ts_argextreme(value, days, maximum=True)

    @staticmethod
    def ts_argmin(value: pd.DataFrame, days: float) -> pd.DataFrame:
        return Alpha101Evaluator._ts_argextreme(value, days, maximum=False)

    @staticmethod
    def _ts_argextreme(
        value: pd.DataFrame, days: float, *, maximum: bool,
    ) -> pd.DataFrame:
        window = _window(days)
        array = value.to_numpy(dtype=float, copy=False)
        best = np.full(array.shape, np.nan)
        position = np.full(array.shape, np.nan)
        valid = np.zeros(array.shape, dtype=np.uint16)
        # Oldest-to-newest plus strict comparison preserves NumPy/Pandas'
        # first-position tie convention.
        for lag in range(min(window, len(array)) - 1, -1, -1):
            source = array[: len(array) - lag]
            target_best = best[lag:]
            finite = np.isfinite(source)
            improve = finite & (
                ~np.isfinite(target_best)
                | ((source > target_best) if maximum else (source < target_best))
            )
            target_best[improve] = source[improve]
            position[lag:][improve] = window - lag
            valid[lag:][finite] += 1
        position[valid != window] = np.nan
        return pd.DataFrame(position, index=value.index, columns=value.columns)

    def minimum(self, left: Any, right: Any) -> pd.DataFrame:
        if np.isscalar(right):
            return self.ts_min(_as_frame(left, self.template), right)
        return pd.DataFrame(
            np.minimum(left, right), index=self.template.index,
            columns=self.template.columns,
        )

    def maximum(self, left: Any, right: Any) -> pd.DataFrame:
        if np.isscalar(right):
            return self.ts_max(_as_frame(left, self.template), right)
        return pd.DataFrame(
            np.maximum(left, right), index=self.template.index,
            columns=self.template.columns,
        )

    def where(self, condition: Any, if_true: Any, if_false: Any) -> pd.DataFrame:
        condition_frame = _as_frame(condition, self.template)
        true_frame = _as_frame(if_true, self.template)
        false_frame = _as_frame(if_false, self.template)
        return true_frame.where(condition_frame.eq(1), false_frame).where(condition_frame.notna())

    def finite_power(self, left, right):
        left, right = _as_frame(left, self.template), _as_frame(right, self.template)
        return left.pow(right).where(np.isfinite(left) & np.isfinite(right))

    def less_than(self, left, right):
        left, right = _as_frame(left, self.template), _as_frame(right, self.template)
        return left.lt(right).astype('float32').where(np.isfinite(left) & np.isfinite(right))

    def equal_to(self, left, right):
        left, right = _as_frame(left, self.template), _as_frame(right, self.template)
        return left.eq(right).astype('float32').where(np.isfinite(left) & np.isfinite(right))

    def logical_or(self, left, right):
        left, right = _as_frame(left, self.template), _as_frame(right, self.template)
        true = left.eq(1) | right.eq(1)
        return true.astype('float32').where(true | (left.eq(0) & right.eq(0)))

    @staticmethod
    def _neutralize_one_date(
        row: pd.Series, groups: pd.Series,
    ) -> pd.Series:
        row = row.replace([np.inf, -np.inf], np.nan)
        aligned = groups.reindex(row.index).replace({"__unknown__": None, "": None})
        return row - row.groupby(aligned).transform("mean")

    def indneutralize(
        self, value: pd.DataFrame, groups: pd.DataFrame | pd.Series,
    ) -> pd.DataFrame:
        if isinstance(groups, pd.Series):
            return value.apply(self._neutralize_one_date, axis=1, groups=groups)
        output = value.copy()
        for date_value in value.index:
            output.loc[date_value] = self._neutralize_one_date(
                value.loc[date_value], groups.loc[date_value]
            )
        return output

    def _namespace(self) -> dict[str, Any]:
        if self._namespace_cache is not None:
            return self._namespace_cache
        panel = self.panel
        sector = panel.sector if panel.sector is not None else panel.industry
        subindustry = (
            panel.subindustry if panel.subindustry is not None else panel.industry
        )
        namespace: dict[str, Any] = {
            "open": panel.open, "high": panel.high, "low": panel.low,
            "close": panel.close, "volume": panel.volume,
            "amount": panel.amount, "cap": panel.cap,
            "returns": panel.returns, "vwap": panel.vwap,
            "IndClass": SimpleNamespace(
                sector=sector, industry=panel.industry, subindustry=subindustry,
            ),
            "less_than": self.less_than, "equal_to": self.equal_to, "logical_or": self.logical_or,
            "rank": self.rank, "delay": self.delay, "delta": self.delta,
            "correlation": self.correlation, "covariance": self.covariance, "finite_power": self.finite_power,
            "scale": self.scale, "signedpower": self.signedpower,
            "decay_linear": self.decay_linear, "ts_min": self.ts_min,
            "ts_max": self.ts_max, "ts_sum": self.ts_sum,
            "ts_product": self.ts_product, "stddev": self.stddev,
            "ts_rank": self.ts_rank, "ts_argmax": self.ts_argmax,
            "ts_argmin": self.ts_argmin, "minimum": self.minimum,
            "maximum": self.maximum, "where": self.where,
            "indneutralize": self.indneutralize,
            "abs": np.abs, "log": np.log, "sign": np.sign,
        }
        for days in (5, 10, 15, 20, 30, 40, 50, 60, 81, 120, 150, 180):
            namespace[f"adv{days}"] = panel.adv(days)
        self._namespace_cache = namespace
        return namespace

    def evaluate(self, number: int) -> pd.DataFrame:
        if number not in ALPHA101_FORMULAS:
            raise ValueError(f"unknown Alpha101 formula: {number}")
        exact_midpoint = number == 66 and self.panel.open_minus_midpoint is not None
        namespace = self._namespace()
        if exact_midpoint:
            namespace = dict(namespace, open_minus_midpoint=self.panel.open_minus_midpoint.replace(0, np.nan))
        value = eval(_expression(number, exact_midpoint), {"__builtins__": {}}, namespace)  # noqa: S307
        return _as_frame(value, self.template).replace([np.inf, -np.inf], np.nan)

    def evaluate_latest(
        self, *, exclude: frozenset[int] = frozenset()
    ) -> dict[str, pd.Series]:
        return {
            f"alpha101_{number}": self.evaluate(number).iloc[-1]
            for number in range(1, 102)
            if number not in exclude
        }
