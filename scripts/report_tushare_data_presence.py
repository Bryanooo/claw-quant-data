#!/usr/bin/env python3
"""Report implementation, scheduling and positive-row evidence per API.

This report intentionally separates three facts that are often conflated:
an API can be implemented, not automatically scheduled, and still have no
positive-row evidence in the current database.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import date, datetime
import json
from pathlib import Path
import sys
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import psycopg2
from psycopg2 import sql

from service.collector_catalog import discover_collectors
from service.clock import business_now
from service.config import DB_CONFIG
from service.orchestration_v2.catalog import acquisition_task_blueprints
from service.orchestration_v2.repository import OrchestrationV2Repository
from service.tushare_catalog import TushareInterfaceCatalog
from service.tushare_normalization import normalized_table_name


def _json_default(value: Any) -> str:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return str(value)


def _implementation_tables() -> dict[str, set[str]]:
    collectors = discover_collectors()
    by_reference: dict[tuple[str, str | None], list[Any]] = defaultdict(list)
    for collector in collectors:
        module_name, class_name = collector.qualified_name.rsplit(".", 1)
        path = module_name.replace(".", "/") + ".py"
        by_reference[(path, class_name)].append(collector)
        by_reference[(path, None)].append(collector)

    result: dict[str, set[str]] = defaultdict(set)
    for contract in TushareInterfaceCatalog().list():
        # CatalogRawCollector owns one dynamically generated typed table per
        # interface.  Its static ``table_name`` is only the optional anomaly
        # quarantine, not the business table.  Omitting the generated table
        # made every healthy generic interface look empty after raw capture
        # was correctly reduced to anomalies_only.
        if contract.implementation.get("mode") == "generic_raw":
            result[contract.api_name].add(
                normalized_table_name(contract.api_name)
            )
        for reference in contract.implementation.get("references", ()):
            if ":" in reference:
                path, class_name = reference.split(":", 1)
            else:
                path, class_name = reference, None
            for collector in by_reference.get((path, class_name), ()):
                # Raw evidence is API-scoped and counted separately below;
                # using the shared raw table total would make every generic
                # interface look populated after the first successful API.
                if collector.table_name != "tushare_raw_record":
                    result[contract.api_name].add(collector.table_name)
    return result


def _scheduled_api_names(scheduled_task_keys: set[str]) -> set[str]:
    """Resolve the endpoint the active V2 runtime actually selects per task."""

    result: set[str] = set()
    for task in acquisition_task_blueprints():
        if task.task_key not in scheduled_task_keys:
            continue
        selected = sorted(
            task.endpoints,
            key=lambda item: (
                item.endpoint_key != task.task_key,
                item.endpoint_key.endswith("_vip"),
                item.source_id != "tushare",
                item.endpoint_key,
            ),
        )[0]
        if selected.source_id == "tushare":
            result.add(selected.endpoint_key)
    return result


def build_report(*, exact_row_counts=False) -> dict[str, Any]:
    catalog = TushareInterfaceCatalog()
    implementation_tables = _implementation_tables()
    connection = psycopg2.connect(**DB_CONFIG)
    connection.set_session(readonly=True)
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT api_name, COUNT(*), MAX(collected_at) "
                "FROM tushare_raw_record GROUP BY api_name"
            )
            raw = {
                api_name: {"rows": int(rows), "last_at": last_at}
                for api_name, rows, last_at in cursor.fetchall()
            }
            cursor.execute(
                """
                SELECT task_key AS api_name,
                       COUNT(*) FILTER (WHERE status = 'success'),
                       MAX(finished_at) FILTER (WHERE status = 'success')
                FROM orchestration_v2.task_execution
                GROUP BY 1
                """
            )
            jobs = {
                api_name: {"successful_jobs": int(count), "last_success_at": last_at}
                for api_name, count, last_at in cursor.fetchall()
                if api_name
            }
            scheduled_task_keys = {key for key, state in OrchestrationV2Repository().automation_states().items()
                                   if state['automatic']}

            table_counts: dict[str, int] = {}
            for table_name in sorted({t for values in implementation_tables.values() for t in values}):
                cursor.execute(
                    sql.SQL("SELECT COUNT(*) FROM {}" if exact_row_counts
                            else "SELECT EXISTS(SELECT 1 FROM {} LIMIT 1)").format(sql.Identifier(table_name))
                )
                table_counts[table_name] = int(cursor.fetchone()[0])
    finally:
        connection.close()

    rows = []
    scheduled_apis = _scheduled_api_names(scheduled_task_keys)
    for contract in catalog.list():
        if not contract.collectable:
            continue
        tables = sorted(implementation_tables.get(contract.api_name, ()))
        raw_rows = raw.get(contract.api_name, {}).get("rows", 0)
        normalized_rows = sum(table_counts.get(table, 0) for table in tables)
        positive = raw_rows > 0 or normalized_rows > 0
        automatic = contract.api_name in scheduled_apis
        rows.append(
            {
                "api_name": contract.api_name,
                "implementation_mode": contract.implementation.get("mode"),
                "automatic_scheduling": automatic,
                "raw_rows": raw_rows,
                "normalized_tables": tables,
                "normalized_rows": normalized_rows if exact_row_counts else None,
                "has_normalized_rows": bool(normalized_rows),
                "normalized_row_count_exact": exact_row_counts,
                "successful_jobs": jobs.get(contract.api_name, {}).get("successful_jobs", 0),
                "last_success_at": jobs.get(contract.api_name, {}).get("last_success_at"),
                "last_raw_at": raw.get(contract.api_name, {}).get("last_at"),
                "data_status": "positive_rows" if positive else "no_positive_row_evidence",
            }
        )

    return {
        "generated_at": business_now(),
        "normalized_evidence_mode": "exact_row_counts" if exact_row_counts else "existence_only_not_row_totals",
        "summary": {
            "collectable_interfaces": len(rows),
            "implemented_interfaces": sum(
                item["implementation_mode"] not in {None, "unavailable"} for item in rows
            ),
            "automatically_scheduled_interfaces": sum(
                item["automatic_scheduling"] for item in rows
            ),
            "interfaces_with_positive_rows": sum(
                item["data_status"] == "positive_rows" for item in rows
            ),
            "interfaces_without_positive_row_evidence": sum(
                item["data_status"] == "no_positive_row_evidence" for item in rows
            ),
        },
        "interfaces": rows,
    }


def write_report(report: dict[str, Any], json_path: Path, markdown_path: Path) -> None:
    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, default=_json_default) + "\n",
        encoding="utf-8",
    )
    summary = report["summary"]
    lines = [
        "# Tushare 数据落地证据",
        "",
        f"生成时间：{_json_default(report['generated_at'])}",
        "",
        "> `已实现`、`已自动编排`、`当前库中有正行数`是三个独立状态。无正行数证据不一定代表故障，也可能是当前分区合法为空或尚未执行历史回填。",
        "",
        "| 指标 | 数量 |",
        "|---|---:|",
        f"| 契约登记可采集接口（本次未重新探测权限） | {summary['collectable_interfaces']} |",
        f"| 已实现接口 | {summary['implemented_interfaces']} |",
        f"| 已自动编排接口 | {summary['automatically_scheduled_interfaces']} |",
        f"| 当前有正行数证据 | {summary['interfaces_with_positive_rows']} |",
        f"| 当前无正行数证据 | {summary['interfaces_without_positive_row_evidence']} |",
        "",
        "| API | 实现模式 | 自动编排 | 原始行 | 规范数据证据 | 数据状态 |",
        "|---|---|---:|---:|---:|---|",
    ]
    for item in report["interfaces"]:
        normalized = (str(item['normalized_rows']) if item.get('normalized_row_count_exact', True)
                      else '存在记录' if item['has_normalized_rows'] else '无记录')
        lines.append(
            f"| `{item['api_name']}` | {item['implementation_mode']} | "
            f"{'是' if item['automatic_scheduling'] else '否'} | "
            f"{item['raw_rows']} | {normalized} | {item['data_status']} |"
        )
    markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--exact-row-counts', action='store_true', help='opt in to full table COUNT scans')
    parser.add_argument(
        "--json",
        type=Path,
        default=PROJECT_ROOT / "reports" / "tushare_data_presence_latest.json",
    )
    parser.add_argument(
        "--markdown",
        type=Path,
        default=PROJECT_ROOT / "reports" / "tushare_data_presence_latest.md",
    )
    arguments = parser.parse_args()
    report = build_report(exact_row_counts=arguments.exact_row_counts)
    arguments.json.parent.mkdir(parents=True, exist_ok=True)
    arguments.markdown.parent.mkdir(parents=True, exist_ok=True)
    write_report(report, arguments.json, arguments.markdown)
    print(json.dumps(report["summary"], ensure_ascii=False))


if __name__ == "__main__":
    main()
