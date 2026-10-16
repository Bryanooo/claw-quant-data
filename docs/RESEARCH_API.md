# 股票与板块研究数据服务

本服务为个人和 Agent 提供带来源、历史时点和质量状态的结构化研究材料。它负责
数据访问和可信度表达，不在数据层生成评级、交易建议、因子或回测结果。

确定性基本面、估值和技术指标已经迁移到独立研究命名空间
`/api/v1/research/*`。资料包仍负责组合原始研究材料；派生接口负责统一公式、窗口、
基准和质量证据。完整能力与数据缺口见 [RESEARCH_CAPABILITIES.md](RESEARCH_CAPABILITIES.md)。

Agent 首先通过研究层检查可用性，不需要调用运营接口：

```http
GET /api/v1/research/readiness
GET /api/v1/research/capabilities
```

## 股票检索与可视化入口

```http
GET /api/v1/research/stocks/search?q=宁德时代&limit=20
GET /api/v1/research/stocks/search?q=300750&limit=20
```

检索基于本地 `stock_basic` 证券主数据，支持交易所代码、证券代码、简称、全称和拼音简码；
精确匹配和当前上市证券优先。Dashboard 的“个股研究”页面使用该接口选择股票，再调用
技术面接口展示日 / 周 / 月 K 线、成交量与 MACD。日线还可叠加 MA5/10/20/60、
BOLL、20/60 日实际成交成本线、牛门线和确认线。页面不在浏览器中重算成本线或牛门线，
只消费研究接口中已经统一口径的逐日序列；MACD 序列也随各周期图表点返回。

Dashboard 自选使用独立的偏好数据接口，不复制行情数据：

```http
GET    /api/v1/research/watchlist
POST   /api/v1/research/watchlist/{ts_code}
DELETE /api/v1/research/watchlist/{ts_code}
```

自选保存在 PostgreSQL `sys_stock_watchlist`，容器重建后仍保留；重复添加和重复删除均为
幂等操作。该接口只管理页面偏好，研究计算仍由下述股票技术面接口提供。

## 一致预期、股东行为与总股东回报

```http
GET /api/v1/research/stocks/300750.SZ/analyst-revisions
    ?window_days=90&target_periods=4&as_of=2026-09-18
GET /api/v1/research/stocks/300750.SZ/ownership
    ?lookback_days=1825&as_of=2026-09-18
GET /api/v1/research/stocks/300750.SZ/shareholder-return
    ?lookback_days=1825&as_of=2026-09-18
```

`analyst-revisions` 把当前窗口与紧邻的等长历史窗口比较。每个券商在每个预测目标期只
保留窗口内最新一份报告，再对 EPS、净利润、收入和目标价取中位数，避免高频发报告的
机构被重复加权。少于三家机构时不会生成“可靠一致预期”；没有前一窗口时会返回
`insufficient_history`，而不是把当前预测误称为上调或下调。

`ownership` 分别返回十大股东集中度、十大流通股东集中度、基金持仓、北向持仓、股东
户数和股东/高管增减持。存在更正公告的数据按 `as_of` 之前最新公告版本去重。某类事件
为空只表示“本地没有可用披露”，不推断为持仓为零或没有交易。

`shareholder-return` 使用 `stock_daily + adj_factor` 的最新因子基准计算区间总回报和
年化回报。分红、回购和未来一年已披露解禁作为独立证据返回；分红不再加到复权收益上，
避免双重计算。回购公告通常是累计快照，因此接口只展示最新状态，不对历次公告金额求和。
如果复权因子不完整、日线不足一年或分红历史缺失，`meta.quality` 会明确降为 `warning`。

三项接口已经可调用，但全历史是否补齐仍由 `/api/v1/research/readiness` 和能力目录中的
backfill 工作流独立判断；“研究接口存在”与“全历史严格就绪”不是同一个状态。

## 股票技术面与成交成本线

```http
GET /api/v1/research/stocks/{ts_code}/technicals
    ?as_of=2026-10-09
    &lookback_days=3000
    &chart_points=120
```

`data.volume_price.analysis.transaction_cost_lines` 提供20日、60日实际成交成本线；
`data.chart.points[*].cost_20` 和 `cost_60` 提供可直接绘图的逐日序列。A股公式为：

```text
daily_average_price = amount(千元) × 10 / vol(手)
cost_N = SUM(amount × 10 × price_adjustment_scale, N) / SUM(vol, N)
```

成本线和K线使用同一个截至 `as_of` 的复权基准。任一窗口内成交额或成交量缺失、
非正数时，该窗口返回 `missing_input`，不会静默退化成OHLC近似；上市历史不足时返回
`insufficient_history`。原有 `anchored_vwap_proxy` 使用日线典型价估算，保留用于量价
分析，但不得视为实际成交成本线。

## 牛门线与突破确认线

股票和通用标的的日线技术接口在
`data.trend.systems.niumen_breakout`（股票主视图）以及
`data.timeframes.1d.trend.systems.niumen_breakout` 中返回牛门线。通用标的技术接口在
`data.timeframes.1d` 使用同一契约。逐日绘图字段为
`niumen_line`、`niumen_confirmation_line` 和 `niumen_signal_ma_10`。

这里的“14期”和“20期”明确指14个、20个已排序交易日，不是自然日：

```text
TR = MAX(H-L, ABS(H-REF(C,1)), ABS(L-REF(C,1)))
ATRV = MA(TR, 14)                         # 简单移动平均，含当日已完成K线
BASE = REF(HHV(H, 20), 1)                # 前20个交易日最高价，不含当日
NIUMEN = BASE + 0.5 * ATRV
CONFIRMATION = BASE + 1.0 * ATRV
SIGNAL = MA(C, 10)
```

