# Claw Quant Data 文档

人工维护的正文只保留五份，按阅读顺序如下：

| 文档 | 内容 | 主要读者 |
|---|---|---|
| [项目 README](../README.md) | 定位、安装、运行、备份、Dashboard 和测试 | 所有使用者 |
| [系统架构](ARCHITECTURE.md) | 系统边界、五层结构、API 分区和权威状态入口 | 产品负责人、架构师、开发者 |
| [数据生产与质量](DATA_PIPELINE.md) | 采集器、任务/节点、重试、审计、数据日历和查询治理 | 数据工程、运维、DBA |
| [数据来源](DATA_SOURCES.md) | 多来源模型、本地优先、公开 Connector、蚂蚁数据源和扩展流程 | 数据平台开发者、审计人员 |
| [研究 API](RESEARCH_API.md) | 股票、板块、宏观、ETF、投资日历和指标语义 | Agent、研究应用开发者 |
| [CLI](CLI.md) | REST 对应的只读命令和示例 | 人类研究员、自动化脚本作者 |

## 机器契约

机器生成文件不算人工文档，不应复制拆分：

- [Tushare 接口索引](tushare/README.md)与 [JSON 契约](tushare/contracts.json)；
- [Tushare 标准表索引](tushare/tables/README.md)与[表契约](tushare/tables/contracts.json)；
- [Tushare 官方补充契约](tushare/official_contract_supplements.json)；
- [蚂蚁数据源路由契约](ant_data/route-contracts.json)。

## 运行报告

`reports/` 是带生成时间的现场快照，不是设计文档。当前状态优先查 API 或重新运行生成器：

| 报告 | 当前入口/生成器 |
|---|---|
| 数据集严格审计 | `GET /api/v1/ops/data-health` / `scripts/generate_dataset_audit_report.py` |
| Tushare 数据落地 | `scripts/report_tushare_data_presence.py` |
| 数据源优先级 | `GET /api/v1/data/source-priorities` / `scripts/generate_source_priority_report.py` |
| 服务目录 | `GET /api/v1/catalog` / `scripts/generate_data_service_inventory.py` |
| Token 权限复核 | `scripts/recheck_tushare_permissions.py`，时间以报告正文为准 |

## 维护规则

1. 只记录当前契约；迁移纪要、事故过程、一次性验收和候选方案不进入 `docs/`。
2. 数量和运行状态由机器接口或生成器提供，不在正文手工同步。
3. 新内容优先补进上述主题文档，不为单个功能再建 Markdown。
4. 修改后运行 `python3 scripts/check_documentation.py` 和 `git diff --check`。
5. `sql/README.md`、`deploy/hibro/README.md` 和第三方 NOTICE 是目录级维护说明，不属于产品文档。
