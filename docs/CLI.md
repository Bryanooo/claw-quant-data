# clawq：个人与 Agent 数据访问入口

`clawq` 是 `claw-quant-data` REST API 的只读命令行客户端。它的目标是让个人、
脚本和 Agent 使用同一套稳定契约访问数据，而不是依赖数据库表名、手写 SQL 或
临时 `curl` 命令。

## 运行条件

- `claw-quant-data` API 已启动；
- 宿主机有 Python 3.9 或更高版本；
- 不需要在宿主机安装 `requests`、`python-dotenv` 或采集器依赖。

默认 API 地址为 `http://127.0.0.1:8000/api`。可以通过全局参数或环境变量修改：

```bash
./clawq --api-url http://127.0.0.1:8000/api health

export CLAW_QUANT_API_URL=http://127.0.0.1:8000/api
export CLAW_QUANT_TIMEOUT_SECONDS=15
./clawq health
```

API 地址不接受嵌入式用户名、密码、查询字符串或 URL fragment，避免凭据意外进入
进程列表、Shell 历史和日志。

## 命令

### 系统和数据状态

```bash
./clawq health
./clawq health --live-only
./clawq status
./clawq status --full
./clawq freshness
./clawq freshness stock_daily
```

`health` 检查 API 进程和 PostgreSQL 是否可用。`status` 默认返回有界的运行状态、
覆盖摘要、服务心跳和历史初始化进度，适合 Agent 高频预检；`status --full` 才读取
包含全部数据集新鲜度和交付明细的完整健康视图，响应明显更大。

### 数据集发现

```bash
./clawq datasets list
./clawq datasets list --category market
./clawq --pretty datasets describe stock_daily
```

`describe` 返回数据表语义、字段、主键、允许过滤器、日期字段和最大分页大小。
Agent 应先调用 `describe`，不能猜测过滤字段。

### 数据查询

```bash
./clawq query stock_daily \
  --filter ts_code=000001.SZ \
  --start-date 2026-01-01 \
  --end-date 2026-09-08 \
  --limit 100 \
  --include-total
```

可用参数：

| 参数 | 含义 |
|---|---|
| `--filter NAME=VALUE` | 精确过滤，可重复使用；字段必须由数据集契约允许 |
| `--date` | 单一日期或报告期 |
| `--start-date` | 起始日期 |
| `--end-date` | 结束日期 |
| `--as-of` | 按数据可获得日期过滤，避免读到该历史时点尚未公开的数据；仅支持声明了可获得日期字段的数据集 |
| `--limit` | 本页记录数，1 到 1,000 |
| `--offset` | 分页偏移量，必须非负 |
| `--include-total` | 额外计算总行数；大表查询可能更慢 |

CLI 拒绝重复过滤器、空过滤值、非法数据集名和使用 `--filter` 伪造分页参数。

### 股票快照

```bash
./clawq stock snapshot 000001.SZ
```

快照聚合股票基础资料、最近行情、每日基本面、资金流、财务指标、涨跌停和停牌信息。

### 股票研究资料包

```bash
./clawq stock research-pack 300750.SZ \
  --lookback-days 180 \
  --benchmark 399006.SZ \
  --financial-periods 8 \
  --as-of 2026-09-08
```

资料包面向 Agent，一次返回公司资料、行情/估值/资金流/筹码/两融/基准指数、
财务三表与指标、股东/质押/回购/分红，以及 `major_news` 的公司名称/代码关键词
检索结果。`meta.provenance` 逐数据集
保留来源和返回行数，`meta.gaps` 标记所选范围内的空数据集，
`meta.external_data_needed` 说明必须由外部官方来源补齐的资料；新闻关键词命中
不等同于公司公告，当前仍需到交易所或公司公告系统核验。

该命令只聚合原始研究材料，不计算预测、评级或交易建议；衍生分析仍由 Agent 完成。

