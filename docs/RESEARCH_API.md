# 股票与板块研究数据服务

本服务为个人和 Agent 提供带来源、历史时点和质量状态的结构化研究材料。它负责
数据访问和可信度表达，不在数据层生成评级、交易建议、因子或回测结果。

确定性基本面、估值和技术指标已经迁移到独立研究命名空间
`/api/v1/research/*`。资料包仍负责组合原始研究材料；派生接口负责统一公式、窗口、
基准和质量证据。当前能力与数据缺口以
`GET /api/v1/research/capabilities` 为准；本文只维护稳定的调用契约和计算语义。

Agent 首先通过研究层检查可用性，不需要调用运营接口：

```http
GET /api/v1/research/readiness
GET /api/v1/research/capabilities
```

## 沪深 300 历史因子切片

沪深 300 的**单日成分 × 因子截面**另有入口：

```http
GET /api/v1/research/factor-slices/csi300?day=2026-10-30&factor=return_5d&factor=roe_y
```

此契约仅覆盖一个历史交易日、指数 000300.SH、1～32 个本地 272 目录内因子。
默认 `known_then` 以北京时间当日 24:00 为界：只读此前已首次入库的当日权重、
此前已计算且仍保留的当日因子版本，不可用于模拟当日盘中信号。事后补算须显式用
`knowledge=reconstructed`，不能解释为当时系统已掌握。缺当天完整的 300 个成分返回
409，不以前月或未来权重回填。缺因子仍保留成分行、空值和原因；可用掩码不等于
供应商逐值校验通过。清单同时给出导出时的分区审计（没有记录即无证据）、计算时间和输入摘要。

离线冻结（DuckDB 仅用于导出，无需安装到服务容器）：

```sh
uv pip install --python .venv/bin/python duckdb==1.4.3
.venv/bin/python scripts/export_index_slice.py --day 2026-10-30 --factor return_5d --factor roe_y --output csi300-20261030.zip
```

归档包括强类型长表 `factors.parquet`、逐成分证据 `rows.json` 和 `manifest.json`。
同一数据库事务读取所有底表；固定内容可重复导出，不覆盖已有文件。数据或审计发生修订后可能产生新 ID，
复现实验应保留原归档。此接口不推断停牌、可成交性或全市场历史完整性。

## 行业与指数成分估值分布

```http
GET /api/v1/research/indices/000300.SH/valuation-distribution?trade_date=2026-10-30
GET /api/v1/research/indices/000688.SH/valuation-distribution?trade_date=2026-10-30
GET /api/v1/research/indices/000300.SH/valuation-distribution?trade_date=2026-10-30&report_period=2026-06-30
GET /api/v1/research/indices/000300.SH/valuation-distribution/history?start=2026-10-01&end=2026-10-30
GET /api/v1/research/indices/000300.SH/valuation-distribution/snapshot?trade_date=2026-10-30
GET /api/v1/research/sectors/ths/{sector_code}/valuation-distribution?trade_date=2026-10-30
```

这是本地数据的按需计算，不调用蚂蚁，也不替代供应商指数估值接口。
必须传明确日期；休市日或缺数据不会自动回退为另一天。指数采用不晚于请求日的最近
成分权重快照；超过55天或权重和偏离100%会警告。行业历史成员资格尚未独立认证，始终披露限制。
`membership_conflicts`披露旧指数成分中截至请求日已退市的证券，保留原成员集合，
不将其简单当作当日日行情缺口、不自动删除成员或填入价格。2026-10-31本地检查中，
沪深300的2026-08-31快照仍含601059.SH，本地主数据退市日为2026-10-19；
这说明需要刷新并验收指数成员，而非为该证券补造10月30日行情。

PE、PE-TTM、PB、PS-TTM、股息率各返回均值、中位数、线性插值P10/P25/P75/P90、最小最大值、
市值加权均值和（指数场景）成分权重加权均值。比率仅纳入正数，股息率允许0；
非有限值按缺失处理，逐项列出缺失、非正剔除证券及有效数量。加权值仅在有效样本中重新归一，
同时给出参与数量和权重和，不能当作全体成员估值。集中度包括前十大市值占比和市值HHI，
基于当日有正市值的成员；市值单位为万元。正PE-TTM覆盖率不能称为已审计的盈利公司占比。

