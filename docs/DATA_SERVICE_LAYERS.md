# 接口服务分层与数据服务三层契约

接口首先按使用者分为四类，避免把研究查询和系统管理混在一起：

1. **研究接口**（默认）：`/api/v1/research/*`；
2. **数据接口**：`/api/v1/data/*`；
3. **运营接口**：`/api/v1/ops/*`；
4. **审计接口**：`/api/v1/audit/*`。

前三个数据抽象层则描述数据加工关系，不是四类使用入口的重复菜单：原始事实经
标准化后成为研究对象；运营接口是独立控制面，不参与这条加工链路。

统一服务目录由 `GET /api/v1/catalog` 提供。它返回四类使用入口、三层加工关系、
运营控制面、覆盖指标和 REST 契约；控制台“数据服务”页面也以该目录为唯一事实
来源。旧路径不提供兼容别名，调用方应以目录和 OpenAPI 中的规范路径为准。

## 1. 原始审计层

原始层保存每一次 Tushare SDK 请求的参数、状态、响应行数和响应摘要；生产默认只为
异常响应保存逐行无损原文。
采集发生在 `query()` 传输边界，因此即使后续字段转换或标准表写入失败，仍可检查
当时上游到底返回了什么。

- `tushare_raw_request`：每一次真实请求，包括有数据、空响应和失败请求；
- `tushare_raw_record`：异常原文与存量历史归档，按接口、逻辑请求和记录内容哈希
  幂等去重；正常响应以业务表和请求摘要作为持久化证据；
- 分页的 `limit` / `offset` 只属于传输请求，不改变逻辑请求身份；
- `token` 等敏感请求参数在落库前强制脱敏；
- 通用采集器和专项采集器使用同一套请求审计，标准表写入逻辑保持独立。

原始层只用于审计、排障、重放和契约升级，不作为日常研究的默认入口。

| REST 接口 | 用途 |
|---|---|
| `GET /api/v1/audit/raw/interfaces` | 查看请求成功、空响应、失败统计以及是否保留了异常原文 |
| `GET /api/v1/audit/raw/{api_name}/requests` | 分页查看真实上游请求和传输结果 |
| `GET /api/v1/audit/raw/{api_name}/records` | 按请求哈希、记录哈希和采集时间查询原始 JSONB |
| `GET /api/v1/audit/raw/{api_name}/coverage` | 查看请求证据与异常/存量原文覆盖摘要；raw 行数不是业务覆盖率 |
| `GET /api/v1/audit/raw/{api_name}/lineage/{record_hash}` | 从一条原始记录追溯产生它的逻辑请求 |

这里的请求 `success` 只表示 Tushare 成功返回响应，不等同于业务完整性通过。
完整性仍由采集器校验和 Coverage Auditor 判定。

## 2. 标准数据层

标准层是需要底层字段时的数据服务入口：专项接口进入领域表，契约通用接口进入强类型
`tushare_norm_*` 表，并通过 Dataset Registry 暴露稳定字段、日期、主键、过滤器和
分页契约。

多来源统一查询优先使用规范接口，而不是直接调用供应商 Connector：

| 接口 | 当前规范范围 | 来源策略 |
|---|---|---|
| `GET /api/v1/data/canonical/market-bars` | A 股、日频、不复权、最多 10 个代码/366 天 | 本地 `stock_daily` 优先，整段零行时可回退 Financial Data |
| `GET /api/v1/data/canonical/trading-sessions` | A 股开市日、最多 366 天 | 本地 SSE `trade_calendar` 优先，零行时可回退 Financial Data |
| `GET /api/v1/data/canonical/fund-profiles` | 最多 10 只 OF/SH/SZ 基金 | 本地 `fund_basic` 优先，单只基金零行时回退 |
| `GET /api/v1/data/canonical/fund-nav` | 最多 10 只基金、最多 366 天 | 本地 `fund_nav` 优先，仅整段零行时回退，不按股票日历误判缺日 |
| `GET /api/v1/data/canonical/fund-stock-holdings` | 最多 10 只基金、8 个季度末 | 本地 `fund_portfolio` 分区优先，仅空基金/报告期分区回退 |
| `GET /api/v1/data/canonical/fund-dividends` | 最多 10 只基金、最多 366 天 | 本地基金分红优先，代码区间为空才回退；统一为每份现金 |
| `GET /api/v1/data/canonical/fund-managers` | 最多 10 只基金 | 本地基金经理任期优先，基金整体为空才回退 |
| `GET /api/v1/data/canonical/index-profiles` | 最多 10 个沪深指数代码 | 本地指数档案优先，单指数为空才回退 |
| `GET /api/v1/data/canonical/index-constituents` | 最多 10 个沪深指数、20 个明确更新日 | 本地指数权重优先，缺失指数/日期分区才回退 |
| `GET /api/v1/data/canonical/equity-profiles` | 最多 10 只 A 股 | 本地 `stock_basic` 优先，单只证券零行时回退 |
| `GET /api/v1/data/canonical/equity-valuations` | 最多 10 只 A 股、最多 366 天 | 本地 `stock_daily_basic` 优先，缺失开市日切片时回退 |
| `GET /api/v1/data/canonical/equity-financial-periods` | 最多 10 只 A 股、20 个明确季度末 | 本地三张财务表按分段优先，仅缺失的报表分段回退 |
| `GET /api/v1/data/canonical/equity-financial-metrics` | 最多 10 只 A 股、20 个明确季度末 | 本地 `financial_indicator` 优先，仅缺失报告期回退 |
| `GET /api/v1/data/canonical/equity-ttm-financials` | 最多 10 只 A 股、6 个明确季度末 | 本地累计报表按可复核公式派生，无法派生时回退 |
| `GET /api/v1/data/canonical/equity-performance-updates` | 最多 10 只 A 股、20 个明确季度末 | 本地预告/快报分别优先，仅缺失类型与报告期回退 |
| `GET /api/v1/data/canonical/equity-dividends` | 最多 10 只 A 股、20 个明确季度末 | 本地分红方案优先，仅缺失报告期回退 |
| `GET /api/v1/data/canonical/equity-repurchases` | 最多 10 只 A 股、最长 10 年 | 本地回购事件优先，仅代码整段为空时回退 |
| `GET /api/v1/data/canonical/equity-holder-counts` | 最多 10 只 A 股、最长 10 年 | 本地股东户数优先，仅代码整段为空时回退 |
| `GET /api/v1/data/canonical/equity-business-segments` | 最多 10 只 A 股、20 个报告期，显式选择业务/行业/产品/地区 | 本地 `fina_mainbz` 产品和行业优先，缺失维度与报告期才回退 |
| `GET /api/v1/data/canonical/equity-shareholders` | 最多 10 只 A 股、20 个季度末 | 本地前十大股东和流通股东优先，缺失季度才回退 |
| `GET /api/v1/data/canonical/equity-restricted-releases` | 最多 10 只 A 股、最长 10 年 | 本地 `share_float` 优先，代码区间为空才回退 |
| `GET /api/v1/data/canonical/equity-pledges` | 最多 10 只 A 股、最长 10 年 | 本地质押明细优先，代码区间为空才回退 |
| `GET /api/v1/data/canonical/equity-risk-alerts` | 最多 10 只 A 股、最长 10 年 | 本地风险警示事件/状态优先，代码区间为空才回退 |
| `GET /api/v1/data/canonical/equity-suspensions` | 最多 10 只 A 股、最长 10 年 | 本地停牌记录优先，代码区间为空才回退 |

