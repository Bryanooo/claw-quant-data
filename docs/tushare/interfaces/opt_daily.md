# `opt_daily` — 期权日线行情

- 分类：期权数据
- 功能：获取期权日线行情
- Token 权限：**有权限**（接口返回成功）
- 官方权限要求：用户需要至少2000积分才可以调取，但有流量控制，请自行提高积分，积分越多权限越大，具体请参阅 积分获取办法
- 官方文档：[doc 159](https://tushare.pro/document/2?doc_id=159)
- HTTP：`POST http://api.tushare.pro`
- claw-quant：已实现（契约通用采集器：原始层+强类型标准表）；代码：[collectors/tushare_raw.py:CatalogRawCollector](../../../collectors/tushare_raw.py)

## 输入契约

| 参数 | 类型 | 必选 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | N | TS合约代码（输入代码或时间至少任意一个参数） |
| `trade_date` | str | N | 交易日期 |
| `start_date` | str | N | 开始日期 |
| `end_date` | str | N | 结束日期 |
| `exchange` | str | N | 交易所(SSE/SZSE/CFFEX/DCE/SHFE/CZCE） |

## 输出契约

| 字段 | 类型 | 默认显示 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | Y | TS代码 |
| `trade_date` | str | Y | 交易日期 |
| `exchange` | str | Y | 交易市场 |
| `pre_settle` | float | Y | 昨结算价 |
| `pre_close` | float | Y | 前收盘价 |
| `open` | float | Y | 开盘价 |
| `high` | float | Y | 最高价 |
| `low` | float | Y | 最低价 |
| `close` | float | Y | 收盘价 |
| `settle` | float | Y | 结算价 |
| `vol` | float | Y | 成交量(手) |
| `amount` | float | Y | 成交金额(万元) |
| `oi` | float | Y | 持仓量(手) |

## HTTP 请求示例

```bash
curl -X POST 'http://api.tushare.pro' \
  -H 'Content-Type: application/json' \
  -d '{
  "api_name": "opt_daily",
  "token": "${TUSHARE_TOKEN}",
  "params": {
    "trade_date": "20260829"
  },
  "fields": ""
}'
```

## 官方 SDK 示例

```python
pro = ts.pro_api('your token')

df = pro.opt_daily(trade_date='20181212')
```

## 实际返回示例（官方文档）

```text
ts_code trade_date exchange  ...      vol       amount       oi
0         10001313.SH   20181212      SSE  ...  38354.0  1261.435472  98882.0
1         10001314.SH   20181212      SSE  ...  14472.0   234.933288  79980.0
2         10001315.SH   20181212      SSE  ...  10092.0    69.311776  72370.0
3         10001316.SH   20181212      SSE  ...   5434.0    16.107224  55117.0
4         10001317.SH   20181212      SSE  ...   4240.0     5.798919  61746.0
..                ...        ...      ...  ...      ...          ...      ...
753  M1911-P-2900.DCE   20181212      DCE  ...      0.0     0.000000     20.0
754  M1911-P-2950.DCE   20181212      DCE  ...      0.0     0.000000     20.0
755  M1911-P-3000.DCE   20181212      DCE  ...      0.0     0.000000     20.0
756  M1911-P-3050.DCE   20181212      DCE  ...      0.0     0.000000     20.0
757  M1911-P-3100.DCE   20181212      DCE  ...      0.0     0.000000      0.0
```

## claw-quant 存储契约

该接口采用两阶段持久化：上游响应先无损写入 `tushare_raw_record`，随后按契约转换到
强类型标准表 `tushare_norm_opt_daily`。标准表字段、类型、日期列、系统血缘字段和
稳定性规则见[标准化表契约](../tables/opt_daily.md)。转换失败记录进入
`sys_tushare_normalization_error`，契约外字段保存在 `_extra_payload` 并登记到
`sys_tushare_schema_drift`；原始响应始终可用于修复后重放。

> 权限状态来自实际 Token 探测；示例中的 Token 仅为环境变量占位符，不包含真实密钥。
