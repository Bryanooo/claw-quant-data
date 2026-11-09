"""Derive field lineage by executing financial formulas on symbolic inputs.

No data values or provider requests are involved. Unsupported operations fail
closed, so a new formula cannot silently inherit a stale hand-maintained list.
Existing fillna(0) conventions are exposed as optional inputs, not approved as
evidence that a missing source value is zero.
"""
from dataclasses import dataclass, replace
from functools import lru_cache

from .financial import FinancialFactorEvaluator


@dataclass(frozen=True)
class Dependency:
    required: frozenset[tuple[str, str]] = frozenset()
    optional: frozenset[tuple[str, str]] = frozenset()

    # If a leaf is zero, the expression is respectively undefined, or zero
    # whenever defined. Addition, ranking and nonlinear operations can erase
    # the latter property. A denominator promotes it to a domain constraint.
    nonzero_required: frozenset[tuple[str, str]] = frozenset()
    zero_when: frozenset[tuple[str, str]] = frozenset()

    @classmethod
    def leaf(cls, bucket, metric):
        key = frozenset({(bucket, metric)})
        return cls(required=key, zero_when=key)

    def combine(self, other):
        if not isinstance(other, Dependency):
            return replace(self, zero_when=frozenset())
        required = self.required | other.required
        return Dependency(required, (self.optional | other.optional) - required,
                          self.nonzero_required | other.nonzero_required)

    __add__ = __radd__ = __sub__ = __rsub__ = combine

    def __mul__(self, other):
        other_zero = other.zero_when if isinstance(other, Dependency) else frozenset()
        return replace(self.combine(other), zero_when=self.zero_when | other_zero)

    __rmul__ = __mul__

    def div(self, other):
        result = self.combine(other)
        denominator = other.zero_when if isinstance(other, Dependency) else frozenset()
        return replace(result, nonzero_required=result.nonzero_required | denominator,
                       zero_when=self.zero_when)

    __truediv__ = div

    def __rtruediv__(self, other):
        return Dependency().div(self) if not isinstance(other, Dependency) else other.div(self)

    def __neg__(self): return self
    def replace(self, *args, **kwargs): return self
    def rank(self, *args, **kwargs): return replace(self, zero_when=frozenset())
    def reindex(self, *args, **kwargs): return self
    def pipe(self, function): return function(self)

    def fillna(self, value):
        if value != 0:
            raise ValueError('unreviewed financial fill convention')
        return Dependency(optional=self.required | self.optional)

    def __array_ufunc__(self, ufunc, method, *inputs, **kwargs):
        if ufunc.__name__ != 'power' or method != '__call__' or kwargs:
            raise ValueError('unreviewed financial symbolic operation')
        result = Dependency()
        for item in inputs:
            result = result.combine(item)
        return result


class _SymbolicPanel:
    securities = ()
    close = Dependency.leaf('market', 'close')
    total_mv = Dependency.leaf('market', 'total_mv')
    dividend_cash_3y = Dependency.leaf('special', 'dividend_cash_3y')
    roe_ttm_lag63d = Dependency.leaf('special', 'roe_ttm_lag63d')

    def values(self, bucket, metric):
        return Dependency.leaf(bucket, metric)


@lru_cache(maxsize=1)
def financial_dependencies():
    from types import MappingProxyType
    from .catalog import FACTOR_SPECS
    result = FinancialFactorEvaluator(_SymbolicPanel()).evaluate_latest()
    expected = {s.name for s in FACTOR_SPECS if s.computation_group == 'financial'}
    if set(result) != expected or any(not isinstance(v, Dependency) for v in result.values()):
        raise ValueError('financial dependency coverage does not match the factor catalog')
    return MappingProxyType(result)


def input_value(panel, code, bucket, metric):
    if bucket == 'market':
        return getattr(panel, metric).get(code)
    if bucket == 'special':
        series = getattr(panel, metric)
        return series.get(code) if series is not None else None
    return panel.values(bucket, metric).get(code)


def dependency_inputs(panel):
    """Freeze audit lookups once per panel; avoid per-security Series reindexing."""
    result = {}
    keys = set().union(*(d.required | d.optional for d in financial_dependencies().values()))
    for bucket, metric in keys:
        series = getattr(panel, metric) if bucket in {'market', 'special'} else panel.values(bucket, metric)
        result[(bucket, metric)] = series.to_dict() if series is not None else {}
    return result
