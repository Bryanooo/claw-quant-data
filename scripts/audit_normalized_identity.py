#!/usr/bin/env python3
"""Audit normalized-table identity evidence without mutating business data."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from psycopg2 import sql

from service.db import get_conn
from service.tushare_normalization import NORMALIZATION_CONTRACTS


def audit() -> dict:
    rows: list[dict] = []
    connection = get_conn()
    try:
        with connection.cursor() as cursor:
            for contract in NORMALIZATION_CONTRACTS.list():
                cursor.execute(
                    sql.SQL("SELECT count(*) FROM {}").format(
                        sql.Identifier(contract.table_name)
                    )
                )
                total_rows = cursor.fetchone()[0]
                identity = contract.business_identity_fields
                if not identity:
                    rows.append(
                        {
                            "api_name": contract.api_name,
                            "table": contract.table_name,
                            "identity_fields": [],
                            "identity_confidence": contract.identity_confidence,
                            "total_rows": total_rows,
                            "null_identity_rows": None,
                            "distinct_identity_groups": None,
                            "conflicting_groups": None,
                            "extra_rows_in_conflicting_groups": None,
                            "max_group_size": None,
                            "evidence_status": (
                                "empty" if total_rows == 0 else "no_identity_contract"
                            ),
                        }
                    )
                    continue

                identity_sql = sql.SQL(", ").join(map(sql.Identifier, identity))
                null_clause = sql.SQL(" OR ").join(
                    sql.SQL("{} IS NULL").format(sql.Identifier(name))
                    for name in identity
                )
                cursor.execute(
                    sql.SQL("SELECT count(*) FROM {} WHERE ").format(
                        sql.Identifier(contract.table_name)
                    )
                    + null_clause
                )
                null_rows = cursor.fetchone()[0]
                cursor.execute(
                    sql.SQL(
                        """
                        SELECT count(*),
                               count(*) FILTER (WHERE group_size > 1),
                               COALESCE(sum(group_size - 1) FILTER (
                                   WHERE group_size > 1
                               ), 0),
                               COALESCE(max(group_size), 0)
                        FROM (
                            SELECT count(*) AS group_size
                            FROM {table}
                            GROUP BY {identity}
                        ) grouped
                        """
                    ).format(
                        table=sql.Identifier(contract.table_name),
                        identity=identity_sql,
                    )
                )
                groups, conflicts, extra_rows, max_group = (
                    int(value) for value in cursor.fetchone()
                )
                if total_rows == 0:
                    status = "empty"
                elif null_rows:
                    status = "nullable_business_identity"
                elif conflicts:
                    status = "non_unique_observed_identity"
                else:
                    status = "unique_in_observed_data"
                rows.append(
                    {
                        "api_name": contract.api_name,
                        "table": contract.table_name,
                        "identity_fields": list(identity),
                        "identity_confidence": contract.identity_confidence,
                        "total_rows": total_rows,
                        "null_identity_rows": null_rows,
                        "distinct_identity_groups": groups,
                        "conflicting_groups": conflicts,
                        "extra_rows_in_conflicting_groups": extra_rows,
                        "max_group_size": max_group,
                        "evidence_status": status,
                    }
                )
    finally:
        connection.close()

    summary = {
        "contracts": len(rows),
        "with_data": sum(item["total_rows"] > 0 for item in rows),
        "unique_in_observed_data": sum(
            item["evidence_status"] == "unique_in_observed_data" for item in rows
        ),
        "non_unique_observed_identity": sum(
            item["evidence_status"] == "non_unique_observed_identity"
            for item in rows
        ),
        "nullable_business_identity": sum(
            item["evidence_status"] == "nullable_business_identity" for item in rows
        ),
        "empty": sum(item["evidence_status"] == "empty" for item in rows),
    }
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "semantics": {
            "technical_primary_key": "_record_hash",
            "storage": "versioned_payload",
            "identity_fields": (
                "logical version-grouping fields; uniqueness is not assumed"
            ),
            "safety": (
                "unique constraints or current-row views require independent "
                "upstream-contract proof in addition to this observed-data audit"
            ),
        },
        "summary": summary,
        "datasets": rows,
    }


def markdown(report: dict) -> str:
    lines = [
        "# 通用标准化表身份审计",
        "",
        f"生成时间：`{report['generated_at']}`",
        "",
        "`_record_hash` 是完整上游 payload 的技术主键；业务身份字段用于版本分组和冲突审计，不承诺数据库唯一。",
        "因此，观察数据唯一也不能单独作为创建唯一约束或 `current` 视图的依据。",
        "",
        "## 汇总",
        "",
        "| 合约 | 有数据 | 当前样本唯一 | 当前样本冲突 | 身份值为空 | 空表 |",
        "| ---: | ---: | ---: | ---: | ---: | ---: |",
        (
            f"| {report['summary']['contracts']} | {report['summary']['with_data']} | "
            f"{report['summary']['unique_in_observed_data']} | "
            f"{report['summary']['non_unique_observed_identity']} | "
            f"{report['summary']['nullable_business_identity']} | "
            f"{report['summary']['empty']} |"
        ),
        "",
        "## 明细",
        "",
        "| 接口 | 身份字段 | 可信度 | 行数 | 冲突组 | 冲突额外行 | 最大组 | 结论 |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: | --- |",
    ]
    for item in report["datasets"]:
        lines.append(
            "| {api_name} | `{identity}` | {confidence} | {total_rows} | {conflicts} | "
            "{extra} | {maximum} | {status} |".format(
                api_name=item["api_name"],
                identity=", ".join(item["identity_fields"]) or "—",
                confidence=item["identity_confidence"],
                total_rows=item["total_rows"],
                conflicts=item["conflicting_groups"]
                if item["conflicting_groups"] is not None
                else "—",
                extra=item["extra_rows_in_conflicting_groups"]
                if item["extra_rows_in_conflicting_groups"] is not None
                else "—",
                maximum=item["max_group_size"]
                if item["max_group_size"] is not None
                else "—",
                status=item["evidence_status"],
            )
        )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json-output", type=Path)
    parser.add_argument("--markdown-output", type=Path)
    args = parser.parse_args()
    report = audit()
    if args.json_output:
        args.json_output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    if args.markdown_output:
        args.markdown_output.write_text(markdown(report), encoding="utf-8")
    if not args.json_output and not args.markdown_output:
        print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
