# 多数据源基础层

## 当前结论

系统已经从“全局绑定 Tushare”调整为“来源注册表 + 端点契约 + Connector”的结构。
Tushare 是第一个正式 Connector；现有专项采集器、分页完整性、任务重试和标准表均保持
兼容。网页解析和按需实时查询已经具备可测试的基础组件，但尚未把任何第三方站点伪装
成生产数据源。

## 四种获取模式

| 模式 | 适用场景 | 持久化与保护 |
|---|---|---|
| `scheduled_pull` | Tushare、定时 API、批量文件接口 | 持久化任务、租约、重试、完整性证据 |
| `web_snapshot` | 需要定时抓取并解析的网页、HTML、PDF | 先保存原始工件，再解析；记录解析器名称和版本 |
| `query_through` | 请求到来时才查询的低延迟外部数据源 | 白名单端点、TTL 缓存、请求合并、熔断、有限陈旧回退 |
| `stream` | 行情流、消息流 | 契约已预留；生产消费者与 offset/checkpoint 尚未实现 |

一个来源可以支持多个模式，但每个端点只能声明一个明确的获取模式。任务提交时的模式
必须与端点契约一致，不能由调用方临时绕过。

## 核心对象

- `SourceSpec`：稳定的 `source_id`、类型、时区、许可策略和凭据引用；只引用凭据，
  不把 Token 写入数据库或接口响应。
- `EndpointSpec`：来源内稳定的 `endpoint_key`、更新周期、资源队列、分页/完整性策略、
  解析器版本和缓存期限。
- `SourceConnector`：执行一个有界采集请求，返回统一 `ConnectorResult`。
- `source_endpoint`：统一任务类型。任务实例持久化 `source_id`、`endpoint_key` 和
  `acquisition_mode`，因此可以准确判断由哪个 Connector 执行。
- `DatasetSpec.source_ids`：规范数据集可以声明一个或多个来源，并显式指定合并策略；
  当前存量数据集仍是 `single_source/tushare`。

运行时代码注册表是受代码评审的允许列表。每次迁移会把它幂等同步到
`sys_data_source` 和 `sys_source_endpoint`，便于控制台和审计查询，不允许直接在数据库
里加入一个未实现的 Connector 后就开始执行。

## 原始证据与大表兼容

Tushare 存量原始表体量很大。多数据源迁移不会重建它的主键，也不会复制全表：

- 所有 Tushare 请求继续写 `tushare_raw_request`；生产默认仅在规范化、校验或业务
  落库异常时把逐行原文写入 `tushare_raw_record`；
- 新来源写 `source_raw_request_store`、`source_raw_record_store`；
- `source_raw_request`、`source_raw_record` 视图把两者统一成
  `source_id + endpoint_key` 语义；
- 网页、PDF 和文件原件写 `source_raw_artifact`，保存内容哈希、URL、响应头、HTTP
  状态及解析器版本；
- 请求参数中的 Token、密码、密钥始终先脱敏再持久化。

这个旁路结构避免在部署时锁住大表，同时让新来源拥有正确的联合主键。

## 网页解析的失败语义

`WebSnapshotConnector` 先归档原始内容，再运行解析器。页面成功获取但选择器、字段或
格式发生变化时，任务应报告 `ParserDriftError`，而不是把“解析为零行”当成正常空数据。
错误会携带 `artifact_id`，后续可用同一原件升级解析器并重放，无需再次请求网站。

生产网页 Connector 还必须实现：域名允许列表、robots/许可审查、连接与读取超时、
有限重定向、内容大小上限、内容类型校验和来源专属限频。

## 按需查询边界

`QueryBroker` 只接受声明为 `query_through` 的端点。它提供：

- 参数规范化后的 TTL 缓存；
- 同一进程内相同请求合并；
- 按来源端点统计失败并熔断；
- 上游失败时，在端点允许的期限内返回带 `cache=stale` 证据的旧结果。

Connector 自身必须实施网络超时；Broker 不通过无限后台线程模拟取消。研究层接口只能
使用已经注册的 Query Connector，不能接收任意 URL 或任意 SQL。

## 确定性数据源优先级

外部数据读取不允许在 Tushare 与 Financial Data 之间随机选择，也不允许把两套供应商
原生响应假装成同一种模型：

1. 先查询 Tushare 定时采集并经过数据审计的本地规范数据集；命中且满足请求范围与
   新鲜度 SLA 时直接返回，不消耗 Financial Data 额度。
2. 本地切片确实缺失或不新鲜时，只有路由已经完成代码、日期、单位、字段映射并通过
   契约测试，才允许由 Financial Data 回退。上游错误不能伪装成空数据。
3. 实时快照等本地没有等价数据的能力必须由调用方显式请求；它不会在普通历史查询中
   被静默调用。
4. 对外响应携带 `served_from`、`read_strategy` 和 `fallback_used`；数据集描述公开
   `fallback_endpoints` 与 `fallback_status`。

