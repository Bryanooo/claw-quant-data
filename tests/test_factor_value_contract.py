import pytest

from service.acquisition_runtime.factor_value_contract import (
    FACTOR_VALUE_ALPHA101_NAMES,
    FACTOR_VALUE_EXPECTED_COUNT,
    FACTOR_VALUE_EXPECTED_NON_ALPHA_COUNT,
    FactorValueCatalogDriftError,
    governed_factor_names,
)


def reviewed_catalog() -> set[str]:
    # Mirror the currently discovered state: all 171 non-Alpha factors but
    # only the 31 Alpha101 rows rendered in the expanded documentation table.
    rendered_alpha_numbers = (
        *range(1, 21), 22, 23, 25, 33, 34, 41, 52, 53, 54, 57, 101,
    )
    return {f"alpha101_{number}" for number in rendered_alpha_numbers} | {
        f"reviewed_non_alpha_{index}"
        for index in range(FACTOR_VALUE_EXPECTED_NON_ALPHA_COUNT)
    }


def test_reviewed_factor_value_catalog_is_accepted_and_normalized():
    names = reviewed_catalog()

    governed = governed_factor_names([*names, "alpha101_1", " "])

    assert len(governed) == FACTOR_VALUE_EXPECTED_COUNT
    assert set(FACTOR_VALUE_ALPHA101_NAMES) <= set(governed)
    assert "alpha101_21" in governed


def test_alpha101_name_outside_declared_range_is_rejected():
    names = reviewed_catalog()
    names.add("alpha101_102")

    with pytest.raises(FactorValueCatalogDriftError, match="Alpha101 catalog drift"):
        governed_factor_names(names)


def test_catalog_count_drift_fails_closed():
    names = reviewed_catalog()
    names.remove("reviewed_non_alpha_0")

    with pytest.raises(FactorValueCatalogDriftError, match="expected 171"):
        governed_factor_names(names)
