# Agent 研究能力与数据动作

本项目不再用上游接口数量衡量研究能力，而是从 Agent 需要完成的基本面和技术面
分析倒推数据、计算契约与缺口。上游原始接口仍在 `/api/v1/audit/raw/*`，标准数据仍在
`/api/v1/data/datasets/*`，确定性派生服务统一位于 `/api/v1/research/*`。

## 为什么使用新的路径

研究派生接口与标准数据接口的契约不同：

- 标准数据接口返回供应方事实记录，不改变业务口径；
- 研究接口执行明确公式、窗口、复权、基准或横截面计算；
- 研究结果必须同时返回 `as_of`、方法说明、数据来源和质量警告；
- Agent 可以解释结果，但不应在每次任务中重新发明指标公式。

`/api/v1/research/stocks/*` 和 `/api/v1/research/sectors/*` 用于资料包、板块关系和
基础快照，并与其余派生能力统一属于 `/api/v1/research/*` 命名空间。

## 已实现的派生服务

11 个 Agent REST 入口中有 1 个能力目录、1 个研究就绪检查、9 个聚合研究服务。
它们不是“11 种分析”，
也不表示已经覆盖所有可能的投研方法；投研方法本身没有封闭全集。项目定义了一份
可验收的 v1 基线：59 项核心能力中，当前 51 项已由研究接口直接服务，3 项可由
已有 Tushare 数据补采后增加服务，另 5 项仍受外部数据源或额度约束。能力目录会
返回逐项 `techniques.served` 和 `techniques.gaps`，不再只给一个容易误解的总数。

| 接口 | 覆盖能力 |
|---|---|
| `GET /api/v1/research/capabilities` | 能力目录、补采工作流、新数据源待办 |
| `GET /api/v1/research/readiness` | 面向 Agent 的研究数据时效、覆盖、失败和初始化摘要 |
| `GET /api/v1/research/stocks/{ts_code}/fundamentals` | 财务趋势、盈利、成长、现金质量、偿债、效率、杜邦与主营构成 |
| `GET /api/v1/research/stocks/{ts_code}/valuation` | PE/PB/PS/股息率历史分位、同行中位数、DCF/DDM 输入 |
| `GET /api/v1/research/stocks/{ts_code}/technicals` | K线与缺口、MA/MACD/ADX/Aroon/PSAR、RSI/KDJ/CCI/Williams/MFI/StochRSI、量能异常/价量四象限/突破确认/背离/换手率/日线VWAP代理、ATR/布林/下行风险、Ichimoku、Donchian、Supertrend、六类枢轴、斐波那契回撤、缠论候选结构、基准风险和绘图序列 |
| `GET /api/v1/research/instruments/{asset_type}/{code}/technicals` | 股票、指数、ETF、THS板块、SGE现货的日/周/月同口径技术体系、斐波那契回撤、缠论候选结构和长期趋势 |
| `GET /api/v1/research/stocks/{ts_code}/capital-flow` | 个股资金流、两融、北向、大宗和筹码状态 |
| `GET /api/v1/research/stocks/{ts_code}/repurchase-progress` | 结构化回购方案、最新累计实施进度、执行均价与公告后相对收益 |
| `GET /api/v1/research/stocks/{ts_code}/event-study` | 事件窗口收益、基准收益、异常收益和 CAR |
| `GET /api/v1/research/market/breadth` | 涨跌分布、均线扩散、成交和涨跌停情绪 |
| `GET /api/v1/research/sectors/{provider}/rotation` | THS/DC/TDX 当前有效板块内按日收益复利的强弱排序，并披露实际数据日与滞后 |

当前 51 项服务能力按聚合入口分布为：基本面 8 项、估值 3 项、技术与风险 31 项、
资金与筹码 5 项、回购进展 1 项、事件研究 1 项、市场宽度 1 项、板块轮动 1 项。仍有 8 项缺口：
一致预期修正、股东与机构行为、总股东回报可以用现有接口补齐；公告证据、治理风险、
新闻事件、新闻情绪和微观结构需要派生能力或新数据源。逐项机器可读状态以能力目录为准。

这些接口只输出可复现的研究事实和指标，不输出买卖建议。估值模型不会在缺少增长、
折现率等显式假设时伪造“合理价格”。

### 技术结构的确认口径

- `levels.fibonacci_retracement` 只使用最近两个已确认 ZigZag 拐点，最后一个实时拐点
  永远不作为锚点；返回 23.6%、38.2%、50%、61.8%、78.6% 回撤和
  127.2%、161.8%、200% 扩展。
- `chan_analysis` 先消除 K 线包含关系，再生成确认分型、笔、三笔延伸线段候选、
  三笔价格交集形成的中枢、MACD 面积背驰以及一二三类买卖点候选。缠论流派在笔和
  线段定义上并不统一，因此接口固定披露本系统采用的规则，所有买卖点都标记为候选，
  不能直接作为交易指令。
- 两项结构分析都在 `1d`、`1w`、`1mo` 独立计算；最新周/月聚合棒明确标记为
  `period_complete=false`，可以描述盘中/期内状态，但不会参与分型、笔、中枢或确认波段锚点。

