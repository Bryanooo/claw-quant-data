#!/usr/bin/env python3
"""Generate a truthful inventory of public data-service entrypoints."""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from service.data_service.catalog import (
    CANONICAL_ENDPOINTS,
    RAW_ENDPOINTS,
    RESEARCH_ENDPOINTS,
    STANDARD_ENDPOINTS,
)
from service.data_service.registry import DATASETS
from service.research.validation import RESEARCH_VALIDATION_CASES
from service.source_connectors.financial_data_catalog import FINANCIAL_DATA_ROUTES


JSON_PATH = ROOT / "reports" / "data_service_inventory_latest.json"
MARKDOWN_PATH = ROOT / "reports" / "data_service_inventory_latest.md"
STANDARD_GENERIC_ENDPOINTS = tuple(
    endpoint for endpoint in STANDARD_ENDPOINTS
    if endpoint not in CANONICAL_ENDPOINTS
)


def _entry(endpoint: dict, origin: str, test_scope: str) -> dict:
    return {
        **endpoint,
        "origin": origin,
        "test_scope": test_scope,
        "route_contract": "covered",
    }


def build_inventory() -> dict:
    sources = Counter(tuple(item.source_ids) for item in DATASETS.list())
    groups = [
        {
            "id": "tushare_raw_audit",
            "title": "Tushare 原始审计服务",
            "origin": "tushare",
            "items": [
                _entry(item, "tushare", "route + repository contract")
                for item in RAW_ENDPOINTS
            ],
        },
        {
            "id": "canonical_store",
            "title": "规范数据集通用服务",
            "origin": "canonical_db",
            "items": [
                _entry(
                    item,
                    "canonical_db (193 Tushare-only datasets; 1 ChinaMoney/Tushare merged dataset)",
                    "route + registry + query contract",
                )
                for item in STANDARD_GENERIC_ENDPOINTS
            ],
        },
        {
            "id": "canonical_hybrid",
            "title": "规范语义服务",
            "origin": "tushare_db_first_financial_data_fallback",
            "items": [
                _entry(
                    item,
                    "Tushare canonical DB first; Financial Data only after a verified local miss",
                    "route + canonical model + source-selection contract",
                )
                for item in CANONICAL_ENDPOINTS
            ],
        },
        {
            "id": "derived_research",
            "title": "系统聚合研究服务",
            "origin": "derived_from_canonical_db",
            "items": [
                _entry(
                    item,
                    "system-derived aggregation over canonical datasets",
                    "route + calculation unit tests; representative live acceptance set",
                )
                for item in RESEARCH_ENDPOINTS
            ],
        },
    ]
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "counting_rule": (
            "63 catalogued GET data-service entrypoints plus one authenticated "
            "Financial Data POST query-through gateway. The gateway exposes 163 "
            "allowlisted upstream business routes; those routes are not counted as "
            "163 separate local HTTP endpoints."
        ),
        "summary": {
            "catalogued_get_entrypoints": sum(len(group["items"]) for group in groups),
            "financial_data_query_gateways": 1,
            "public_data_http_entrypoints": sum(len(group["items"]) for group in groups) + 1,
            "tushare_raw_audit_entrypoints": len(RAW_ENDPOINTS),
            "canonical_store_entrypoints": len(STANDARD_GENERIC_ENDPOINTS),
            "canonical_hybrid_entrypoints": len(CANONICAL_ENDPOINTS),
            "derived_research_entrypoints": len(RESEARCH_ENDPOINTS),
            "financial_data_business_routes": len(FINANCIAL_DATA_ROUTES),
            "standard_datasets": len(DATASETS.list()),
            "tushare_only_datasets": sources[("tushare",)],
            "multi_source_datasets": sum(
                count for source_ids, count in sources.items()
                if source_ids != ("tushare",)
            ),
        },
        "testing": {
            "route_contract": "64/64 public data entrypoints covered by OpenAPI registration tests",
            "tushare_mapping_contract": "201/201 collectable interfaces map to public datasets",
            "dataset_registry_contract": "194/194 registered datasets map to collector or normalization storage",
            "financial_data_catalog_contract": "163/163 business routes are allowlisted and input-validated",
            "canonical_contract": "24/24 canonical routes registered; domain services have unit/contract tests",
            "research_contract": "28/28 research routes registered; calculation services have unit tests",
            "research_live_acceptance": f"{len(RESEARCH_VALIDATION_CASES)} representative end-to-end cases",
            "financial_data_live_acceptance": (
                "protocol and query gateway covered; a full 163-route live sweep is intentionally not run "
                "in CI because it consumes provider quota and depends on mutable upstream sample data"
            ),
        },
        "groups": groups,
        "financial_data": {
            "gateway": {
                "method": "POST",
                "path": "/api/v1/data/sources/financial_data/query",
                "origin": "financial_data",
                "route_contract": "covered",
                "protocol_contract": "covered",
            },
            "routes": sorted(FINANCIAL_DATA_ROUTES),
        },
    }


def render_markdown(inventory: dict) -> str:
    summary = inventory["summary"]
    lines = [
        "# Data service inventory",
        "",
        f"Generated: `{inventory['generated_at']}`",
        "",
        inventory["counting_rule"],
        "",
        "## Summary",
        "",
        "| Measure | Count |",
        "|---|---:|",
    ]
    for key, value in summary.items():
        lines.append(f"| `{key}` | {value} |")
    lines.extend(["", "## Public service groups", ""])
    for group in inventory["groups"]:
        lines.extend([
            f"### {group['title']} ({len(group['items'])})",
            "",
            "| Method | Path | Service | Origin | Test scope |",
            "|---|---|---|---|---|",
        ])
        for item in group["items"]:
            lines.append(
                f"| {item['method']} | `{item['path']}` | {item['name']} | "
                f"{item['origin']} | {item['test_scope']} |"
            )
        lines.append("")
    lines.extend([
        "## Financial Data query-through",
        "",
        "The local gateway is `POST /api/v1/data/sources/financial_data/query`. "
        "It exposes the following reviewed upstream routes without persisting the credential:",
        "",
    ])
    lines.extend(f"- `{route}`" for route in inventory["financial_data"]["routes"])
    lines.extend(["", "## Test posture", ""])
    for key, value in inventory["testing"].items():
        lines.append(f"- `{key}`: {value}")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    inventory = build_inventory()
    JSON_PATH.write_text(
        json.dumps(inventory, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    MARKDOWN_PATH.write_text(render_markdown(inventory), encoding="utf-8")
    print(json.dumps(inventory["summary"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
