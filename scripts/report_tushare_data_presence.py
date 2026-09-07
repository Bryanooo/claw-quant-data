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
from service.fanout_scheduling import SCHEDULED_FANOUT_RECIPES
from service.tushare_catalog import TushareInterfaceCatalog
from service.tushare_policy import TusharePolicyRegistry
from service.tushare_scheduling import DEDICATED_SCHEDULED_APIS


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


def build_report() -> dict[str, Any]:
    catalog = TushareInterfaceCatalog()
    policies = TusharePolicyRegistry()
    implementation_tables = _implementation_tables()
    connection = psycopg2.connect(**DB_CONFIG)
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
                SELECT COALESCE(api_name, parameters->>'api_name') AS api_name,
                       COUNT(*) FILTER (WHERE status = 'success'),
                       MAX(finished_at) FILTER (WHERE status = 'success')
                FROM sys_collection_job
                GROUP BY 1
                """
            )
            jobs = {
                api_name: {"successful_jobs": int(count), "last_success_at": last_at}
                for api_name, count, last_at in cursor.fetchall()
                if api_name
            }

            table_counts: dict[str, int] = {}
            for table_name in sorted({t for values in implementation_tables.values() for t in values}):
                cursor.execute(
                    sql.SQL("SELECT COUNT(*) FROM {}").format(sql.Identifier(table_name))
                )
                table_counts[table_name] = int(cursor.fetchone()[0])
    finally:
        connection.close()

    rows = []
    scheduled_fanout_apis = {
        recipe.api_name for recipe in SCHEDULED_FANOUT_RECIPES
    }
    for contract in catalog.list():
        if not contract.collectable:
            continue
        policy = policies.get(contract.api_name)
        tables = sorted(implementation_tables.get(contract.api_name, ()))
        raw_rows = raw.get(contract.api_name, {}).get("rows", 0)
        normalized_rows = sum(table_counts.get(table, 0) for table in tables)
        positive = raw_rows > 0 or normalized_rows > 0
        automatic = (
            contract.api_name in DEDICATED_SCHEDULED_APIS
            or policy.automatic_safe
            or contract.api_name in scheduled_fanout_apis
        )
        rows.append(
            {
                "api_name": contract.api_name,
                "implementation_mode": contract.implementation.get("mode"),
                "automatic_scheduling": automatic,
                "raw_rows": raw_rows,
                "normalized_tables": tables,
                "normalized_rows": normalized_rows,
                "successful_jobs": jobs.get(contract.api_name, {}).get("successful_jobs", 0),
                "last_success_at": jobs.get(contract.api_name, {}).get("last_success_at"),
                "last_raw_at": raw.get(contract.api_name, {}).get("last_at"),
                "data_status": "positive_rows" if positive else "no_positive_row_evidence",
            }
        )

    return {
        "generated_at": business_now(),
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
        f"| Token 可采集接口 | {summary['collectable_interfaces']} |",
        f"| 已实现接口 | {summary['implemented_interfaces']} |",
        f"| 已自动编排接口 | {summary['automatically_scheduled_interfaces']} |",
        f"| 当前有正行数证据 | {summary['interfaces_with_positive_rows']} |",
        f"| 当前无正行数证据 | {summary['interfaces_without_positive_row_evidence']} |",
        "",
        "| API | 实现模式 | 自动编排 | 原始行 | 规范化行 | 数据状态 |",
        "|---|---|---:|---:|---:|---|",
    ]
    for item in report["interfaces"]:
        lines.append(
            f"| `{item['api_name']}` | {item['implementation_mode']} | "
            f"{'是' if item['automatic_scheduling'] else '否'} | "
            f"{item['raw_rows']} | {item['normalized_rows']} | {item['data_status']} |"
        )
    markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--json",
        type=Path,
        default=PROJECT_ROOT / "reports" / "tushare_data_presence.json",
    )
    parser.add_argument(
        "--markdown",
        type=Path,
        default=PROJECT_ROOT / "reports" / "tushare_data_presence.md",
    )
    arguments = parser.parse_args()
    report = build_report()
    arguments.json.parent.mkdir(parents=True, exist_ok=True)
    arguments.markdown.parent.mkdir(parents=True, exist_ok=True)
    write_report(report, arguments.json, arguments.markdown)
    print(json.dumps(report["summary"], ensure_ascii=False))


if __name__ == "__main__":
    main()
