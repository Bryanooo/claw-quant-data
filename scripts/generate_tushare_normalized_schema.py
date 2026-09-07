#!/usr/bin/env python3
"""Generate the immutable SQL migration and per-table normalization docs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from service.tushare_normalization import NORMALIZATION_CONTRACTS


METADATA_COLUMNS = (
    ("_record_hash", "CHAR(64)", "原始 payload 的 SHA-256 技术主键"),
    ("_request_hash", "CHAR(64)", "去除分页参数后的请求 SHA-256"),
    ("_source_doc_id", "INTEGER", "Tushare 官方文档编号"),
    ("_source_collected_at", "TIMESTAMPTZ", "原始数据采集时间"),
    ("_first_seen_at", "TIMESTAMPTZ", "首次标准化时间"),
    ("_last_seen_at", "TIMESTAMPTZ", "最近一次标准化时间"),
    ("_schema_version", "INTEGER", "标准化契约版本"),
    ("_extra_payload", "JSONB", "契约外字段，保留且触发 Schema Drift"),
)


def quote(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def render_migration() -> str:
    statements = [
        "-- Generated typed standard layer for contract-driven Tushare interfaces.",
        "-- Source: docs/tushare/contracts.json; generator: scripts/generate_tushare_normalized_schema.py",
        "",
        "CREATE TABLE IF NOT EXISTS sys_tushare_normalization_run (\n"
        "    normalization_run_id BIGSERIAL PRIMARY KEY,\n"
        "    api_name VARCHAR(128) NOT NULL,\n"
        "    request_hash CHAR(64) NOT NULL,\n"
        "    schema_version INTEGER NOT NULL,\n"
        "    status VARCHAR(16) NOT NULL CHECK (status IN ('complete', 'partial', 'failed')),\n"
        "    raw_rows INTEGER NOT NULL,\n"
        "    normalized_rows INTEGER NOT NULL,\n"
        "    quarantined_rows INTEGER NOT NULL,\n"
        "    unknown_fields JSONB NOT NULL DEFAULT '[]'::jsonb,\n"
        "    missing_fields JSONB NOT NULL DEFAULT '[]'::jsonb,\n"
        "    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()\n"
        ");",
        "CREATE INDEX IF NOT EXISTS idx_tushare_normalization_run_api_created "
        "ON sys_tushare_normalization_run(api_name, created_at DESC);",
        "",
        "CREATE TABLE IF NOT EXISTS sys_tushare_normalization_error (\n"
        "    api_name VARCHAR(128) NOT NULL,\n"
        "    request_hash CHAR(64) NOT NULL,\n"
        "    record_hash CHAR(64) NOT NULL,\n"
        "    payload JSONB NOT NULL,\n"
        "    error_code VARCHAR(64) NOT NULL,\n"
        "    error_message TEXT NOT NULL,\n"
        "    attempts INTEGER NOT NULL DEFAULT 1,\n"
        "    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),\n"
        "    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),\n"
        "    resolved_at TIMESTAMPTZ,\n"
        "    PRIMARY KEY (api_name, request_hash, record_hash)\n"
        ");",
        "",
        "CREATE TABLE IF NOT EXISTS sys_tushare_schema_drift (\n"
        "    api_name VARCHAR(128) NOT NULL,\n"
        "    field_name VARCHAR(128) NOT NULL,\n"
        "    drift_type VARCHAR(32) NOT NULL,\n"
        "    severity VARCHAR(16) NOT NULL,\n"
        "    occurrences BIGINT NOT NULL DEFAULT 1,\n"
        "    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),\n"
        "    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),\n"
        "    resolved_at TIMESTAMPTZ,\n"
        "    PRIMARY KEY (api_name, field_name, drift_type)\n"
        ");",
        "",
    ]
    for contract in NORMALIZATION_CONTRACTS.list():
        columns = [
            "    _record_hash CHAR(64) PRIMARY KEY",
            "    _request_hash CHAR(64) NOT NULL",
            "    _source_doc_id INTEGER",
            "    _source_collected_at TIMESTAMPTZ NOT NULL",
            "    _first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW()",
            "    _last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW()",
            f"    _schema_version INTEGER NOT NULL DEFAULT {contract.schema_version}",
            "    _extra_payload JSONB NOT NULL DEFAULT '{}'::jsonb",
            *(f"    {quote(field.name)} {field.sql_type}" for field in contract.fields),
        ]
        table = quote(contract.table_name)
        statements.extend(
            [
                f"CREATE TABLE IF NOT EXISTS {table} (\n" + ",\n".join(columns) + "\n);",
                f"CREATE INDEX IF NOT EXISTS {quote('idx_' + contract.table_name + '_source')} "
                f"ON {table} (_source_collected_at DESC);",
            ]
        )
        if contract.date_column:
            statements.append(
                f"CREATE INDEX IF NOT EXISTS {quote('idx_' + contract.table_name + '_date')} "
                f"ON {table} ({quote(contract.date_column)} DESC);"
            )
        statements.append(
            f"COMMENT ON TABLE {table} IS {literal(contract.title + '；契约驱动标准化表')} ;"
        )
        for field in contract.fields:
            if field.description:
                statements.append(
                    f"COMMENT ON COLUMN {table}.{quote(field.name)} IS "
                    f"{literal(field.description)};"
                )
        statements.append("")
    return "\n".join(statements).rstrip() + "\n"


def render_index() -> str:
    lines = [
        "# Tushare 通用接口标准化表",
        "",
        "本目录由接口契约生成。每个表均保留原始记录哈希、采集时间、契约版本和契约外字段。",
        "原始 JSON 仍保存在 `tushare_raw_record`，标准化失败记录进入",
        "`sys_tushare_normalization_error`，字段漂移进入 `sys_tushare_schema_drift`。",
        "",
        "| 接口 | PostgreSQL 表 | 字段数 | 主日期字段 | 文档 |",
        "|---|---|---:|---|---|",
    ]
    for contract in NORMALIZATION_CONTRACTS.list():
        lines.append(
            f"| `{contract.api_name}` | `{contract.table_name}` | {len(contract.fields)} | "
            f"`{contract.date_column or '-'}` | [{contract.api_name}.md]({contract.api_name}.md) |"
        )
    return "\n".join(lines) + "\n"


def render_doc(contract) -> str:
    lines = [
        f"# `{contract.api_name}` 标准化表契约",
        "",
        f"- 功能：{contract.description}",
        f"- PostgreSQL 表：`{contract.table_name}`",
        f"- 契约版本：`{contract.schema_version}`",
        f"- 技术主键：`_record_hash`（原始 payload SHA-256）",
        f"- 主日期字段：`{contract.date_column or '无'}`",
        f"- 必填身份字段：`{', '.join(contract.identity_fields) or '无'}`",
        f"- 业务身份字段：`{', '.join(contract.business_identity_fields) or '未配置'}`",
        f"- 业务身份可信度：`{contract.identity_confidence}`",
        (
            f"- 当前数据视图：`tushare_current_{contract.api_name}`"
            if contract.identity_confidence == "contract_reviewed"
            else "- 当前数据视图：未创建（业务身份仍为启发式，REST 保留全部 payload 版本）"
        ),
        f"- 原始数据表：`tushare_raw_record`（`api_name={contract.api_name}`）",
        f"- REST：`GET /api/v1/datasets/{contract.api_name}/records`",
        f"- 接口 REST：`GET /api/v1/interfaces/{contract.api_name}/records`",
        "- 标准化实现：[service/tushare_normalization.py](../../../service/tushare_normalization.py)",
        "",
        "## 业务字段",
        "",
        "| 字段 | 上游类型 | PostgreSQL 类型 | 说明 |",
        "|---|---|---|---|",
    ]
    for field in contract.fields:
        description = field.description.replace("|", "\\|")
        lines.append(
            f"| `{field.name}` | `{field.upstream_type}` | `{field.sql_type}` | {description} |"
        )
    lines.extend(
        [
            "",
            "## 系统字段",
            "",
            "| 字段 | PostgreSQL 类型 | 说明 |",
            "|---|---|---|",
            *(f"| `{name}` | `{sql_type}` | {description} |" for name, sql_type, description in METADATA_COLUMNS),
            "",
            "## 稳定性契约",
            "",
            "- 原始记录先提交，标准化失败不会造成上游响应丢失。",
            "- 同一 payload 使用 `_record_hash` 幂等 UPSERT，重复采集只更新最近观测时间。",
            "- 契约外字段完整保存在 `_extra_payload` 并登记 Schema Drift。",
            "- 类型转换失败的整行进入隔离表，修复契约后可以从原始层重放。",
            "- 未经确认的业务键不会被猜测成唯一约束；当前主键是可验证的技术主键。",
            "- `contract_reviewed` 接口的 REST 查询使用 `tushare_current_*` 视图；原始标准表仍保留全部版本。",
            "",
        ]
    )
    return "\n".join(lines)


def update_interface_doc(contract) -> None:
    path = PROJECT_ROOT / "docs" / "tushare" / "interfaces" / f"{contract.api_name}.md"
    if not path.exists():
        return
    text = path.read_text(encoding="utf-8")
    heading = "## claw-quant 存储契约"
    if heading not in text:
        return
    prefix, remainder = text.split(heading, 1)
    marker = "> 权限状态来自实际 Token 探测"
    suffix = ""
    if marker in remainder:
        _, tail = remainder.split(marker, 1)
        suffix = f"\n> {marker.removeprefix('> ')}{tail.lstrip()}"
    replacement = f"""{heading}