规范日线固定使用 `instrument_id`、ISO 日期、`volume_unit=share`、
`amount_unit=CNY`，解决 Tushare“手/千元”与 Financial Data“股/元”的单位差异。每行
保留 `source_id` 与 `source_dataset`，响应元数据明确是否消耗了额度回退。
基金档案的费率统一为小数比率、金额统一为 CNY；基金持仓数量统一为股、市值统一为
CNY、权重统一为百分点。供应商协议或代码/日期/单位不符合契约时返回 502，不把异常
伪装成空结果。

财务期间接口不猜测“当前季度是否应该披露”，调用方必须提供明确的季度末日期。响应把
利润表、现金流量表和资产负债表分别记录来源与披露日，因此混合来源不会被伪装成单一
来源；三张表当前均为年初至报告期末累计口径，金额单位为 CNY。

预告、快报、分红和财务指标同样使用明确报告期；事件型回购和股东户数使用有界日期范围。
预告与本地快报的万元金额在规范层统一转换为 CNY，增长率仍使用百分点；供应商没有披露
发布日期的股东户数不会伪造发布日期。分红总额除以股本基数得到含税每股现金时会同时保留
原始总额和股本基数，便于复核。
滚动十二月核心金额使用“上年年报 + 本期累计 - 上年同期累计”派生；年报直接采用年度值。
响应公开公式和计算类型，不把派生值冒充上游原始值。
主营构成要求显式指定分类维度；本地来源仅承诺产品和行业，业务及地区维度不会从名称
猜测，而是在该维度缺失时才允许额度源补齐。主要股东、解禁、质押、风险警示和停复牌
均保留事件或报告期语义，稀疏事件的“区间零行”只标为未解决，不等同于已经核验为空。
股票估值把总股本与总市值统一为股和 CNY，股息率统一为小数比率；行业名称同时携带
`industry_classification`，禁止跨分类体系直接比较。

| REST 接口 | 用途 |
|---|---|
| `GET /api/v1/data/datasets` | 发现已登记的数据资产 |
| `GET /api/v1/data/datasets/{name}` | 查看表结构、业务身份、日期列和允许过滤器 |
| `GET /api/v1/data/datasets/{name}/records` | 查询标准化记录，支持 `as_of` 的数据集可做历史时点约束 |
| `GET /api/v1/data/interfaces` | 从上游接口视角查看实现方式及其对应数据集 |
| `GET /api/v1/data/interfaces/{api_name}/records` | 查询契约通用接口的强类型标准记录 |
| `GET /api/v1/data/freshness` | 查看数据最新日期与时效状态 |

这一层供数据工程和公式维护复核输入；不属于公开 Agent 契约。Agent 不自行拼装
跨表研究口径，更不解析原始 JSONB。

## 3. 研究就绪层

研究层把多个标准数据集组合成稳定的研究对象，返回来源、历史时点、质量状态和
缺口，而不是把“查表和拼表”推给每一个 Agent。

当前已落地：

- 研究就绪检查与能力目录；
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
| `GET /api/v1/ops/orchestration-v2/summary` | V2 定义、执行和真实未恢复异常总览 |
| `GET /api/v1/ops/orchestration-v2/executions` | 全量 V2 执行实例、节点、尝试与重试状态 |
| `GET /api/v1/ops/delivery/data-calendar` | 按数据日期查看完整性，不使用任务日期替代 |
| `GET /api/v1/ops/data-health` | 数据集时效和质量状态 |
| `GET /api/v1/ops/initialization` | 初始化和历史补采进度 |
| `GET /api/v1/ops/coverage` | 查看日期或报告期完整性证据 |
| `GET /api/v1/ops/health/ready` | 检查 API 与 PostgreSQL 是否就绪 |
