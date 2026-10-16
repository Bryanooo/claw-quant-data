"""Strict decoding helpers for 蚂蚁数据源 tabular responses."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from service.source_connectors.financial_data import FinancialDataProtocolError


def tabular_rows(response: Mapping[str, Any], *, route: str) -> list[dict[str, Any]]:
    """Decode one audited route from the provider's fields/row-array format."""
    if response.get("status") != "SUCCESS":
        raise FinancialDataProtocolError(
            f"financial-data route {route} did not complete successfully"
        )
    results = response.get("results")
    if not isinstance(results, list):
        raise FinancialDataProtocolError("financial-data results must be a list")
    matching = [item for item in results if isinstance(item, Mapping) and item.get("url") == route]
    if len(matching) != 1:
        raise FinancialDataProtocolError(
            f"financial-data response must contain exactly one result for {route}"
        )
    result = matching[0]
    meta = result.get("meta")
    fields = meta.get("fields") if isinstance(meta, Mapping) else None
    data = result.get("data")
    if not isinstance(data, list):
        raise FinancialDataProtocolError("financial-data rows must be a list")
    # The provider represents a legitimate empty result as both an empty
    # field list and an empty row list.  Treating that shape as protocol drift
    # would make one no-data route discard every valid result in the same
    # research evidence batch.  Empty fields remain invalid whenever any row
    # is present, so malformed payloads still fail closed.
    if fields == [] and data == []:
        return []
    if not isinstance(fields, list) or not fields or not all(
        isinstance(field, str) and field for field in fields
    ):
        raise FinancialDataProtocolError("financial-data fields are invalid")
    if len(set(fields)) != len(fields):
        raise FinancialDataProtocolError("financial-data fields must be unique")

    rows: list[dict[str, Any]] = []
    for raw in data:
        if isinstance(raw, Mapping):
            unknown = set(raw) - set(fields)
            if unknown:
                raise FinancialDataProtocolError(
                    f"financial-data row has unknown fields: {sorted(unknown)}"
                )
            rows.append({field: raw.get(field) for field in fields})
            continue
        if not isinstance(raw, list) or len(raw) != len(fields):
            raise FinancialDataProtocolError(
                "financial-data row width does not match meta.fields"
            )
        rows.append(dict(zip(fields, raw, strict=True)))
    return rows