`outliers` 使用Tukey 1.5×IQR标记极端值并列出证券，不删除、不缩尾，原均值保持不变。
`member_percentiles` 返回成员在有效样本中的中位秩百分位：
`(小于该值的数量 + 0.5×等值数量) / 有效样本数 × 100`；同值同排名，越大意味着指标越高，
并不等于越值得投资。排序加二分定位避免全市场逐对比较。

可选 `report_period` 请求同一报告期的ROE、ROIC、毛利率、净利率、资产负债率分布，
仅取该报告期且公告日期不晚于trade_date的记录，不跨报告期填补、不把负值剔除、不擅自年化。
逐项返回有效数量、覆盖率、缺失证券、正负值数量；这些统计不是整体法ROE，也不是盈利公司占比。
未提供report_period不查财务表；报告期晚于trade_date直接拒绝。已入库的历史修订版本限制仍适用。

`quality.status=computed`仅代表已计算，不代表严格独立验收通过；`independently_audited=false`。
缺失证券、指标或成分风险返回warning。历史修订值不能自动视为当时已公开数据。
指定report_period时另返回 `aggregate_valuation`：整体法PE-TTM用累计归母利润
（上年全年＋本期累计－上年同期；年报直接取全年），整体法PB用总权益减少数股东权益。
只选公告可见的合并报表；市值万元转元后计算比值，纳入匹配样本的亏损和零分母公司。
缺分母不补0，整体分母非正不返回可用估值。披露匹配数、缺失代码、分子分母和partial状态。
这是指定共同报告期口径，不冒充供应商指数估值或每家公司各自最新报告期口径。

行业和指数均支持 `valuation-distribution/history?start=...&end=...`，一次至多31个自然日，
依赖完整上交所日历，逐交易日选择当时可用成员，保留无成员/无数据日期。
窗口百分位只用quality=computed的日期，对warning日期不作有效历史样本；不是十年历史分位。
较长范围应分段读取，不通过扩大同步查询拖慢API。

V2 `valuation_percentile_snapshot` 现已实现，代码冻结沪深300、科创50两个指数范围，
不声称覆盖全部行业。日常依赖daily_basic；index_weight为异步辅助输入，修复后其状态修订
触发重新计算，不强迫月度权重与日数据使用同一观察周期。存储表同名，每日期一行，
重复执行覆盖该日期，不产生第二套正式数据。写入前独立SQL核对PE-TTM有效数量和中位数；
任何缺项/成分风险保存partial诊断，不发布ready，覆盖审计只接受ready与固定公式版本。
`/snapshot`只读物化结果，不重新计算，返回计算时间、公式版本和源执行实例；partial不能用于完整性背书。
该派生任务启用时，依赖检查会对两个指定指数补查最近已结束月份的权重；按月幂等创建一个V2
有界修复实例，失败不反复新建，不启用全指数目录扇出，不调用蚂蚁。
盈利公司占比、增长/现金流集合统计及全部行业的定时物化尚未覆盖。

2026-10-31落地验证：V2修复实例168343已成功补入两指数2026-09-30及2026-10-30权重，
10月30日分别300/50成员，权重和99.990%/99.999%；同日估值行分别300/50。
日常派生定义921已启用，首个实例168381完成计算落库但因缺字段进入attention，
存储audit_status=partial，不等于完整验收通过。PE-TTM空值分别24/14只，股息率空值26/18只；
这些值未被补0或用供应商指数值填充。以2026-06-30报告期计算整体法时，
PE-TTM分母分别匹配300/50只，PB分母仅匹配281/31只；仍需区分源字段缺失与合法不可定义值。
本轮针对性回归83项通过；此前更广测试中factor_value旧mock缺少is_open的失败不属于本轮已修复范围。

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

## 熊门线与熊市反弹提示

与牛门线使用同一套复权日线，股票主视图的 `data.trend.systems.xiongmen_rebound`
及所有标的的 `data.timeframes.1d.trend.systems.xiongmen_rebound` 返回最新状态。
周/月线返回 `not_applicable`，图表不包含熊门字段。

日线 `chart.points` 的价格字段：

| 字段 | 原公式 | 含义 |
| --- | --- | --- |
| `xiongmen_line` | BML | 前20日最低价减当日半个简单ATR14 |
| `xiongmen_foundation` | DJ | 当日及此前共20日最低收盘 |
| `xiongmen_floor_1/2/3` | LT1/2/3 | LL20到HH60收盘区间的38.2%、50%、61.8% |
| `xiongmen_recovery_ma_60` | JTX | 收盘MA60 |
| `xiongmen_bear_entry_line` | RXX | 250日最高收盘×0.8 |

