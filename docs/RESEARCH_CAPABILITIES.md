# Agent 研究能力与数据动作

本项目不再用上游接口数量衡量研究能力，而是从 Agent 需要完成的基本面和技术面
分析倒推数据、计算契约与缺口。上游原始接口仍在 `/api/v1/raw/*`，标准数据仍在
`/api/v1/datasets/*`，确定性派生服务统一位于 `/api/v1/research/*`。

## 为什么使用新的路径

研究派生接口与标准数据接口的契约不同：

- 标准数据接口返回供应方事实记录，不改变业务口径；
- 研究接口执行明确公式、窗口、复权、基准或横截面计算；
- 研究结果必须同时返回 `as_of`、方法说明、数据来源和质量警告；
- Agent 可以解释结果，但不应在每次任务中重新发明指标公式。

现有 `/api/v1/stocks/*` 和 `/api/v1/sectors/*` 保持兼容，用于资料包、板块关系和
基础快照。新的 `/api/v1/research/*` 不替代这些入口。

## 已实现的派生服务

| 接口 | 覆盖能力 |
|---|---|
| `GET /api/v1/research/capabilities` | 能力目录、补采工作流、新数据源待办 |
| `GET /api/v1/research/stocks/{ts_code}/fundamentals` | 财务趋势、盈利、成长、现金质量、偿债、效率、杜邦与主营构成 |
| `GET /api/v1/research/stocks/{ts_code}/valuation` | PE/PB/PS/股息率历史分位、同行中位数、DCF/DDM 输入 |
| `GET /api/v1/research/stocks/{ts_code}/technicals` | 趋势、MACD、RSI、ATR、布林、量价、关键价位、相对强弱、复权收益 |
| `GET /api/v1/research/stocks/{ts_code}/capital-flow` | 个股资金流、两融、北向、大宗和筹码状态 |
| `GET /api/v1/research/stocks/{ts_code}/event-study` | 事件窗口收益、基准收益、异常收益和 CAR |
| `GET /api/v1/research/market/breadth` | 涨跌分布、均线扩散、成交和涨跌停情绪 |
| `GET /api/v1/research/sectors/{provider}/rotation` | THS/DC/TDX 当前有效板块内按日收益复利的强弱排序，并披露实际数据日与滞后 |

这些接口只输出可复现的研究事实和指标，不输出买卖建议。估值模型不会在缺少增长、
折现率等显式假设时伪造“合理价格”。

## 待补采的现有接口

补采工作按以下顺序执行。后一阶段只有在前一阶段任务无活动失败、完整性证据通过后
才应启动，避免高基数扇出挤占日常采集资源。

1. `report_rc`：卖方预测和评级历史，目标从 2010 年开始；
2. `top10_holders`、`top10_floatholders`、`fund_portfolio`、`hk_hold`、
   `stk_holdertrade`、`stk_holdernumber`：股东与机构行为；
3. `dividend`、`repurchase`、`share_float`：总股东回报与资本行动；
4. `cyq_chips`、`cyq_perf`：筹码数据，按股票和不超过 31 天窗口限速扇出；
5. `stk_mins`：分钟行情。当前 Token 限制为每天 2 次，只能做小范围证券池，不能
   声称完成全市场历史。

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

- 当前 `major_news` 数据量不足以形成稳定新闻历史；
- 最低契约：来源、发布时间、标题、正文、实体绑定、去重和更正关系；
- 用途：新闻冲击、事件检测和情绪变化。

### 逐笔成交与 Level-2

- 当前 Tushare 目录没有满足研究要求的历史委托簿；
- 必须先解决授权、供应商、时序身份、压缩存储和恢复能力；
- 用途：订单失衡、冲击成本和微观结构研究。

## Agent 调用约束

Agent 默认使用研究层；需要核对公式输入时读取标准层；只有排障和血缘追踪时读取
原始层。历史研究必须传 `as_of`，并检查响应中的 `meta.quality` 和 `provenance`。
CLI 与 REST 对应，例如：

```bash
./clawq research fundamentals 000001.SZ --periods 8 --as-of 2026-09-18
./clawq research technicals 000001.SZ --benchmark 399006.SZ
./clawq research market-breadth
./clawq research sector-rotation ths --lookback-days 60
```
