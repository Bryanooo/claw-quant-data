# 接口服务分层与数据服务三层契约

接口首先按使用者分为四类，避免把研究查询和系统管理混在一起：

1. **研究接口**（默认）：`/api/v1/research/*`、`/stocks/*`、`/sectors/*`；
2. **数据接口**：`/api/v1/datasets/*`、`/interfaces/*`；
3. **运营接口**：`/api/v1/collection*`、`/delivery/*`、`/coverage/*`、`/initialization/*`；
4. **审计接口**：`/api/v1/raw/*`、`/normalization/*`。

前三个数据抽象层则描述数据加工关系，不是四类使用入口的重复菜单：原始事实经
标准化后成为研究对象；运营接口是独立控制面，不参与这条加工链路。

统一服务目录由 `GET /api/v1/catalog` 提供。它返回四类使用入口、三层加工关系、
运营控制面、覆盖指标和 REST 契约；控制台“数据服务”页面也以该目录为唯一事实
来源。`GET /api/v1/data-services` 暂时兼容旧客户端，并已在 OpenAPI 中标记为旧入口。

## 1. 原始审计层

原始层保存每一次 Tushare SDK 请求的参数、状态、响应行数、响应摘要和无损记录。
采集发生在 `query()` 传输边界，因此即使后续字段转换或标准表写入失败，仍可检查
当时上游到底返回了什么。

- `tushare_raw_request`：每一次真实请求，包括有数据、空响应和失败请求；
- `tushare_raw_record`：按接口、逻辑请求和记录内容哈希幂等去重的 JSONB 原文；
- 分页的 `limit` / `offset` 只属于传输请求，不改变逻辑请求身份；
- `token` 等敏感请求参数在落库前强制脱敏；
- 通用采集器和专项采集器使用同一套请求审计，标准表写入逻辑保持独立。

原始层只用于审计、排障、重放和契约升级，不作为日常研究的默认入口。

| REST 接口 | 用途 |
|---|---|
| `GET /api/v1/raw/interfaces` | 查看每个可采接口是否已有原始记录，以及请求成功、空响应、失败统计 |
| `GET /api/v1/raw/{api_name}/requests` | 分页查看真实上游请求和传输结果 |
| `GET /api/v1/raw/{api_name}/records` | 按请求哈希、记录哈希和采集时间查询原始 JSONB |
| `GET /api/v1/raw/{api_name}/coverage` | 查看原始请求与记录覆盖摘要 |
| `GET /api/v1/raw/{api_name}/lineage/{record_hash}` | 从一条原始记录追溯产生它的逻辑请求 |

这里的请求 `success` 只表示 Tushare 成功返回响应，不等同于业务完整性通过。
完整性仍由采集器校验和 Coverage Auditor 判定。

## 2. 标准数据层

标准层是需要底层字段时的数据服务入口：专项接口进入领域表，契约通用接口进入强类型
`tushare_norm_*` 表，并通过 Dataset Registry 暴露稳定字段、日期、主键、过滤器和
分页契约。

| REST 接口 | 用途 |
|---|---|
| `GET /api/v1/datasets` | 发现已登记的数据资产 |
| `GET /api/v1/datasets/{name}` | 查看表结构、业务身份、日期列和允许过滤器 |
| `GET /api/v1/datasets/{name}/records` | 查询标准化记录，支持 `as_of` 的数据集可做历史时点约束 |
| `GET /api/v1/interfaces` | 从上游接口视角查看实现方式及其对应数据集 |
| `GET /api/v1/interfaces/{api_name}/records` | 查询契约通用接口的强类型标准记录 |
| `GET /api/v1/freshness` | 查看数据最新日期与时效状态 |
| `GET /api/v1/coverage` | 查看日期或报告期完整性证据 |

研究接口不能满足需求时才下钻这一层；Agent 不应默认自行拼装跨表研究口径，更不应
解析原始 JSONB。

## 3. 研究就绪层

研究层把多个标准数据集组合成稳定的研究对象，返回来源、历史时点、质量状态和
缺口，而不是把“查表和拼表”推给每一个 Agent。

当前已落地：

- 个股快照、个股 Research Pack；
- 股票所属板块和同行发现；
- 板块搜索、快照、成分和 Research Pack；
- 投资日历范围和单日事件明细。
- `/api/v1/research/*` 下的基本面、估值、技术面、资金、事件研究、市场宽度和板块轮动。

下一阶段按优先级补充：

1. 统一证券搜索与代码解析；
2. 财务指标时序、同比/环比与公告时点安全视图；
3. 市场/行业横截面排名和估值分位；
4. 事件时间线、公司行动和风险提示；
5. 面向 Agent 的证据引用、批量查询和研究上下文导出。

研究层只组合标准层，不直接依赖原始 JSONB。这样契约修复、字段升级和重放都不会
迫使 Agent 改写研究逻辑。

## 4. 运营控制面（不属于数据加工层）

运营控制面回答“数据是怎样生产出来、是否完成、失败后如何恢复”，与研究接口回答的
“这家公司或板块怎么样”严格分开。主要入口包括：

| REST 接口 | 用途 |
|---|---|
| `GET /api/v1/collection-overview` | 当前运营总览和真实未恢复异常 |
| `GET /api/v1/collection-jobs` | 全量执行实例及自动尝试/人工重试关系 |
| `GET /api/v1/delivery/data-calendar` | 按数据日期查看完整性，不使用任务日期替代 |
| `GET /api/v1/data-health` | 数据集时效和质量状态 |
| `GET /api/v1/initialization` | 初始化和历史补采进度 |