`xiongmen_bear_state` 对应XS；`xiongmen_candidate` 对应SJ；
`xiongmen_sample_count/lower_count/lower_rate_pct` 对应NK/NW/JLV。
`xiongmen_reduction_signal` 是 `减一`、`减二` 或 null，
`xiongmen_marker_price` 是相应的 C×1.03/C×1.05，仅供绘图。
BF/ATRV同时在逐日字段中提供，布尔值、整数计数和文字标签保留类型。

版本 `xiongmen-tongdaxin-v1` 保留用户原式的
`FILTER(XS AND crossing,10) AND NOT(DY)` 顺序：大涨日被排除后仍占用10日过滤间隔。
DY按收盘价相对昨收的涨点计算，BF包含当日变化。仅在SJ发生20个交易日后结算，
统计对象是SJ，不是最终减仓提示；到期收盘必须严格低于信号日收盘。
至少15个已结算样本且下跌比例至少65%才显示减字，不代表策略盈利胜率。

沿用牛门线的完整窗口原则：BML至少21根日线，楼层/MA60至少60根，XS至少250根；
暖机阶段相应价格/状态为null，不用缩短窗口模拟250日历史，也不回填历史信号。
统计在当前请求的全部可用历史上累计、完成后才裁剪图表点，缩放/平移不改变统计；
改变查询历史范围可能改变累计样本和提示。摘要公开历史长度、统计口径和过滤顺序。

标的研究、指数与板块K线提供“熊门体系”开关，显示六条参考线和减仓标记；
入熊线独立开关且默认关闭。浅色主题使用灰色熊门线，深色主题使用白色；
悬停显示各线价格、当日提示及已结算样本统计。前端不重新计算熊门信号。

## 常用技术指标包

股票与多资产技术接口使用同一个 `common-technicals-v1` 公式契约，并在日、周、月
各周期独立计算，禁止把日线指标直接缩放成周/月指标：

- 趋势：`EMA20/50/200`、`BIAS6/12/24`、`BBI(3,6,12,24)`；
- 百分比动量：`PPO(12,26,9)`、`TRIX(12,9)`；
- 波动：`NATR14`、`Keltner(EMA20 ± 2×Wilder ATR20)`；
- 挤压：Bollinger(20,2σ) 完全进入 Keltner(20,1.5×ATR) 时
  `ttm_squeeze.on=true`；
- 量价：PVT、VROC12/20、Force Index 13，同时提供
  `force_index_13_normalized_pct` 供跨股票比较。

完整参数在 `data.indicator_contract.parameters` 返回。K线逐点字段与摘要字段使用相同
计算结果；EMA20/50/200 在对应观察数不足前返回 `null`，不会把短历史的种子值冒充
完整周期指标。PVT 与原始 Force Index 属于路径相关绝对值，跨标的筛选应使用20期变化、
百分比或归一化字段。

`data.indicator_contract.parameter_profile` 另外给出当前频率实际采用的 SMA、EMA、
RSI、ROC、CCI、ATR/NATR 参数族。日、周、月分别使用独立的 bar 参数，而不是把
“日”机械替换成“周/月”。逐点结果包含 `sma_family`、`ema_family`、`rsi_family`、
`roc_family_pct`、`cci_family`、`tsi_25_13`、Bollinger `%B` 与带宽；摘要还包含
9 个连续 K 线几何量、60 期区间位置、ATR5/ATR20、20/120 期回撤深度、20/60 期
回归斜率与拟合度、ATR 归一化突破幅度和高低位触碰次数。完整参数矩阵见本文的
“指标参数与因子边界”。这些结果只描述已发生行情，
不声明预测能力；Alpha158/191、未来收益标签和 IC 检验由 claw-factor-lab 负责。

### 全市场派生快照

逐股研究接口继续支持任意 `as_of` 即时计算；收盘后的全市场筛选与审计使用 V2
物化数据集：

```http
GET /api/v1/data/datasets/technical_factor_snapshot/records
    ?date=2026-10-09
    &calculation_status=ready
    &limit=1000
```

该数据集是 `local_factor_snapshot` 的只读投影视图，不存第二份值；每天由统一的
`local_factor_snapshot` 派生实例批量生成，不为每只股票拆分
任务。每个当日上市证券都有一行，包含 `source_trade_date`、牛门/确认线、20/60日
成本线、EMA/BIAS/BBI/PPO/NATR/Keltner/TTM Squeeze/TRIX/PVT/VROC/Force、公式版本
和 `unavailable_reasons`。停牌股票的 `source_trade_date` 可以早于
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

