"""One machine-readable statement of what Claw Quant Data is and is not.

The dashboard and documentation link to this contract instead of copying
independently maintained totals.  Counts are derived from the same registries
that serve the public catalog, source policy, and research capability APIs.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Any

from service.data_service.provider_equivalence import financial_tushare_summary
from service.data_service.source_policy import source_policy_summary
from service.research.catalog import capability_catalog
from service.research.external_provider import (
    FUNDAMENTAL_ROUTES,
    REALTIME_ROUTES,
    TECHNICAL_ROUTES,
)
from service.source_connectors.registry import SOURCE_REGISTRY
from service.tushare_catalog import TushareInterfaceCatalog


SYSTEM_OVERVIEW_SCHEMA = "claw-quant-system-overview/v1"


def _tushare_inventory() -> dict[str, Any]:
    contracts = TushareInterfaceCatalog().list()
    permission_statuses = Counter(
        str(item.permission.get("status") or "unknown") for item in contracts
    )
    return {
        "contracts": len(contracts),
        "collectable_contracts": sum(item.collectable for item in contracts),
        "permission_statuses": dict(sorted(permission_statuses.items())),
        "role": "scheduled historical and routine bulk source",
        "persistence": "PostgreSQL canonical datasets plus request audit",
    }


def build_system_overview(
    *,
    public_catalog: dict[str, Any],
    data_health: dict[str, Any],
) -> dict[str, Any]:
    """Build the canonical cross-layer summary from governed registries."""

    source_policy = source_policy_summary()
    equivalence = financial_tushare_summary()
    research = capability_catalog({})
    research_routes = sorted({
        *FUNDAMENTAL_ROUTES.values(),
        *TECHNICAL_ROUTES.values(),
        *REALTIME_ROUTES.values(),
    })
    public = public_catalog.get("summary", {})
    health_summary = data_health.get("summary", {})
    sources = SOURCE_REGISTRY.list_sources()

    return {
        "schema_version": SYSTEM_OVERVIEW_SCHEMA,
        "generated_at": datetime.now(timezone.utc),
        "positioning": {
            "product": "Claw Quant Data",
            "statement": (
                "面向个人与研究 Agent 的可审计金融数据底座；负责采集、标准化、"
                "完整性核验和研究数据服务，不负责组合回测与交易执行。"
            ),
            "agent_entrypoint": "/api/v1/research",
            "primary_data_rule": (
                "Tushare 定时入库且审计通过的数据是确定性主口径；蚂蚁数据源 "
                "只在明确契约中按需补充，不能覆盖本地事实。"
            ),
        },
        "authorities": {
            "system_overview": "/api/v1/system/overview",
            "public_service_catalog": "/api/v1/catalog",
            "research_capabilities": "/api/v1/research/capabilities",
            "source_supply_matrix": "/api/v1/data/source-priorities",
            "runtime_data_health": "/api/v1/ops/data-health",
            "rule": "总览只汇总；服务、研究方法、来源映射和运行状态分别以上述接口为唯一明细口径。",
        },
        "architecture": [
            {
                "id": "sources",
                "order": 1,
                "title": "上游来源",
                "description": "Tushare 批量采集、蚂蚁数据源 按需查询及官方公开来源。",
            },
            {
                "id": "production",
                "order": 2,
                "title": "数据生产",
                "description": "版本化任务定义、执行节点、重试、租约与独立完整性校验。",
            },
            {
                "id": "canonical",
                "order": 3,
                "title": "规范数据",
                "description": "PostgreSQL 业务表、统一代码/日期/单位、请求审计和数据状态。",
            },
            {
                "id": "research",
                "order": 4,
                "title": "研究服务",
                "description": "基本面、技术面、板块、宏观及事件的稳定 REST/CLI 契约。",
            },
            {
                "id": "agents",
                "order": 5,
                "title": "Agent 与 Skill",
                "description": "只消费研究契约和质量证据，不直接解析供应商原始响应。",
            },
        ],
        "inventory": {
            "registered_sources": len(sources),
            "tushare": _tushare_inventory(),
            "financial_data": {
                "whitelisted_routes": source_policy["routes"],
                "canonical_adapters_ready": source_policy[
                    "local_first_canonical_fallback_ready"
                ],
                "local_overlap_adapters_pending": source_policy[
                    "local_overlap_adapter_pending"
                ],
                "realtime_required_routes": source_policy[
                    "financial_data_realtime_required"
                ],
                "no_local_canonical_routes": source_policy[
                    "financial_data_primary_no_local_canonical"
                ],
                "research_evidence_routes": len(research_routes),
                "research_route_list": research_routes,
                "persistence": "request metadata only; provider response records are not stored",
            },
            "public_services": {
                "raw_interfaces": int(public.get("raw_interfaces", 0)),
                "standard_datasets": int(public.get("standard_datasets", 0)),
                "research_endpoints": int(public.get("research_endpoints", 0)),
            },
            "research": {
                "baseline_techniques": research["summary"]["baseline_techniques"],
                "currently_served_techniques": research["summary"]["currently_served"],
                "technique_gaps": len(research["techniques"]["gaps"]),
                "stable_agent_endpoints": research["summary"]["agent_endpoints"],
            },
            "provider_equivalence": {
                "tushare_direct": equivalence["tushare_direct"],
                "tushare_derived": equivalence["tushare_derived"],
                "tushare_announcement_parse": equivalence[
                    "tushare_announcement_parse"
                ],
                "financial_data_only": equivalence["financial_data_only"],
            },
        },
        "runtime": {
            "status": data_health.get("status", "unknown"),
            "engine": "current_workflow_engine",
            "generated_at": data_health.get("generated_at"),
            "summary": dict(health_summary),
            "issues": list(data_health.get("issues", [])),
            "details_url": "/api/v1/ops/data-health",
        },
        "number_definitions": [
            {
                "name": "蚂蚁数据源 白名单路由",
                "value": source_policy["routes"],
                "meaning": "允许调用的供应商原始能力，不等于对 Agent 的研究接口数。",
            },
            {
                "name": "规范适配器就绪",
                "value": source_policy["local_first_canonical_fallback_ready"],
                "meaning": "已完成代码、日期、单位和字段映射的本地优先规范回退。",
            },
            {
                "name": "研究证据路由",
                "value": len(research_routes),
                "meaning": "已被基本面、技术面或研究资料包治理后使用的供应商路由。",
            },
            {
                "name": "对外研究接口",
                "value": int(public.get("research_endpoints", 0)),
                "meaning": "供用户和 Agent 调用的稳定研究 REST 入口。",
            },
        ],
        "boundaries": [
            "163 条供应商路由、规范适配器和研究接口属于三个不同维度，不能相互等同。",
            "蚂蚁数据源 原始响应不持久化；当前按进程 TTL 缓存并保存脱敏请求审计。",
            "供应商技术指标复权口径未声明时只作交叉验证，本地可复现计算仍是主结论。",
            "因子组合、策略回测、组合管理和交易执行不属于本系统当前职责。",
        ],
    }