该接口采用两阶段持久化：上游响应先无损写入 `tushare_raw_record`，随后按契约转换到
强类型标准表 `{contract.table_name}`。标准表字段、类型、日期列、系统血缘字段和
稳定性规则见[标准化表契约](../tables/{contract.api_name}.md)。转换失败记录进入
`sys_tushare_normalization_error`，契约外字段保存在 `_extra_payload` 并登记到
`sys_tushare_schema_drift`；原始响应始终可用于修复后重放。
"""
    path.write_text(prefix + replacement.rstrip() + "\n" + suffix, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--migration", default="021_tushare_normalized_tables.sql")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--docs-only", action="store_true")
    args = parser.parse_args()
    migration = PROJECT_ROOT / "sql" / "migrations" / args.migration
    if not args.docs_only:
        if migration.exists() and not args.force:
            raise SystemExit(f"refusing to overwrite existing migration: {migration}")
        migration.write_text(render_migration(), encoding="utf-8")

    docs_dir = PROJECT_ROOT / "docs" / "tushare" / "tables"
    docs_dir.mkdir(parents=True, exist_ok=True)
    (docs_dir / "README.md").write_text(render_index(), encoding="utf-8")
    contracts_payload = []
    for contract in NORMALIZATION_CONTRACTS.list():
        (docs_dir / f"{contract.api_name}.md").write_text(
            render_doc(contract), encoding="utf-8"
        )
        update_interface_doc(contract)
        contracts_payload.append(
            {
                "api_name": contract.api_name,
                "table_name": contract.table_name,
                "schema_version": contract.schema_version,
                "date_column": contract.date_column,
                "identity_fields": list(contract.identity_fields),
                "business_identity_fields": list(contract.business_identity_fields),
                "identity_confidence": contract.identity_confidence,
                "current_view": (
                    f"tushare_current_{contract.api_name}"
                    if contract.identity_confidence == "contract_reviewed"
                    else None
                ),
                "fields": [
                    {
                        "name": field.name,
                        "upstream_type": field.upstream_type,
                        "sql_type": field.sql_type,
                        "description": field.description,
                    }
                    for field in contract.fields
                ],
            }
        )
    (docs_dir / "contracts.json").write_text(
        json.dumps(
            {"schema_version": 1, "tables": contracts_payload},
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"generated {len(contracts_payload)} tables and docs")


if __name__ == "__main__":
    main()