## 宏观与行业

```http
GET /api/v1/research/macro/regime?as_of=2026-09-18
GET /api/v1/research/macro/{theme}?periods=24&as_of=2026-09-18
GET /api/v1/research/sectors/{provider}/{sector_code}/fundamentals?as_of=2026-09-18
GET /api/v1/research/sectors/{provider}/{sector_code}/breadth?as_of=2026-09-18
```

`theme` 支持增长、通胀和流动性主题。宏观状态使用透明规则组合 GDP、PMI、CPI/PPI、
货币社融和利率；标准表尚未完整保存首次发布值及历次修订，因此历史 `as_of` 不等于
严格 publication-vintage 快照。

行业身份必须同时包含 `provider` 和 `sector_code`。行业基本面以目标时点有效成分为
边界，返回聚合财务、同比、估值覆盖和主要贡献公司；行业宽度返回涨跌分布、均线扩散、
成交额和行情覆盖率。板块指数上涨不能替代成分内部宽度证据。

## ETF 份额与证据分级

```http
GET /api/v1/research/etfs/flows
GET /api/v1/research/etfs/state-team-signals
```

份额资金流按以下口径估算：

```text
估算申赎资金（亿元） = （期末总份额 - 期初总份额） × 期末单位净值 ÷ 10,000
```

规模变化不能直接当成资金流，因为还包含价格变化。相同指数的 ETF 按跟踪指数聚合，
跨产品同时流入流出只表示横截面共现，不证明是同一投资者腾挪。

证据分为 `market_flow_only`、`suspected` 和 `confirmed`。没有正式公告或定期报告中的
持有人身份与份额变化时，接口不得生成 `confirmed`，避免把做市、套利、联接基金或普通
投资者误报为国家队行为。

## 投资日历

投资日历与数据日历不同：前者展示宏观发布时间、央行事件和股指期货交割日；后者展示
某个数据日期的业务数据是否落库并通过审计。

```http
GET /api/v1/research/investment-calendar?start_date=2026-09-01&end_date=2026-09-30
GET /api/v1/research/investment-calendar/2026-09-18
```

经济事件来自财经日历，股指期货交割日来自真实合约 `last_ddate`，浏览器不硬编码日期。
实际值为空且事件时间已过时标记为“实际值待来源回填”，不能误报成未发生或没有事件。
响应同时返回来源覆盖范围；超过覆盖截止日表示尚无已采集事实。

## 指标参数与因子边界

claw-data 负责可审计的原始/标准数据和确定性派生指标；claw-factor-lab 负责横截面处理、
未来收益标签、IC/RankIC、显著性、分组收益、回测和预测性验证。同一个表达式可以在两边
出现，但 claw-data 不声明其具有预测收益，也不使用未来标签挑参数。

所有周期参数表示当前频率的 bar 数，不是自然日：

| 指标族 | 日线 | 周线 | 月线 |
|---|---|---|---|
| SMA | 5/10/20/30/60/120/250 | 5/10/20/30/40/52 | 3/6/12/24/36/60 |
| EMA | 5/10/12/20/26/50/100/200 | 5/10/12/20/26/50/52 | 3/6/12/20/24/26/36/60 |
| RSI | 6/12/14/24 | 6/12/14/24 | 6/12/14/24 |
| ROC | 5/10/20/60/120 | 4/12/26/52 | 3/6/12/24/36 |
| CCI | 14/20 | 14/20 | 14/20 |
| ATR/NATR | 14/20 | 14/20 | 14/20 |

MACD 12/26/9、KDJ 9/3/3、Ichimoku 9/26/52 和 Bollinger 20/2 使用行业惯例。
Alpha158/191、横截面中性化、预测标签和回测属于 factor-lab，不在本服务包装成基础数据。

## Factor Lab 输入契约

`GET /api/v1/research/factor-inputs` 发布 `claw-factor-inputs@v1`，用于冻结
claw-factor-lab 的可复现输入。当前按核心日线、日频估值、时点基本面、财务参考、
公司行为、公司新闻、资金情绪、确定性技术描述、ETF、指数与行业、宏观分包。契约同时声明每个
数据集的日期列、可用时间列、数据源、存储语义、是否为必需输入以及缺行语义。

