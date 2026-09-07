#!/usr/bin/env python3
"""Collect one authorized Tushare interface from the contract catalog."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from collectors.tushare_raw import CatalogRawCollector
from service.tushare_catalog import TushareInterfaceCatalog


def _key_value(value: str) -> tuple[str, str]:
    key, separator, item = value.partition("=")
    if not separator or not key:
        raise argparse.ArgumentTypeError("use KEY=VALUE")
    return key, item


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Collect an authorized, read-only Tushare interface"
    )
    parser.add_argument("api_name", nargs="?")
    parser.add_argument("--param", action="append", default=[], type=_key_value)
    parser.add_argument("--params-json", default="{}")
    parser.add_argument("--fields", default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--list", action="store_true", dest="list_interfaces")
    args = parser.parse_args()

    catalog = TushareInterfaceCatalog()
    if args.list_interfaces:
        for contract in catalog.list():
            if contract.collectable:
                print(f"{contract.api_name}\t{contract.title}")
        return 0
    if not args.api_name:
        parser.error("api_name is required unless --list is used")

    try:
        parameters = json.loads(args.params_json)
    except json.JSONDecodeError as exc:
        parser.error(f"--params-json is invalid: {exc}")
    if not isinstance(parameters, dict):
        parser.error("--params-json must contain a JSON object")
    parameters.update(dict(args.param))
    if args.fields:
        parameters["fields"] = args.fields

    rows = CatalogRawCollector(args.api_name).collect(
        skip_store=args.dry_run,
        **parameters,
    )
    action = "fetched" if args.dry_run else "stored"
    print(f"{args.api_name}: {action} {rows} rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
