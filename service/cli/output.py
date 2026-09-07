"""Stable output encoders for humans, shell pipelines and agents."""

from __future__ import annotations

import csv
import io
import json
from collections.abc import Iterable, Mapping
from typing import Any

from service.cli.client import CliError, EXIT_INVALID_RESPONSE


def render(payload: Any, *, output_format: str, pretty: bool) -> str:
    if output_format == "json":
        return json.dumps(
            payload,
            ensure_ascii=False,
            indent=2 if pretty else None,
            separators=None if pretty else (",", ":"),
            sort_keys=True,
            default=_json_default,
        )

    rows = _rows(payload)
    if output_format == "jsonl":
        return "\n".join(
            json.dumps(
                row,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
                default=_json_default,
            )
            for row in rows
        )
    if output_format == "csv":
        return _csv(rows)
    raise CliError(
        code="unsupported_output",
        message=f"unsupported output format: {output_format}",
        exit_code=EXIT_INVALID_RESPONSE,
    )


def render_error(error: CliError) -> str:
    return json.dumps(
        error.as_dict(),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _rows(payload: Any) -> list[dict[str, Any]]:
    candidate = payload.get("data") if isinstance(payload, Mapping) else payload
    if isinstance(candidate, Mapping):
        return [dict(candidate)]
    if isinstance(candidate, list) and all(isinstance(item, Mapping) for item in candidate):
        return [dict(item) for item in candidate]
    raise CliError(
        code="tabular_output_unavailable",
        message="CSV and JSONL output require an object or a list of objects",
        exit_code=EXIT_INVALID_RESPONSE,
    )


def _csv(rows: Iterable[dict[str, Any]]) -> str:
    materialized = list(rows)
    if not materialized:
        return ""
    fieldnames = sorted({key for row in materialized for key in row})
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    for row in materialized:
        writer.writerow(
            {
                key: _csv_value(row.get(key))
                for key in fieldnames
            }
        )
    return output.getvalue().rstrip("\n")


def _csv_value(value: Any) -> Any:
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
            default=_json_default,
        )
    return value


def _json_default(value: Any) -> str:
    isoformat = getattr(value, "isoformat", None)
    return isoformat() if callable(isoformat) else str(value)
