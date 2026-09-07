# `hk_daily_adj` — 港股复权行情

- 分类：港股数据
- 功能：获取港股复权行情，提供股票股本、市值和成交及换手多个数据指标
- Token 权限：**无权限**（Tushare 明确返回无访问权限）
- 官方权限要求：官方页面未单独声明
- 官方文档：[doc 339](https://tushare.pro/document/2?doc_id=339)
- HTTP：`POST http://api.tushare.pro`
- claw-quant：未实现；代码：无

## 输入契约

| 参数 | 类型 | 必选 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | N | 股票代码（e.g. 00001.HK） |
| `trade_date` | str | N | 交易日期（YYYYMMDD） |
| `start_date` | str | N | 开始日期（YYYYMMDD） |
| `end_date` | str | N | 结束日期（YYYYMMDD） |

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
| `turnover_ratio` | float | Y | 换手率(基于总股本) |
| `free_share` | int | Y | 流通股本(港股股本) |
| `total_share` | int | Y | 总股本 |
| `free_mv` | float | Y | 流通市值（港股市值） |
| `total_mv` | float | Y | 总市值 |

## HTTP 请求示例

```bash
curl -X POST 'http://api.tushare.pro' \
  -H 'Content-Type: application/json' \
  -d '{
  "api_name": "hk_daily_adj",
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
df = pro.hk_daily_adj(ts_code='00001.HK', start_date='20240101', end_date='20240722')

#获取某一日某个交易所的全部股票
df = pro.hk_daily_adj(trade_date='20240722')
```

## 实际返回示例（官方文档）

```text
ts_code trade_date  close pre_close      vol adj_factor turnover_ratio
0    00001.HK   20240722  40.95     40.90  2799284     1.0000           0.07
1    00001.HK   20240719  40.90     40.85  6472801     1.0000           0.17
2    00001.HK   20240718  40.85     40.50  5498406     1.0000           0.14
3    00001.HK   20240717  40.50     39.95  4151953     1.0000           0.11
4    00001.HK   20240716  39.95     40.15  3978223     1.0000           0.10
..        ...        ...    ...       ...      ...        ...            ...
131  00001.HK   20240108  38.91     39.05  3271763     0.9572           0.09
132  00001.HK   20240105  39.05     39.24  2731319     0.9572           0.07
133  00001.HK   20240104  39.24     39.58  2800255     0.9572           0.07
134  00001.HK   20240103  39.58     39.48  3498817     0.9572           0.09
135  00001.HK   20240102  39.48     40.06  2782895     0.9572           0.07

[136 rows x 7 columns]
```

## claw-quant 存储契约

当前 Token 不可采集或接口不可直接调用，因此没有启用运行时采集。

> 权限状态来自实际 Token 探测；示例中的 Token 仅为环境变量占位符，不包含真实密钥。