历史 `--as-of` 不只限制行情日期，也会按 `ann_date` 限制财务报表、业绩预告、
股东和公司行为数据。`meta.quality` 区分确定缺失和无法仅凭空结果确认的
`unknown_empty`，Agent 不得把后者直接解释为“没有发生”。

### 板块研究

```bash
./clawq stock sectors 300750.SZ --provider ths --as-of 2026-09-08
./clawq stock peers 300750.SZ --provider ths --max-sectors 5 --limit 20
./clawq sector list --provider ths --query 人工智能 --market A
./clawq sector list --provider dc --category 概念板块 --as-of 2026-09-08
./clawq sector snapshot tdx 880728.TDX
./clawq sector members dc BK1184.DC --as-of 2026-09-08 --limit 500
./clawq sector research-pack ths 885728.TI \
  --lookback-days 180 --member-limit 500 --as-of 2026-09-08
```

板块供应方固定为 `ths`、`dc`、`tdx`。服务统一返回 `provider`、`sector_code`、
名称、类型、行情和成分语义，但不会错误地把不同供应方的同名板块合并为一个代码。
Research Pack 的 `meta.quality` 会标记行情/成分缺失、成分截断以及资金流是否可用。

### 接口契约和标准数据

```bash
./clawq interfaces list
./clawq interfaces list --permission 有权限
./clawq interfaces list --mode generic_raw
./clawq interfaces describe adj_factor

./clawq interfaces query adj_factor \
  --filter ts_code=000001.SZ \
  --date-field trade_date \
  --start-date 2026-01-01
```

### 覆盖证据

```bash
./clawq coverage summary
./clawq coverage show stock_daily
./clawq coverage show stock_daily \
  --start-date 2026-01-01 \
  --end-date 2026-09-08 \
  --status missing
```

状态可选值为 `present`、`partial`、`missing`、`pending` 和 `observed_only`。

## 输出契约

全局输出参数必须位于具体命令之前：

```bash
./clawq --pretty status
./clawq --output json query stock_daily --limit 10
./clawq --output jsonl query stock_daily --limit 10
./clawq --output csv query stock_daily --limit 10
```

- `json`：默认；保留 API 的 `data`、`meta` 和 `page`；
- `jsonl`：只输出响应中的记录，每行一个 JSON 对象；
- `csv`：只输出响应中的记录；嵌套值编码为紧凑 JSON；
- `--pretty`：只影响 JSON 缩进；
- 成功结果只写 `stdout`；错误只写 `stderr`。

CSV/JSONL 是行式输出，因此不会包含 JSON 响应中的分页和元数据。Agent 需要判断
`has_more`、数据来源或完整性时，应使用默认 JSON。

## 退出码

| 退出码 | 含义 |
|---:|---|
| `0` | 成功 |
| `2` | 命令参数或本地配置无效 |
| `3` | 无法连接 API |
| `4` | 请求超时 |
| `5` | API 返回 4xx |
| `6` | API 返回 5xx |
| `7` | API 返回非 JSON，或无法编码指定输出格式 |
| `130` | 用户中断 |

错误示例：

```json
{"error":{"code":"dataset_not_found","message":"unknown dataset: missing","request_id":"...","status_code":404}}
```

Agent 应根据 `error.code` 和退出码处理失败，不应解析自然语言错误消息。

## Agent 使用约束

建议 Agent 按以下顺序访问：

1. `clawq health`；
2. `clawq status`；
3. `clawq datasets describe <name>`；
4. `clawq freshness <name>` 和 `clawq coverage show <name>`；
5. 使用小 `limit` 验证查询；
6. 再按页读取所需数据；
7. 在结论中标明数据集、日期范围、最新分区和覆盖状态。

第一版 CLI 只有 GET 请求，没有任务提交、重试、初始化、删除或任意 SQL 能力。
需要管理采集时，应由用户在 Dashboard 二次确认，或明确要求使用管理 API。