完整的 163 个路由优先级可通过 `GET /api/v1/data/source-priorities` 查询，版本化报告见
[`../reports/source_priority_matrix_latest.md`](../reports/source_priority_matrix_latest.md)。

当前隐式额度回退数为 0；已经启用二十九个受范围约束的规范路由适配器：A 股未复权日线、A 股
交易日历、A 股证券身份、A 股日度核心估值、A 股累计利润/现金流、A 股资产负债表、
A 股财务指标、滚动十二月财务、业绩预告、累计业绩快报、分红方案、回购计划、股东户数、
主营业务/行业/产品/地区、主要股东、解禁、质押、风险警示和停复牌，以及基金基础档案、
基金净值、基金股票持仓、基金分红、基金经理，以及沪深指数档案和指数成分权重。
其余重叠路由仍为
`adapter_required`。只有完成规范适配器后才逐项切为
`partial_ready` 或 `ready`，不能直接把供应商原生 JSON 返回给规范数据集调用方。

### 第一批规范接口

```text
GET /api/v1/data/canonical/market-bars
GET /api/v1/data/canonical/trading-sessions
GET /api/v1/data/canonical/fund-profiles
GET /api/v1/data/canonical/fund-nav
GET /api/v1/data/canonical/fund-stock-holdings
GET /api/v1/data/canonical/fund-dividends
GET /api/v1/data/canonical/fund-managers
GET /api/v1/data/canonical/index-profiles
GET /api/v1/data/canonical/index-constituents
GET /api/v1/data/canonical/equity-profiles
GET /api/v1/data/canonical/equity-valuations
GET /api/v1/data/canonical/equity-financial-periods
GET /api/v1/data/canonical/equity-financial-metrics
GET /api/v1/data/canonical/equity-ttm-financials
GET /api/v1/data/canonical/equity-performance-updates
GET /api/v1/data/canonical/equity-dividends
GET /api/v1/data/canonical/equity-repurchases
GET /api/v1/data/canonical/equity-holder-counts
GET /api/v1/data/canonical/equity-business-segments
GET /api/v1/data/canonical/equity-shareholders
GET /api/v1/data/canonical/equity-restricted-releases
GET /api/v1/data/canonical/equity-pledges
GET /api/v1/data/canonical/equity-risk-alerts
GET /api/v1/data/canonical/equity-suspensions
```

`market-bars` 当前只接受最多 10 个 A 股标准代码、最多 366 天、日频、不复权查询。本地
`stock_daily` 与交易日历可以覆盖请求时不调用额度源；某个代码整段零行，或存在本地
开市日缺口时才回退，并且回退行不能覆盖同日期的本地行。
规范模型把 Tushare 的“手/千元”转换为“股/元”，并验证 Financial Data 返回的周期、
复权、代码、字段宽度和日期。

`trading-sessions` 当前提供 A 股开市日。本地 SSE 日历覆盖请求范围时直接返回；本地结果
为空时才允许回退。两个接口都支持 `allow_quota_fallback=false`，并返回
`fallback_used`、`fallback_policy`、覆盖行数和未解决代码。

基金接口同样只返回版本化规范模型。档案把 Tushare 的最低申购金额从万元转换为 CNY，
把两侧管理费/托管费转换为小数比率；净值只在某只基金的请求区间整段零行时回退，
不会错误地用股票交易日历推断基金净值缺日；持仓按基金和季度末分区回退，把
Financial Data 的无后缀股票代码规范为 TS 代码、净值占比从小数比率转换为百分点。
所有本地行优先，Financial Data 只补本地空切片且不能覆盖本地记录。
Financial Data 持仓回退只承诺其接口定义的前十大重仓范围，响应元数据以
`fallback_scope=provider_top_10_holdings_only` 明示，不把它误报为完整持仓全集。

股票身份接口保留行业分类来源，避免把 Tushare 旧行业名称与申万二级行业当成同一口径。
日度估值明确采用 `PE_LYR`、`PE_TTM`、`PB_MRQ`、`PS_LYR`、`PS_TTM`，股息率统一为
小数比率；Tushare 的万股/万元转换为股/CNY。流通市值没有跨来源等价定义时保持为空，
不把 Financial Data 的 A/B 股流通市值冒充为 Tushare A 股流通市值。

财务期间接口要求显式季度末列表，不把尚未披露的季度误判为缺失。利润、现金流和资产
负债三个分段分别记录 `source_id`、`source_dataset` 与 `disclosure_date`；本地分段始终
优先，额度源只补明确缺失的分段且不能覆盖本地值。当前统一的是累计报表核心字段与 CNY
金额口径，不把累计数伪装成单季度数，也不声称具备历史修订时点回放能力。

