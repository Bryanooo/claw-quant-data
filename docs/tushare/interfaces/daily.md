# `daily` — A股日线行情

- 分类：股票数据/行情数据
- 功能：获取股票行情数据，或通过 通用行情接口 获取数据，包含了前后复权数据
- Token 权限：**有权限**（接口返回成功）
- 官方权限要求：官方页面未单独声明
- 官方调用上限：每次 6,000 条；系统以 5,000 行 offset 分页并要求短页耗尽证据
- 官方文档：[doc 27](https://tushare.pro/document/2?doc_id=27)
- HTTP：`POST http://api.tushare.pro`
- claw-quant：已实现；代码：[collectors/stock/market/daily.py:DailyCollector](../../../collectors/stock/market/daily.py)

## 输入契约

| 参数 | 类型 | 必选 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | N | 股票代码（支持多个股票同时提取，逗号分隔） |
| `trade_date` | str | N | 交易日期（YYYYMMDD） |
| `start_date` | str | N | 开始日期(YYYYMMDD) |
| `end_date` | str | N | 结束日期(YYYYMMDD) |

## 输出契约

| 字段 | 类型 | 默认显示 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | Y | 股票代码 |
| `trade_date` | str | Y | 交易日期 |
| `open` | float | Y | 开盘价 |
| `high` | float | Y | 最高价 |
| `low` | float | Y | 最低价 |
| `close` | float | Y | 收盘价 |
| `pre_close` | float | Y | 昨收价【除权价】 |
| `change` | float | Y | 涨跌额 |
| `pct_chg` | float | Y | 涨跌幅（%） 【基于除权后的昨收计算的涨跌幅：（今收-除权昨收）/除权昨收 】 |
| `vol` | float | Y | 成交量 （手） |
| `amount` | float | Y | 成交额 （千元） |
| `ah_vol` | float | N | 盘后成交量 （手） |
| `ah_amount` | float | N | 盘后成交额 （千元） |

## HTTP 请求示例

```bash
curl -X POST 'http://api.tushare.pro' \
  -H 'Content-Type: application/json' \
  -d '{
  "api_name": "daily",
  "token": "${TUSHARE_TOKEN}",
  "params": {
    "trade_date": "20260829"
  },
  "fields": ""
}'
```

## 官方 SDK 示例

```python
pro = ts.pro_api()

#提取单个股票，跨时间段的历史日线
df = pro.daily(ts_code='000001.SZ', start_date='20180701', end_date='20180718')
```

## 实际返回示例（官方文档）

```text
ts_code     trade_date  open  high   low  close  pre_close  change    pct_chg  vol        amount
0  000001.SZ   20180718  8.75  8.85  8.69   8.70       8.72   -0.02       -0.23   525152.77   460697.377
1  000001.SZ   20180717  8.74  8.75  8.66   8.72       8.73   -0.01       -0.11   375356.33   326396.994
2  000001.SZ   20180716  8.85  8.90  8.69   8.73       8.88   -0.15       -1.69   689845.58   603427.713
3  000001.SZ   20180713  8.92  8.94  8.82   8.88       8.88    0.00        0.00   603378.21   535401.175
4  000001.SZ   20180712  8.60  8.97  8.58   8.88       8.64    0.24        2.78  1140492.31  1008658.828
5  000001.SZ   20180711  8.76  8.83  8.68   8.78       8.98   -0.20       -2.23   851296.70   744765.824
6  000001.SZ   20180710  9.02  9.02  8.89   8.98       9.03   -0.05       -0.55   896862.02   803038.965
7  000001.SZ   20180709  8.69  9.03  8.68   9.03       8.66    0.37        4.27  1409954.60  1255007.609
8  000001.SZ   20180706  8.61  8.78  8.45   8.66       8.60    0.06        0.70   988282.69   852071.526
9  000001.SZ   20180705  8.62  8.73  8.55   8.60       8.61   -0.01       -0.12   835768.77   722169.579
```

## claw-quant 存储契约

该接口由专用采集器写入规范化业务表，主键和字段转换以链接代码为准。按交易日
采集时使用标准 `limit/offset` 穷尽分页，只有短页证明 `exhausted=true` 后任务才会
标记为 `complete`；恰好 1,000 行的历史截面不会再被误报，真实分页上限仍会被拦截。

> 权限状态来自实际 Token 探测；示例中的 Token 仅为环境变量占位符，不包含真实密钥。
