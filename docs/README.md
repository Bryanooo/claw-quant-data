# 文档导航与维护规则

这里仅保留当前有效的契约、架构和操作说明。运行状态不写死在设计文档里；队列、失败、
数据覆盖和 V2 状态分别以 Dashboard、运维 API 和可重复生成的最新审计报告为准。

## 入门

- [项目总览](../README.md)
- [CLI](CLI.md)
- [研究 API](RESEARCH_API.md)
- [研究能力矩阵](RESEARCH_CAPABILITIES.md)
- [接口分层](DATA_SERVICE_LAYERS.md)

## 数据与采集

- [采集器架构](COLLECTOR_ARCHITECTURE.md)：采集器内部契约、分页和写入边界。
- [统一工作流与执行模型](COLLECTION_EXECUTION_MODEL.md)：V2 任务、节点、状态和迁移方案。
- [V2 切换与运维](V2_CUTOVER_2026-09-29.md)：切换口径、发布、恢复演练和回滚边界。
- [数据就绪与审计](DATA_ASSURANCE.md)：任务状态、数据状态、历史义务和研究验收口径。
- [多数据源基础层](MULTI_SOURCE_ARCHITECTURE.md)：来源、Connector、原始证据和扩展边界。
- [数据查询治理](DATA_API_QUERY_GOVERNANCE.md)：过滤、游标分页和索引发布规则。
- [Tushare 接口目录](tushare/README.md)：接口、权限、实现和代码链接；完整输入输出契约保存在同目录 JSON。

## 研究能力

- [宏观与行业研究](MACRO_INDUSTRY_RESEARCH.md)
- [跨资产研究](CROSS_ASSET_RESEARCH.md)
- [ETF 资金流与证据分级](ETF_STATE_TEAM_RESEARCH.md)
- [投资日历](INVESTMENT_CALENDAR.md)
- [Agent 与 Skill 架构](AGENT_RESEARCH_SKILL_ARCHITECTURE.md)
- [免费替代数据源评估](FREE_DATA_SOURCE_ALTERNATIVES.md)

## 可重复生成的报告

- [最新全量数据集审计](../reports/dataset_audit_latest.md)
- [最新 Tushare 数据落地证据](../reports/tushare_data_presence_latest.md)
- [Tushare 权限复核](../reports/tushare_permission_recheck.md)

报告目录不保存逐日快照历史。同一类报告覆盖固定的 `latest` 文件；需要追溯时使用 Git。
事故中形成的长期规则必须回写到架构、可靠性或数据审计文档，之后删除一次性事故报告。

## 维护约束

1. 文档只描述当前契约或明确标注的目标架构，不把一次任务成功写成长期事实。
2. 接口数量、队列数量、缺口数量和运行进度来自 API 或生成脚本，不手工复制到多个文件。
3. 删除或重命名文档时必须执行 `python scripts/check_documentation.py`；CI 会检查相对链接，
   并拒绝在 `reports/` 新增按日期命名的快照。
4. 批量接口和表契约使用统一目录加机器 JSON，不再生成“一接口/一表一 Markdown”。
