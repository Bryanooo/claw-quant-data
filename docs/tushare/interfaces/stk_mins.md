# `stk_mins` — 股票历史分钟行情

- 分类：股票数据/行情数据
- 功能：获取A股分钟数据，支持1min/5min/15min/30min/60min行情，提供Python SDK和 http Restful API两种方式
- Token 权限：**有权限（当前限频）**（Tushare 明确返回该接口的频率上限）
- 官方权限要求：需单独开权限，正式权限请参阅 权限说明 ，可以 在线开通 分钟权限。
- 官方文档：[doc 370](https://tushare.pro/document/2?doc_id=370)
- HTTP：`POST http://api.tushare.pro`
- claw-quant：已实现（契约通用采集器：原始层+强类型标准表）；代码：[collectors/tushare_raw.py:CatalogRawCollector](../../../collectors/tushare_raw.py)

## 输入契约

| 参数 | 类型 | 必选 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | Y | 股票代码，e.g. 600000.SH |
| `freq` | str | Y | 分钟频度（1min/5min/15min/30min/60min） |
| `start_date` | datetime | N | 开始日期 格式：2023-08-25 09:00:00 |
| `end_date` | datetime | N | 结束时间 格式：2023-08-25 19:00:00 |

## 输出契约

| 字段 | 类型 | 默认显示 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | Y | 股票代码 |
| `trade_time` | str | Y | 交易时间 |
| `open` | float | Y | 开盘价 |
| `close` | float | Y | 收盘价 |
| `high` | float | Y | 最高价 |
| `low` | float | Y | 最低价 |
| `vol` | int | Y | 成交量(股) |
| `amount` | float | Y | 成交金额（元） |

## HTTP 请求示例

```bash
curl -X POST 'http://api.tushare.pro' \
  -H 'Content-Type: application/json' \
  -d '{
  "api_name": "stk_mins",
  "token": "${TUSHARE_TOKEN}",
  "params": {
    "ts_code": "000001.SZ",
    "freq": "D"
  },
  "fields": ""
}'
```

## 官方 SDK 示例

```python
pro = ts.pro_api()

#获取浦发银行60000.SH的历史分钟数据
df = pro.stk_mins(ts_code='600000.SH', freq='1min', start_date='2023-08-25 09:00:00', end_date='2023-08-25 19:00:00')
```

## 实际返回示例（官方文档）

```text
ts_code             trade_time  close  open  high   low       vol     amount
0    600000.SH  2023-08-25 15:00:00   7.05  7.05  7.05  7.05  235500.0  1660275.0
1    600000.SH  2023-08-25 14:59:00   7.05  7.05  7.05  7.05       0.0        0.0
2    600000.SH  2023-08-25 14:58:00   7.05  7.05  7.05  7.05       0.0        0.0
3    600000.SH  2023-08-25 14:57:00   7.05  7.06  7.06  7.05   51800.0   365491.0
4    600000.SH  2023-08-25 14:56:00   7.05  7.05  7.06  7.04   92700.0   653831.0
..         ...                  ...    ...   ...   ...   ...       ...        ...
236  600000.SH  2023-08-25 09:34:00   7.01  7.02  7.02  7.00  120500.0   845311.0
237  600000.SH  2023-08-25 09:33:00   7.01  7.01  7.02  7.00  126000.0   883188.0
238  600000.SH  2023-08-25 09:32:00   7.01  7.02  7.02  6.99  236699.0  1659260.0
239  600000.SH  2023-08-25 09:31:00   7.02  6.99  7.02  6.97  807500.0  5649956.0
240  600000.SH  2023-08-25 09:30:00   6.99  6.99  6.99  6.99  103700.0   724863.0
```

## claw-quant 存储契约

该接口采用两阶段持久化：上游响应先无损写入 `tushare_raw_record`，随后按契约转换到
强类型标准表 `tushare_norm_stk_mins`。标准表字段、类型、日期列、系统血缘字段和
稳定性规则见[标准化表契约](../tables/stk_mins.md)。转换失败记录进入
`sys_tushare_normalization_error`，契约外字段保存在 `_extra_payload` 并登记到
`sys_tushare_schema_drift`；原始响应始终可用于修复后重放。

> 权限状态来自实际 Token 探测；示例中的 Token 仅为环境变量占位符，不包含真实密钥。
