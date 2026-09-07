# `cyq_perf` — 每日筹码及胜率

- 分类：股票数据/特色数据
- 功能：获取A股每日筹码平均成本和胜率情况，每天18~19点左右更新，数据从2018年开始 来源：Tushare社区
- Token 权限：**有权限**（接口返回成功）
- 官方权限要求：5000积分每天20000次，10000积分每天200000次，15000积分每天不限总量 算法说明： 参考用“三角分布法”计算，即当天成交的筹码，在最高价、最低价和平均价之间不是平均分配的，而是越接近平均成交价（或均价），成交的筹码越多，形成一个以均价为峰值的三角形分布。 面积 = 1 * /|\ ← 高 h = 2/d / | \ / | \ / | \ / | \ / | \ *------* ------* low avg high ← d = high - low → 新筹码分配（当日成交量）：假设当日成交的总筹码量为 V，当日最高价为 H，最低价为 L，平均价为 A。三角分布法会按照一个三角形模型，将 V 分配到从 L 到 H 的各个价格上。在均价 A 这个价格点上，分配的筹码数量最多，形成三角形的顶点；随着价格远离 A，分配的筹码数量线性减少，直到在 L 和 H 处降至零。 老筹码更新（历史持仓的搬移）：筹码分布图不是只计算当天的，它是一个动态的、每日更新的过程。每天新产生的交易筹码（来自当天成交的换手），需要从原有的历史持仓中“搬移”出来。这个过程引入了历史换手衰减系数的概念。
- 官方文档：[doc 293](https://tushare.pro/document/2?doc_id=293)
- HTTP：`POST http://api.tushare.pro`
- claw-quant：已实现；代码：[collectors/stock/extra/cyq_perf.py:CyqPerfCollector](../../../collectors/stock/extra/cyq_perf.py)

## 输入契约

| 参数 | 类型 | 必选 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | Y | 股票代码 |
| `trade_date` | str | N | 交易日期（YYYYMMDD） |
| `start_date` | str | N | 开始日期 |
| `end_date` | str | N | 结束日期 |

## 输出契约

| 字段 | 类型 | 默认显示 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | Y | 股票代码 |
| `trade_date` | str | Y | 交易日期 |
| `his_low` | float | Y | 历史最低价 |
| `his_high` | float | Y | 历史最高价 |
| `cost_5pct` | float | Y | 5分位成本 |
| `cost_15pct` | float | Y | 15分位成本 |
| `cost_50pct` | float | Y | 50分位成本 |
| `cost_85pct` | float | Y | 85分位成本 |
| `cost_95pct` | float | Y | 95分位成本 |
| `weight_avg` | float | Y | 加权平均成本 |
| `winner_rate` | float | Y | 胜率 |

## HTTP 请求示例

```bash
curl -X POST 'http://api.tushare.pro' \
  -H 'Content-Type: application/json' \
  -d '{
  "api_name": "cyq_perf",
  "token": "${TUSHARE_TOKEN}",
  "params": {
    "ts_code": "000001.SZ"
  },
  "fields": ""
}'
```

## 官方 SDK 示例

```python
pro = ts.pro_api()

df = pro.cyq_perf(ts_code='600000.SH', start_date='20220101', end_date='20220429')
```

## 实际返回示例（官方文档）

```text
面积 = 1
        *
       /|\          ← 高 h = 2/d
      / | \
     /  |  \
    /   |   \
   /    |    \
  /     |     \
 *------*------*
low    avg    high
 ← d = high - low →
```

## claw-quant 存储契约

该接口由专用采集器写入规范化业务表，主键和字段转换以链接代码为准。

> 权限状态来自实际 Token 探测；示例中的 Token 仅为环境变量占位符，不包含真实密钥。
