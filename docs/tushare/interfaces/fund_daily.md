# `fund_daily` — ETF日线行情

- 分类：ETF专题
- 功能：获取ETF行情每日收盘后成交数据，历史超过10年
- Token 权限：**有权限**（接口返回成功）
- 官方权限要求：需要至少5000积分才可以调取，8000积分频次更高，具体请参阅 积分获取办法
- 官方文档：[doc 127](https://tushare.pro/document/2?doc_id=127)
- HTTP：`POST http://api.tushare.pro`
- claw-quant：已实现（契约通用采集器：原始层+强类型标准表）；代码：[collectors/tushare_raw.py:CatalogRawCollector](../../../collectors/tushare_raw.py)

## 输入契约

| 参数 | 类型 | 必选 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | N | 基金代码 |
| `trade_date` | str | N | 交易日期(YYYYMMDD格式，下同) |
| `start_date` | str | N | 开始日期 |
| `end_date` | str | N | 结束日期 |

## 输出契约

| 字段 | 类型 | 默认显示 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | Y | TS代码 |
| `trade_date` | str | Y | 交易日期 |
| `open` | float | Y | 开盘价(元) |
| `high` | float | Y | 最高价(元) |
| `low` | float | Y | 最低价(元) |
| `close` | float | Y | 收盘价(元) |
| `pre_close` | float | Y | 昨收盘价(元) |
| `change` | float | Y | 涨跌额(元) |
| `pct_chg` | float | Y | 涨跌幅(%) |
| `vol` | float | Y | 成交量(手) |
| `amount` | float | Y | 成交额(千元) |

## HTTP 请求示例

```bash
curl -X POST 'http://api.tushare.pro' \
  -H 'Content-Type: application/json' \
  -d '{
  "api_name": "fund_daily",
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

#获取”沪深300ETF华夏”ETF2025年以来的行情，并通过fields参数指定输出了部分字段
df = pro.fund_daily(ts_code='510330.SH', start_date='20250101', end_date='20250618', fields='trade_date,open,high,low,close,vol,amount')
```

## 实际返回示例（官方文档）

```text
trade_date   open   high    low  close         vol       amount
0     20250618  4.008  4.024  3.996  4.017   382896.00   153574.446
1     20250617  4.015  4.022  4.000  4.014   440272.04   176617.125
2     20250616  4.000  4.018  3.996  4.015   423526.00   169788.251
3     20250613  4.023  4.028  3.992  4.004  1216787.53   487632.318
4     20250612  4.023  4.039  4.005  4.032   574727.00   231356.321
..         ...    ...    ...    ...    ...         ...          ...
104   20250108  3.971  3.992  3.908  3.963  3200416.00  1267465.456
105   20250107  3.939  3.974  3.929  3.973  2239739.00   885818.954
106   20250106  3.950  3.964  3.917  3.943  1583794.00   624004.760
107   20250103  4.002  4.013  3.944  3.963  2025111.00   805573.289
108   20250102  4.110  4.117  3.973  4.001  1768592.00   714820.885
```

## claw-quant 存储契约

该接口采用两阶段持久化：上游响应先无损写入 `tushare_raw_record`，随后按契约转换到
强类型标准表 `tushare_norm_fund_daily`。标准表字段、类型、日期列、系统血缘字段和
稳定性规则见[标准化表契约](../tables/fund_daily.md)。转换失败记录进入
`sys_tushare_normalization_error`，契约外字段保存在 `_extra_payload` 并登记到
`sys_tushare_schema_drift`；原始响应始终可用于修复后重放。

> 权限状态来自实际 Token 探测；示例中的 Token 仅为环境变量占位符，不包含真实密钥。