仍需其他数据才能可靠补充的技术能力包括：分钟级锚定 VWAP、成交量分布、盘口订单
失衡、冲击成本和期权隐含波动率曲面。系统不会使用日线成交额或收盘价伪造这些结果。
当传入基准时，`relative_strength.risk_metrics` 还会按 20/60/120/250 个共同交易日返回
Beta、相关性、零无风险利率 Alpha、年化跟踪误差和信息比率；不传基准时不会猜测。
股票和基金类资产必须先通过 `adj_factor` 或 `fund_adj` 转为最新因子基准；因子覆盖不全
时缩短分析范围并告警，不允许混用原始与复权价格制造虚假收益或缺口。

量价契约位于 `volume_price.analysis`：返回量能 Z-Score/历史分位、价量四象限、20周期
突破量能确认、OBV/A-D 背离、PVT、A/D、Force Index、Ease of Movement、换手率归一化
和20/60/120周期及年初锚定的日线VWAP代理。代理使用日K典型价与成交量，不能冒充盘中
VWAP或真实成交量分布；CVD、主动买卖、盘口失衡和冲击成本仍需逐笔或Level-2数据。

## 待补采的现有接口

补采工作按以下顺序执行。后一阶段只有在前一阶段任务无活动失败、完整性证据通过后
才应启动，避免高基数扇出挤占日常采集资源。

1. `major_news`：从 2018 年起按“来源×日”建立可恢复任务；单来源命中 400 行上限时
   自动细分到更小时间窗口，上限响应不能作为完整。当前 Token 实测仅 40 次/天且
   20 次/分钟，系统按 35 次/上海自然日和 3.2 秒最小间隔留出安全余量；小任务保证
   限频恢复时不丢失已经完成的来源/日期；这些叶子按月形成持久化批次，
   并由独立 `worker-news` 执行，避免新闻额度拖住其他初始化和历史补采；
2. `report_rc`：卖方预测和评级历史，目标从 2010 年开始；
3. `top10_holders`、`top10_floatholders`、`fund_portfolio`、`hk_hold`、
   `stk_holdertrade`、`stk_holdernumber`：股东与机构行为；
4. `dividend`、`repurchase`、`share_float`：总股东回报与资本行动；
5. `cyq_chips`、`cyq_perf`：筹码数据，按股票和不超过 31 天窗口限速扇出；
6. `stk_mins`：分钟行情。当前 Token 限制为每天 2 次，只能做小范围证券池，不能
   声称完成全市场历史。

`full` 初始化计划 v6 已内置前五组研究历史，以及 `adj_factor`、`fund_daily`、
`fund_adj`、`sge_daily`、`ths_daily` 的逐交易日完整分区，不再依赖安装后人工运行
一次性的修复脚本。分钟行情
仍作为明确的受限项留在预检提醒中，系统不会虚假承诺全市场完成。

补采成功不能只看任务 `success`。每个分区必须有请求范围、分页耗尽或安全扇出证据，
并在标准表中核对起止日期、实体覆盖和行数变化。

补采由 `scripts/manage_research_backfills.py` 管理；`--group next` 只会在前一组没有
活动任务、未解决失败且完整性均通过后推进。查看持久化进度：

```bash
docker compose run --rm api python scripts/manage_research_backfills.py --status
```

`GET /api/v1/research/capabilities` 会同步返回每组的任务数、活动数、完成数、未解决
失败和实际状态，Agent 不需要根据进程日志猜测补采是否完成。

## 新数据源待办

### 官方公告全文

- 来源候选：上交所、深交所、北交所及公司公告；
- 最低契约：证券实体、公告时间、公告类型、原文地址/内容、文档哈希、可引用段落；
- 用途：公告证据、治理、诉讼、监管处分和风险事件。

### 持续新闻与舆情

- `major_news` 已有完整采集策略，但历史回填是否完成仍以持久化任务和覆盖证据为准；
- 最低契约：来源、发布时间、标题、正文、实体绑定、去重和更正关系；
- 用途：新闻冲击、事件检测和情绪变化。

### 逐笔成交与 Level-2

- 当前 Tushare 目录没有满足研究要求的历史委托簿；
- 必须先解决授权、供应商、时序身份、压缩存储和恢复能力；
- 用途：订单失衡、冲击成本和微观结构研究。

## Agent 调用约束

Agent 只使用研究层；标准、运营和审计层分别供数据工程、系统管理和排障使用，
不作为 Agent 的下钻通道。历史研究必须传 `as_of`，并检查响应中的
`meta.quality` 和 `provenance`。
CLI 与 REST 对应，例如：

```bash
./clawq research readiness
./clawq research capabilities
./clawq research fundamentals 000001.SZ --periods 8 --as-of 2026-09-18
./clawq research technicals 000001.SZ --benchmark 399006.SZ --chart-points 120
./clawq research instrument-technicals index 000688.SH --benchmark 000300.SH
./clawq research instrument-technicals etf 512480.SH --benchmark 000300.SH
./clawq research instrument-technicals sector 884229.TI --provider ths
./clawq research instrument-technicals spot Au99.99
./clawq research repurchase-progress 300750.SZ
./clawq research market-breadth
./clawq research sector-rotation ths --lookback-days 60
./clawq research calendar --start-date 2026-09-01 --end-date 2026-09-30
```