状态 `confirmed_breakout` 表示当日收盘价达到确认线；
`above_niumen_pending_confirmation` 表示站上牛门线但未达到确认线；
`below_niumen` 表示仍在牛门线下方。该公式只在日线执行，周线、月线明确返回
`not_applicable`，避免把“14个交易日”误算成14周或14个月。全部价格和K线采用相同
复权口径，计算时点为日线收盘后。

### 全市场派生快照

逐股研究接口继续支持任意 `as_of` 即时计算；收盘后的全市场筛选与审计使用 V2
物化数据集：

```http
GET /api/v1/data/datasets/technical_factor_snapshot/records
    ?date=2026-10-09
    &calculation_status=ready
    &limit=1000
```

该数据集每天由一个 `technical_factor_snapshot` 派生实例批量生成，不为每只股票拆分
任务。每个当日上市证券都有一行，包含 `source_trade_date`、牛门/确认线、20/60日
成本线、公式版本和 `unavailable_reasons`。停牌股票的 `source_trade_date` 可以早于
`snapshot_date`；上市历史不足或复权因子缺失会明确标为 `partial`、
`insufficient_history` 或 `missing_input`，不会静默遗漏。

## 个股资料包

```http
GET /api/v1/research/stocks/{ts_code}/research-pack
    ?lookback_days=180
    &benchmark=399006.SZ
    &financial_periods=8
    &as_of=2026-09-08
    &include_external=true
    &include_realtime=true
```

`as_of` 同时约束：

- 行情、估值、资金和基准指数的观察日期；
- 财务、预告、快报、股东和公司行为的报告期；
- 有 `ann_date` 的数据在该日期前必须已经公开。

响应的 `meta.provenance` 逐数据集给出返回数量、观察范围、可获得日期字段和历史
时点状态。`meta.quality` 中：

- `missing`：研究包所需的周期性核心数据没有记录；
- `unknown_empty`：结果为空，但仅凭数据库不能证明该股票确实没有该事件；
- `point_in_time_safe`：所有要求历史时点过滤的组成部分均已执行可获得日期约束。

媒体新闻不是交易所公告，`external_data_needed` 会继续明确要求从官方公告源核验。

当前日期的资料包还返回 `data.provider_evidence`：基本面包括 蚂蚁数据源 一致预期、
评级汇总和目标价，技术面包括供应商技术指标、形态及时间戳明确的实时/估值快照。
研究代码应优先读取 `provider_evidence.normalized`；其
`research-fundamental-evidence/v1` 与 `research-technical-evidence/v1` 契约隔离供应商
字段变更，原始路由结果只用于审计和诊断。每条路由独立标记 `available`、`empty` 或
`unavailable`，单条路由协议错误不会清空同一批次的其他有效证据。
本地 Tushare 数据仍是财务事实和确定性技术计算的主口径；供应商证据只作补充或交叉
验证。历史 `as_of` 会排除没有历史截止参数的路由，不能把当前目标价或实时快照带入
历史结论。供应商失败会显示为 `unavailable` 并使质量状态降级，不会伪装为空数据。
技术面响应还在 `data.provider_evidence.reconciliation` 中按同一观察日核对收盘价和
均线；若供应商未声明复权口径且与本地复权序列显著偏离，会保留原始证据、标记
`warning`，但不会混入本地确定性信号。

## 板块发现

```http
GET /api/v1/research/sectors?provider=ths&query=人工智能&category=概念指数&market=A&as_of=2026-09-08&limit=100
```

支持 `ths`、`dc`、`tdx`。板块代码属于供应方命名空间，调用者必须同时保存
`provider` 和 `sector_code`，不能只根据板块名称合并。

## 股票所属板块与可比股票

```http
GET /api/v1/research/stocks/{ts_code}/sectors?provider=ths&as_of=2026-09-08
GET /api/v1/research/stocks/{ts_code}/peers?provider=ths&as_of=2026-09-08&max_sectors=5&limit=50
```

`sectors` 按供应方的历史成分关系解析股票所属板块。`peers` 排除宽基指数，优先使用
行业和规模较小的概念板块，再按共同板块数量排序；响应同时返回产生该关系的板块，
不会把“同板块”伪装成估值或基本面相似度。

## 板块快照与成分

```http
GET /api/v1/research/sectors/{provider}/{sector_code}/snapshot?as_of=2026-09-08
GET /api/v1/research/sectors/{provider}/{sector_code}/members?as_of=2026-09-08&limit=500
```

同花顺成分按照 `in_date <= as_of < out_date` 判断；东财和通达信选择不晚于
`as_of` 的最近一个成分截面。响应返回实际采用的 `membership_effective_date`，
避免把旧截面伪装成目标日期截面。

## 板块资料包

```http
GET /api/v1/research/sectors/{provider}/{sector_code}/research-pack
    ?lookback_days=180
    &member_limit=500
    &as_of=2026-09-08
```

资料包包括板块资料、最新行情、历史行情、历史时点成分和供应方可用的板块资金流。
`meta.quality` 给出核心缺失、实际行情范围、资金流状态和成分是否可能因调用上限截断。

## 底层数据复核（不属于 Agent 契约）

数据工程和人工排障可以使用标准层复核公式输入。声明了
`availability_column` 的数据集支持：

```http
GET /api/v1/data/datasets/income/records
    ?ts_code=000001.SZ
    &end_date=2024-03-31
    &as_of=2024-04-30
```

服务会同时执行 `end_date <= 2024-03-31` 和 `ann_date <= 2024-04-30`。不具备
可靠可获得日期字段的数据集会拒绝 `as_of`，不会悄悄退化为不安全查询。Agent
不会直接调用该路径，所需来源和质量证据由研究响应中的 `meta` 返回。
