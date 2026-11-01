"""Governed provider contract for Tushare ``factor_value``.

Tushare's factor-list page declares 272 factors and 101 Alpha101 members, while
the expanded table currently shows only 31 Alpha101 rows. The missing names
are a numeric continuation of the declared Alpha101 family, so the governed
target is the declared 101-member family rather than the shortened rendering.

The acquisition path seeds the declared Alpha101 names, but still fails closed
when the 171 non-Alpha factors or Alpha101 naming range drift. Provider calls
remain the final evidence that each seeded member has values.
"""

from __future__ import annotations

from collections.abc import Iterable


FACTOR_VALUE_CONTRACT_REVISION = "tushare-factor-list@2026-10-23"
FACTOR_VALUE_EXPECTED_COUNT = 272
FACTOR_VALUE_EXPECTED_NON_ALPHA_COUNT = 171

# The official summary declares the complete numbered Alpha101 family even
# though the expanded HTML table currently renders only 31 selected rows.
FACTOR_VALUE_ALPHA101_NUMBERS = tuple(range(1, 102))
FACTOR_VALUE_ALPHA101_NAMES = frozenset(
    f"alpha101_{number}" for number in FACTOR_VALUE_ALPHA101_NUMBERS
)


class FactorValueCatalogDriftError(ValueError):
    """The discovered provider catalog no longer matches the reviewed contract."""


def governed_factor_names(values: Iterable[str]) -> list[str]:
    """Validate discovered factors and seed the declared Alpha101 family."""

    discovered = {str(value).strip() for value in values if str(value).strip()}
    alpha101 = {name for name in discovered if name.startswith("alpha101_")}
    unexpected_alpha = sorted(alpha101 - FACTOR_VALUE_ALPHA101_NAMES)
    if unexpected_alpha:
        raise FactorValueCatalogDriftError(
            "factor_value Alpha101 catalog drift: unexpected="
            f"{unexpected_alpha}"
        )

    non_alpha = discovered - alpha101
    if len(non_alpha) != FACTOR_VALUE_EXPECTED_NON_ALPHA_COUNT:
        raise FactorValueCatalogDriftError(
            "factor_value non-Alpha catalog drift: expected "
            f"{FACTOR_VALUE_EXPECTED_NON_ALPHA_COUNT} reviewed factors from "
            f"{FACTOR_VALUE_CONTRACT_REVISION}, discovered {len(non_alpha)}"
        )

    names = sorted(non_alpha | FACTOR_VALUE_ALPHA101_NAMES)
    if len(names) != FACTOR_VALUE_EXPECTED_COUNT:  # defensive invariant
        raise FactorValueCatalogDriftError(
            f"factor_value governed catalog must contain {FACTOR_VALUE_EXPECTED_COUNT} factors"
        )
    return names
