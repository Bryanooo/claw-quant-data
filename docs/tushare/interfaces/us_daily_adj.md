# `us_daily_adj` — 美股复权行情

- 分类：美股数据
- 功能：获取美股复权行情，支持美股全市场股票，提供股本、市值、复权因子和成交信息等多个数据指标
- Token 权限：**无权限**（Tushare 明确返回无访问权限）
- 官方权限要求：官方页面未单独声明
- 官方文档：[doc 338](https://tushare.pro/document/2?doc_id=338)
- HTTP：`POST http://api.tushare.pro`
- claw-quant：未实现；代码：无

## 输入契约

| 参数 | 类型 | 必选 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | N | 股票代码（e.g. AAPL） |
| `trade_date` | str | N | 交易日期（YYYYMMDD） |
| `start_date` | str | N | 开始日期（YYYYMMDD） |
| `end_date` | str | N | 结束日期（YYYYMMDD） |
| `exchange` | str | N | 交易所（NAS/NYS/OTC) |
| `offset` | int | N | 开始行数 |
| `limit` | int | N | 每页行数行数 |

## 输出契约

| 字段 | 类型 | 默认显示 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | Y | 股票代码 |
| `trade_date` | str | Y | 交易日期 |
| `close` | float | Y | 收盘价 |
| `open` | float | Y | 开盘价 |
| `high` | float | Y | 最高价 |
| `low` | float | Y | 最低价 |
| `pre_close` | float | Y | 昨收价 |
| `change` | float | Y | 涨跌额 |
| `pct_change` | float | Y | 涨跌幅 |
| `vol` | int | Y | 成交量 |
| `amount` | float | Y | 成交额 |
| `vwap` | float | Y | 平均价 |
| `adj_factor` | float | Y | 复权因子 |
| `turnover_ratio` | float | Y | 换手率 |
| `free_share` | int | Y | 流通股本 |
| `total_share` | int | Y | 总股本 |
| `free_mv` | float | Y | 流通市值 |
| `total_mv` | float | Y | 总市值 |
| `exchange` | str | Y | 交易所代码 |

## HTTP 请求示例

```bash
curl -X POST 'http://api.tushare.pro' \
  -H 'Content-Type: application/json' \
  -d '{
  "api_name": "us_daily_adj",
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

#获取单一股票行情
df = pro.us_daily_adj(ts_code='AAPL', start_date='20240101', end_date='20240722')

#获取某一日某个交易所的全部股票
df = pro.us_daily_adj(trade_date='20240722', exhange='NAS')
```

## 实际返回示例（官方文档）

```text
ts_code trade_date   close pre_close pct_change       vol            amount    vwap adj_factor turnover_ratio
0      AAPL   20240722  223.96    224.31       0.00  48201836  10846348215.6184  225.02     1.0000           0.31
1      AAPL   20240719  224.31    224.18       0.00  49151454  11046273687.7475  224.74     1.0000           0.32
2      AAPL   20240718  224.18    228.88      -0.02  66034563  14869485263.3655  225.18     1.0000           0.43
3      AAPL   20240717  228.88    234.82      -0.03  57345883  13120715665.5056  228.80     1.0000           0.37
4      AAPL   20240716  234.82    234.40       0.00  43234278  10128420808.7874  234.27     1.0000           0.28
..      ...        ...     ...       ...        ...       ...               ...     ...        ...            ...
134    AAPL   20240108  185.07    180.70       0.02  59144469  10903064025.6147  183.86     0.9974           0.38
135    AAPL   20240105  180.70    181.43       0.00  62379661  11321622148.8560  181.02     0.9974           0.40
136    AAPL   20240104  181.43    183.77      -0.01  71983563  13102384071.8889  181.54     0.9974           0.47
137    AAPL   20240103  183.77    185.15      -0.01  58414461  10767233840.9328  183.84     0.9974           0.38
138    AAPL   20240102  185.15    192.02      -0.04  82488688  15330365936.2928  185.36     0.9974           0.53
```

## claw-quant 存储契约

当前 Token 不可采集或接口不可直接调用，因此没有启用运行时采集。

> 权限状态来自实际 Token 探测；示例中的 Token 仅为环境变量占位符，不包含真实密钥。
