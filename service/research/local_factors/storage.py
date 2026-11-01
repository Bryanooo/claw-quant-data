"""Capacity planning helpers for the array-snapshot storage model."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class StorageEstimate:
    rows: int
    long_form_rows: int
    validation_rows: int
    factor_payload_gib: float
    base_with_indexes_gib: float
    planned_low_gib: float
    planned_high_gib: float


def estimate_ten_year_storage(
    *,
    securities: int = 6000,
    sessions_per_year: int = 252,
    years: int = 10,
    factor_count: int = 272,
    measured_factor_array_bytes: int | None = None,
) -> StorageEstimate:
    """Estimate PostgreSQL storage without pretending TOAST/bloat is exact.

    ``FLOAT8[]`` uses a 24-byte array header plus eight bytes per value before
    its optional null bitmap/alignment.  Real database measurements can replace
    that theoretical payload.  The capacity range includes heap/TOAST tuple
    headers, readiness metadata, primary and lookup indexes, autovacuum headroom
    and ordinary 15–35% operational bloat.
    """

    rows = securities * sessions_per_year * years
    long_rows = rows * factor_count
    validation_rows = sessions_per_year * years * factor_count
    payload_bytes = measured_factor_array_bytes or (24 + factor_count * 8 + 40)
    # Main tuple + TOAST pointer/tuple + readiness metadata and two B-tree
    # entries. This is a planning allowance, not a fake byte-exact promise.
    structural_bytes = 360
    factor_payload = rows * payload_bytes
    # Validation is one compact row per factor/session, not per stock.
    base = rows * (payload_bytes + structural_bytes) + validation_rows * 320
    gib = 1024 ** 3
    return StorageEstimate(
        rows=rows,
        long_form_rows=long_rows,
        validation_rows=validation_rows,
        factor_payload_gib=round(factor_payload / gib, 2),
        base_with_indexes_gib=round(base / gib, 2),
        planned_low_gib=round(base * 1.15 / gib, 2),
        planned_high_gib=round(base * 1.45 / gib, 2),
    )
