"""A-share Fama-French three-factor daily returns, deterministic and pure.

This module is independent of repositories and HTTP contracts, matching the
style of ``technical_indicators``. It consumes already-governed cross-sectional
observations (daily returns, total market cap, reported total equity) and exposes the
exact construction contract and version in its output so downstream consumers
can audit how MKT/SMB/HML were derived.

Construction follows Fama-French (1993) with 2x3 value-weighted sorts:
  - Size split: total market cap median each session.
  - B/M split: 30th and 70th percentiles of book-to-market (total equity /
    total market cap) each session.
  - SMB = mean(small portfolios) - mean(big portfolios).
  - HML = mean(high B/M portfolios) - mean(low B/M portfolios).
  - MKT = value-weighted Shanghai/Shenzhen A-share return minus the risk-free
    rate.
"""

from __future__ import annotations

from typing import Any, Iterable

FF3_FORMULA_VERSION = "ff3-sh-sz-v2"

# A session with fewer than this many eligible names is recorded as
# insufficient_universe rather than fabricating a split from a thin sample.
MIN_ELIGIBLE = 20


def _value_weighted(
    returns: list[float],
    caps: list[float],
) -> float | None:
    """Value-weighted mean return; None if weights vanish."""
    total = sum(caps)
    if total <= 0:
        return None
    return sum(r * c for r, c in zip(returns, caps)) / total


def _portfolio_return(rows: list[tuple[float, float]]) -> float | None:
    """Value-weighted return for one size × book-to-market portfolio."""

    if not rows:
        return None
    return _value_weighted(
        [item[0] for item in rows], [item[1] for item in rows]
    )


def daily_factors(
    returns: list[float],
    caps: list[float],
    book_equity: list[float | None],
    risk_free: float = 0.0,
) -> dict[str, Any]:
    """Compute MKT/SMB/HML for a single trading session cross-section.

    ``returns``, ``caps`` and ``book_equity`` are aligned per stock, already
    filtered to the eligible universe by the caller. Stocks without positive
    book equity participate in MKT, but cannot enter the six size/value
    portfolios used by both SMB and HML.
    """
    if not (len(returns) == len(caps) == len(book_equity)):
        raise ValueError("returns, caps and book_equity must have equal length")
    n = len(returns)

    # MKT: value-weighted Shanghai/Shenzhen A-share return minus risk-free.
    # Defined for any
    # non-empty cross-section; it does not depend on a size/B-M sort.
    mkt = _value_weighted(returns, caps)
    if mkt is not None:
        mkt -= risk_free

    if n < MIN_ELIGIBLE:
        return {
            "status": "insufficient_universe",
            "eligible_count": n,
            "book_value_eligible_count": sum(
                value is not None and value > 0 for value in book_equity
            ),
            "small_count": 0,
            "big_count": 0,
            "mkt": mkt,
            "smb": None,
            "hml": None,
            "portfolio_returns": {},
            "formula_version": FF3_FORMULA_VERSION,
        }

    # The six portfolios require a valid positive B/M observation.  A missing
    # B/M may still contribute to MKT, but not to either SMB or HML.
    bm_rows = [
        (i, book_equity[i] / caps[i])
        for i in range(n)
        if book_equity[i] is not None and book_equity[i] > 0 and caps[i] > 0
    ]
    if len(bm_rows) < MIN_ELIGIBLE:
        return {
            "status": "insufficient_universe",
            "eligible_count": n,
            "book_value_eligible_count": len(bm_rows),
            "small_count": 0,
            "big_count": 0,
            "mkt": mkt,
            "smb": None,
            "hml": None,
            "portfolio_returns": {},
            "formula_version": FF3_FORMULA_VERSION,
        }

    eligible_indices = [index for index, _value in bm_rows]
    ranked_by_size = sorted(eligible_indices, key=lambda index: (caps[index], index))
    small_indices = set(ranked_by_size[: len(ranked_by_size) // 2])
    sorted_bm = sorted(value for _index, value in bm_rows)
    low_break = sorted_bm[max(0, int(len(sorted_bm) * 0.3) - 1)]
    high_break = sorted_bm[min(len(sorted_bm) - 1, int(len(sorted_bm) * 0.7))]

    portfolios: dict[str, list[tuple[float, float]]] = {
        key: [] for key in ("small_low", "small_mid", "small_high", "big_low", "big_mid", "big_high")
    }
    for index, bm_value in bm_rows:
        size = "small" if index in small_indices else "big"
        value = "low" if bm_value <= low_break else "high" if bm_value >= high_break else "mid"
        portfolios[f"{size}_{value}"].append((returns[index], caps[index]))
    portfolio_returns = {
        key: _portfolio_return(rows) for key, rows in portfolios.items()
    }
    if any(value is None for value in portfolio_returns.values()):
        return {
            "status": "insufficient_universe",
            "eligible_count": n,
            "book_value_eligible_count": len(bm_rows),
            "small_count": sum(len(rows) for key, rows in portfolios.items() if key.startswith("small_")),
            "big_count": sum(len(rows) for key, rows in portfolios.items() if key.startswith("big_")),
            "mkt": mkt,
            "smb": None,
            "hml": None,
            "portfolio_returns": portfolio_returns,
            "formula_version": FF3_FORMULA_VERSION,
        }

    small_returns = [portfolio_returns[f"small_{bucket}"] for bucket in ("low", "mid", "high")]
    big_returns = [portfolio_returns[f"big_{bucket}"] for bucket in ("low", "mid", "high")]
    high_returns = [portfolio_returns["small_high"], portfolio_returns["big_high"]]
    low_returns = [portfolio_returns["small_low"], portfolio_returns["big_low"]]
    smb = sum(float(value) for value in small_returns) / 3 - sum(float(value) for value in big_returns) / 3
    hml = sum(float(value) for value in high_returns) / 2 - sum(float(value) for value in low_returns) / 2

    return {
        "status": "ready",
        "eligible_count": n,
        "book_value_eligible_count": len(bm_rows),
        "small_count": sum(len(rows) for key, rows in portfolios.items() if key.startswith("small_")),
        "big_count": sum(len(rows) for key, rows in portfolios.items() if key.startswith("big_")),
        "mkt": mkt,
        "smb": smb,
        "hml": hml,
        "portfolio_returns": portfolio_returns,
        "formula_version": FF3_FORMULA_VERSION,
    }


def value_weighted_return(
    returns: list[float],
    caps: list[float],
) -> float | None:
    """Expose value-weighted return for callers that only need MKT."""
    return _value_weighted(returns, caps)


def percentile_split(values: Iterable[float], pct: float) -> float | None:
    """Return the approximate percentile threshold of a finite sample."""
    finite = sorted(v for v in values if v is not None)
    if not finite:
        return None
    return finite[min(len(finite) - 1, int(len(finite) * pct))]
