#!/usr/bin/env python3
"""Generate the reviewed Tushare-DB/Financial-Data precedence matrix."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from service.data_service.source_policy import (
    LOCAL_DB_FIRST,
    source_policy_catalog,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--markdown", default="reports/source_priority_matrix_latest.md")
    parser.add_argument("--json", dest="json_path", default="reports/source_priority_matrix_latest.json")
    args = parser.parse_args()

    policies = source_policy_catalog()
    generated_at = datetime.now(timezone.utc).isoformat()
    local_count = sum(item.preferred_read == LOCAL_DB_FIRST for item in policies)
    ready_count = sum(
        item.adapter_status.startswith("partial_ready") for item in policies
    )
    payload = {
        "generated_at": generated_at,
        "policy": "local canonical DB first; quota source only by explicit policy",
        "summary": {
            "routes": len(policies),
            "local_db_first": local_count,
            "financial_data_first": len(policies) - local_count,
            "active_implicit_fallbacks": 0,
            "active_canonical_fallbacks": ready_count,
        },
        "items": [item.as_dict() for item in policies],
    }

    json_path = Path(args.json_path)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    lines = [
        "# 数据源优先级矩阵",
        "",
        f"> 生成时间：`{generated_at}`。机器可读版本见 "
        "[`source_priority_matrix_latest.json`](source_priority_matrix_latest.json)。",
        "",
        "## 统一规则",
        "",
        "- 外部消费者使用规范数据集或研究接口，不直接依赖供应商字段。",
        "- `local_db_first`：先读已经由 Tushare 定时采集并写入 DB 的规范数据；"
        "只有请求切片缺失或超过新鲜度 SLA，且 Financial Data 规范适配器通过契约测试后，才允许消耗额度回退。",
        "- `financial_data_first`：当前没有等价本地规范数据集，或能力本身是显式实时查询；"
        "返回外部前仍必须经过规范字段、代码、日期和单位适配。",
        "- 当前隐式回退数为 **0**。仅规范接口可触发已通过测试的有限回退；"
        "`adapter_required` 不是已启用，避免供应商原生模型混入统一接口。",
        "",
        "## 汇总",
        "",
        "| Financial Data 路由 | 本地 DB 优先 | Financial Data 优先 | 已启用规范适配 |",
        "|---:|---:|---:|---:|",
        f"| {len(policies)} | {local_count} | {len(policies) - local_count} | {ready_count} |",
        "",
        "## 完整路由清单",
        "",
        "| 路由 | 读取优先级 | 本地规范数据集 | Financial Data 角色 | 规范化状态 | 本地适用范围 |",
        "|---|---|---|---|---|---|",
    ]
    for item in policies:
        datasets = ", ".join(f"`{name}`" for name in item.local_datasets) or "—"
        lines.append(
            f"| `{item.route}` | `{item.preferred_read}` | {datasets} | "
            f"`{item.financial_data_role}` | `{item.adapter_status}` | "
            f"{item.local_scope} |"
        )
    markdown_path = Path(args.markdown)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