连续日频数据使用 `stock_daily_sessions` 覆盖规则，必须逐股票与日线交易会话一致；
预告、快报和大宗交易属于稀疏事件，未观测到记录不代表已证明当期没有事件；
`technical_factor_snapshot` 是统一特征存储的兼容视图，存量历史技术指标可查询；更早历史应由日线因子源重算，不能伪装成
历史快照全量；`fama_french_daily` 则由已治理的日线、市值和公告时点财务数据自 2020 年
开始逐交易日重建，并以公式版本和输入行数对账结果留痕。
财务输入必须带 `as_of` 截止日，缺少受治理可用时间列的数据不得进入历史时点快照。

### 特征来源与身份（2026-10-23）

`GET /api/v1/research/factors/catalog` 返回正式特征、11 类研究分类、系列、唯一来源、
输入供应商、频率、别名和独立验证状态。`GET /api/v1/research/factors/{ts_code}`
支持 `factor` 重复参数，最多 64 项，直接选择数组位置或扩展字段，不重新计算。
同一公式、参数、周期、价格口径、暖机规则构成同一身份；不同复权锚点或周/月参数
不能冒充同一份日频物化值。图表的任意历史时点/周期按需计算仍保留，不另行持久化。

272 因子和额外技术特征仅存于 `local_factor_snapshot`；七项完全同公式指标通过别名
共享数组位置，`roc_5` 只作百分比展示换算。Keltner 中轨允许早期 EMA 暖机值，
EMA20 需要完整窗口，两者可用性不同，不合并契约。筹码供应商估计也不等同于成交成本线。

`factor_value` 是内部对照集：保留采集、原值和抽检，禁止正式查询和自动回退。
运营对照报告在 `/api/v1/ops/factors/validation`；`matched` 需要至少30组配对且99%以上
落在 `1e-5 + 1e-3*abs(reference)` 容差内；仅相关性达标为 `correlated`，不是数值等价。
响应中的 `audit_status/audit_evidence` 是输入就绪证据，`calculation_status/ready_count`
只是计算值可用性。`verification` 另列对照原因与缺值/排除原因。新口径 `local-272-v4`
采用按交易日固定种子的可复现抽样对照（默认 512 只股票），校验 SQL 设 15 分钟硬超时；Tushare `factor_value` 仅用于抽检，不作为正式查询的数据来源。供应商尚未发布参考分区时记录 `provider_pending`，待参考数据出现后由调度器自动复验，不得把“尚未发布”展示为本地公式失败。
不回退旧版本；旧数据仍保存作审计证据，不能把迁移前的存储边界当成新口径的覆盖范围。
目录展示的存储起止日不证明中间连续；最新日非空证券数不证明所有历史日期齐备。
旧的 `factors/local/*` 路径暂作同一查询处理器的兼容入口，没有独立计算或存储。

## 控制台研究加载与导航（2026-10-30）

控制台收敛为运营总览、研究工作台、投资日历、数据健康、任务中心、数据服务六个主入口。
任务定义/执行实例/派生加工与今日交付/数据日历/覆盖审计分区展示，不能互相代替就绪判断。
研究工作台保留个股、大盘、ETF、板块、宏观、盘中观察和因子目录。

研究页手动刷新直接重试当前模块，不等待运营总览；后台轮询不重算研究图表。
指数/ETF/板块的 K 线与估值、份额、成分股分别加载，辅助模块失败不抹去成功的 K 线。
异步返回带选择版本保护，快速切换品种后旧请求不能覆盖新选择。
个股首屏默认查询 1200 个交易日，可明确选择 3000 或最多 10000 个交易日；
图表最多返回 1500 根，月/周聚合仍来自所选分析范围。展示范围不是完整历史审计结论。

技术接口复用短时进程缓存与同参数并发合并，指数/ETF/板块缓存键包含品种、
数据源、基准、日期和历史/图表范围。个股同一次响应的日线公共指标计算包复用，
不跨证券、复权边界或周期复用；有数值等价回归测试。
缓存沿用现有 TTLCache 的过期后台刷新策略，应以响应数据日期为准而非请求成功时间。

本机并行历史计算负载下实测：宁德时代 1200 日首次请求 16.96 秒、缓存命中 0.29 秒；
沪深300 ETF 首次请求 23.64 秒、命中 0.31 秒。上证指数命中约 0.04–0.27 秒。
这些是单次观测，不是性能 SLA；数据库共享磁盘负载下冷请求仍需进一步治理。
