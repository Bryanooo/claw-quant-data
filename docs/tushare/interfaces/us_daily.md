# `us_daily` — 美股行情

- 分类：美股数据
- 功能：获取美股行情（未复权），包括全部股票全历史行情，以及重要的市场和估值指标
- Token 权限：**无权限**（Tushare 明确返回无访问权限）
- 官方权限要求：官方页面未单独声明
- 官方文档：[doc 254](https://tushare.pro/document/2?doc_id=254)
- HTTP：`POST http://api.tushare.pro`
- claw-quant：未实现；代码：无

## 输入契约

| 参数 | 类型 | 必选 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | N | 股票代码（e.g. AAPL） |
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
| `change` | float | N | 涨跌额 |
| `pct_change` | float | Y | 涨跌幅 |
| `vol` | float | Y | 成交量 |
| `amount` | float | Y | 成交额 |
| `vwap` | float | Y | 平均价 |
| `turnover_ratio` | float | N | 换手率 |
| `total_mv` | float | N | 总市值 |
| `pe` | float | N | PE |
| `pb` | float | N | PB |

## HTTP 请求示例

```bash
curl -X POST 'http://api.tushare.pro' \
  -H 'Content-Type: application/json' \
  -d '{
  "api_name": "us_daily",
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
df = pro.us_daily(ts_code='AAPL', start_date='20190101', end_date='20190904')

#获取某一日所有股票
df = pro.us_daily(trade_date='20190904')
```

## 实际返回示例（官方文档）

```text
ts_code trade_date   close    open    high     low pre_close pct_change       vol              amount    vwap
0      AAPL   20190904  209.19  208.39  209.48  207.32    205.70       1.70  19216821   4008342529.970000  208.59
1      AAPL   20190903  205.70  206.43  206.98  204.22    208.74      -1.46  20059575   4120106317.760000  205.39
2      AAPL   20190830  208.74  210.16  210.45  207.20    209.01      -0.13  21162563   4410472824.780000  208.41
3      AAPL   20190829  209.01  208.50  209.32  206.66    205.53       1.69  21007653   4380322743.230000  208.51
4      AAPL   20190828  205.53  204.10  205.72  203.32    204.16       0.67  15957633   3269889907.950000  204.91
..      ...        ...     ...     ...     ...     ...       ...        ...       ...                 ...     ...
165    AAPL   20190108  150.75  149.56  151.82  148.52    147.93       1.91  41025313   6159076907.780000  150.13
166    AAPL   20190107  147.93  148.70  148.83  145.90    148.26      -0.22  54777766   8071925608.900000  147.36
167    AAPL   20190104  148.26  144.53  148.55  143.80    142.19       4.27  58607071   8605786116.450000  146.84
168    AAPL   20190103  142.19  143.98  145.72  142.00    157.92      -9.96  91312188  13108586866.810000  143.56
169    AAPL   20190102  157.92  154.89  158.85  154.23    157.74       0.11  37039739   5814198206.330000  156.97
```

## claw-quant 存储契约

当前 Token 不可采集或接口不可直接调用，因此没有启用运行时采集。

> 权限状态来自实际 Token 探测；示例中的 Token 仅为环境变量占位符，不包含真实密钥。