财务指标、业绩预告/快报和分红也要求显式报告期；回购与股东户数使用最长十年的有界
日期范围。Tushare 预告和快报的万元金额会转换为 CNY，增长率保留百分点。股东户数的
供应商回退没有披露日期时保持为空；分红每股现金只有在总额和股本基数同时存在时才派生。
这些接口不会把“没有发布预告/快报”误写成已验证空，未返回的请求期间会列入
`unresolved`。
主营构成接口要求调用方显式选择分类，避免把产品、行业、业务和地区混在同一维度；本地
`fina_mainbz` 只承诺代码明确标识的产品与行业。股东、解禁、质押、风险警示与停复牌
接口统一日期、股数和百分点语义，并保留来源；稀疏事件没有返回时继续显示为 unresolved，
不会被误判为“确定没有事件”。
滚动十二月金额优先用本地累计报表按“上年年报 + 本期累计 - 上年同期累计”派生，并在
响应中保留公式；只有所需报告期不齐时才查询供应商 TTM 路由。

## 未知历史边界的反向探测

“本地首条数据之前存在候选日期”不等于“数据缺失”。对经过评审的稠密日/周/月序列，
系统可以从首个已观测周期之前开始，由近及远建立受控 V2 探测实例：

- 每个周期仍是一条正常 V2 执行，完整经过范围解析、采集、落库、审计和状态发布；
- 只有 HTTP/供应商响应成功、分页耗尽且审计节点确认零行，才记录
  `verified_empty`；超时、限流和解析异常必须重试，绝不算空；
- 日频要求连续 20 个周期为空，周频 8 个、月频 6 个，并额外验证一个更早的分离锚点；
- 一旦任何周期返回数据，立即把历史起点向前移动并继续探测；
- 连续空窗和锚点都为空时只能标记 `provisional_boundary`，不能冒充供应商权威上线日；
- 财报、成分变更、复权事件等稀疏数据不适用空窗推断，仍需接口契约、实体范围或官方
  边界证据。

实现位于 `service/data_coverage/boundary_probe.py`。生产调度必须复用历史任务的交易时段
门禁、额度预算和批次上限，避免反向探测影响盘中日常采集。

## API 与任务示例

来源发现：

```text
GET /api/v1/data/sources
GET /api/v1/data/sources/tushare
GET /api/v1/data/sources/tushare/endpoints?limit=100&offset=0
GET /api/v1/data/sources/tushare/endpoints/daily
```

Financial Data 的 163 条上游业务路由通过以下接口公开完整依赖分类，而不是只显示一个
Connector 总数：

```http
GET /api/v1/data/source-priorities
GET /api/v1/data/source-priorities?requires_financial_data=true
GET /api/v1/data/source-priorities?dependency_class=financial_data_realtime_required
GET /api/v1/data/source-priorities?dependency_class=financial_data_primary_no_local_canonical
```

当前四类互斥且覆盖全部路由：29 条本地优先且规范回退已就绪、28 条本地已有重叠但
Financial Data 适配待完成、4 条实时能力必须依赖 Financial Data、102 条当前没有本地
规范等价数据。后两类合计 106 条，表示系统今天确实依赖 Financial Data；“无本地规范
等价”不应被解释为已经证明 Tushare 完全没有语义相近接口。

统一任务参数：

```json
{
  "task_name": "source_endpoint",
  "parameters": {
    "source_id": "tushare",
    "endpoint_key": "daily",
    "acquisition_mode": "scheduled_pull",
    "parameters": {"trade_date": "20260921"}
  },
  "max_attempts": 3
}
```

旧 `tushare_interface` 任务保留兼容，且处理器快照键不变；新代码应优先使用
`source_endpoint`。

## 新增一个生产来源的顺序

1. 定义 `SourceSpec` 和每个 `EndpointSpec`，确认授权、许可、时区与数据保留政策。
2. 实现对应模式的 Connector，并让请求只接受结构化参数，不接受任意 URL。
3. 保存原始请求、记录或工件，再完成规范化映射和数据集来源声明。
4. 为分页耗尽、空数据、解析漂移、缓存、熔断、幂等写入和字段漂移建立测试。
5. 增加覆盖规则与更新周期后，才允许 Scheduler 自动生成任务。
6. 最后把研究层接口切到新的规范数据集；上层 Agent 不直接依赖供应商字段。

## 尚未完成的边界

- Financial Data 已作为受额度约束的查询穿透来源接入；免费替代源仍按
  [免费替代源评估](FREE_DATA_SOURCE_ALTERNATIVES.md) 逐项实施。
- `stream` 目前只有契约，尚无生产消费者、offset 与回放能力。
- 多来源冲突解决目前只有数据集级 `merge_policy` 字段，具体优先级、时间对齐和差异审计
  必须在第二个来源接入时按数据集落地，不能用全局“后写覆盖前写”。
- 网页与实时查询组件尚未直接开放为公共 REST 代理，避免形成任意外联通道。
