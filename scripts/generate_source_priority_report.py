#!/usr/bin/env python3
"""Generate the reviewed Tushare-DB/Financial-Data precedence matrix."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from service.data_service.source_policy import (
    source_policy_catalog,
    source_policy_summary,
)
from service.data_service.provider_equivalence import (
    financial_tushare_catalog,
    financial_tushare_summary,
    tushare_financial_reverse_catalog,
    tushare_financial_reverse_summary,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--markdown", default="reports/source_priority_matrix_latest.md")
    parser.add_argument("--json", dest="json_path", default="reports/source_priority_matrix_latest.json")
    args = parser.parse_args()

    policies = source_policy_catalog()
    generated_at = datetime.now(timezone.utc).isoformat()
    summary = source_policy_summary(policies)
    equivalence_summary = financial_tushare_summary(financial_tushare_catalog())
    reverse_items = tushare_financial_reverse_catalog()
    reverse_summary = tushare_financial_reverse_summary(reverse_items)
    payload = {
        "generated_at": generated_at,
        "policy": "local canonical DB first; quota source only by explicit policy",
        "summary": summary,
        "provider_equivalence_summary": equivalence_summary,
        "tushare_reverse_summary": reverse_summary,
        "tushare_endpoints": list(reverse_items),
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
        "当前只能显式调用供应商网关；若要进入规范/研究接口，必须先完成字段、代码、"
        "日期和单位适配。",
        "- 当前隐式回退数为 **0**。仅规范接口可触发已通过测试的有限回退；"
        "`adapter_required` 不是已启用，避免供应商原生模型混入统一接口。",
        "",
        "## 汇总",
        "",
        "| Financial Data 路由 | 当前依赖 Financial Data | 实时必须依赖 | 无本地规范等价 | 本地优先且可回退 | 本地重叠但适配待完成 |",
        "|---:|---:|---:|---:|---:|---:|",
        f"| {summary['routes']} | {summary['financial_data_required_now']} | "
        f"{summary['financial_data_realtime_required']} | "
        f"{summary['financial_data_primary_no_local_canonical']} | "
        f"{summary['local_first_canonical_fallback_ready']} | "
        f"{summary['local_overlap_adapter_pending']} |",
        "",
        "> “无本地规范等价”描述的是当前系统状态，不等同于已经证明 Tushare 完全没有"
        "语义相近接口；其中也可能有尚未完成映射和标准化的缺口。",
        "",
        "## 供应商语义能力四分类",
        "",
        "这组数字回答供应商能否提供同一业务事实，与本地是否已经落表、当前 Token "
        "是否有权限相互独立。只有覆盖完整 Financial Data 合同才算等价；局部市场或字段"
        "重叠仍归入 `financial_data_only`。",
        "",
        "| Financial Data 路由 | Tushare 直接等价 | Tushare 确定性派生 | Tushare 公告解析 | Financial Data 必需 | 当前 Token 可完整执行 | 部分 Tushare 重叠 |",
        "|---:|---:|---:|---:|---:|---:|---:|",
        f"| {equivalence_summary['financial_data_routes']} | "
        f"{equivalence_summary['tushare_direct']} | "
        f"{equivalence_summary['tushare_derived']} | "
        f"{equivalence_summary['tushare_announcement_parse']} | "
        f"{equivalence_summary['financial_data_only']} | "
        f"{equivalence_summary['current_token_ready_routes']} | "
        f"{equivalence_summary['partial_tushare_overlap_routes']} |",
        "",
        "## Financial Data ↔ Tushare 逐条映射",
        "",
        "| Financial Data 路由 | 四类归属 | 完整等价所需 Tushare 接口 | 仅局部重叠接口 | 当前 Token 完整可用 | 判定依据 |",
        "|---|---|---|---|---|---|",
    ]
    for item in policies:
        provider = item.as_dict()["provider_equivalence"]
        interfaces = ", ".join(
            f"`{entry['api_name']}`({entry['permission']})"
            for entry in provider["tushare_interfaces"]
        ) or "—"
        related = ", ".join(
            f"`{entry['api_name']}`({entry['permission']})"
            for entry in provider["related_tushare_interfaces"]
        ) or "—"
        rationale = provider["rationale"].replace("|", "\\|")
        lines.append(
            f"| `{item.route}` | `{provider['equivalence_class']}` | "
            f"{interfaces} | {related} | "
            f"{'是' if provider['current_token_ready'] else '否'} | {rationale} |"
        )
    lines.extend([
        "",
        "## Tushare 244 条契约反向映射",
        "",
        "| Tushare 契约 | 作为完整等价输入 | 仅局部重叠 | 无 Financial Data 对应 |",
        "|---:|---:|---:|---:|",
        f"| {reverse_summary['tushare_contracts']} | "
        f"{reverse_summary['full_equivalence_input']} | "
        f"{reverse_summary['partial_overlap_only']} | "
        f"{reverse_summary['no_financial_data_counterpart']} |",
        "",
        "| Tushare 接口 | 标题 | Token 权限 | 可安全采集 | 映射状态 | 完整等价 Financial 路由 | 局部重叠 Financial 路由 |",
        "|---|---|---|---|---|---|---|",
    ])
    for item in reverse_items:
        full_routes = ", ".join(
            f"`{route}`" for route in item["full_equivalence_routes"]
        ) or "—"
        partial_routes = ", ".join(
            f"`{route}`" for route in item["partial_overlap_routes"]
        ) or "—"
        lines.append(
            f"| `{item['api_name']}` | {item['title']} | "
            f"{item['permission']} | {'是' if item['collectable'] else '否'} | "
            f"`{item['mapping_status']}` | "
            f"{full_routes} | {partial_routes} |"
        )
    lines.extend([
        "",
        "## 完整路由清单",
        "",
        "| 路由 | 依赖分类 | 当前必须依赖 FD | 对外访问 | 本地规范数据集 | 规范化状态 |",
        "|---|---|---|---|---|---|",
    ])
    for item in policies:
        datasets = ", ".join(f"`{name}`" for name in item.local_datasets) or "—"
        lines.append(
            f"| `{item.route}` | `{item.dependency_class}` | "
            f"{'是' if item.requires_financial_data else '否'} | "
            f"`{item.public_access}` | {datasets} | `{item.adapter_status}` |"
        )
    markdown_path = Path(args.markdown)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
