# `sw_daily` — 申万行业日线行情

- 分类：指数专题
- 功能：获取申万行业日线行情（默认是申万2021版行情）
- Token 权限：**有权限**（接口返回成功）
- 官方权限要求：官方页面未单独声明
- 官方文档：[doc 327](https://tushare.pro/document/2?doc_id=327)
- HTTP：`POST http://api.tushare.pro`
- claw-quant：已实现（契约通用采集器：原始层+强类型标准表）；代码：[collectors/tushare_raw.py:CatalogRawCollector](../../../collectors/tushare_raw.py)

## 输入契约

| 参数 | 类型 | 必选 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | N | 行业代码 |
| `trade_date` | str | N | 交易日期 |
| `start_date` | str | N | 开始日期 |
| `end_date` | str | N | 结束日期 |

## 输出契约

| 字段 | 类型 | 默认显示 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | Y | 指数代码 |
| `trade_date` | str | Y | 交易日期 |
| `name` | str | Y | 指数名称 |
| `open` | float | Y | 开盘点位 |
| `low` | float | Y | 最低点位 |
| `high` | float | Y | 最高点位 |
| `close` | float | Y | 收盘点位 |
| `change` | float | Y | 涨跌点位 |
| `pct_change` | float | Y | 涨跌幅 |
| `vol` | float | Y | 成交量（万股） |
| `amount` | float | Y | 成交额（万元） |
| `pe` | float | Y | 市盈率 |
| `pb` | float | Y | 市净率 |
| `float_mv` | float | Y | 流通市值（万元） |
| `total_mv` | float | Y | 总市值（万元） |

## HTTP 请求示例

```bash
curl -X POST 'http://api.tushare.pro' \
  -H 'Content-Type: application/json' \
  -d '{
  "api_name": "sw_daily",
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

#获取20230705当日所有申万行业指数的ts_code,name,open,close,vol,pe,pb数据
df = pro.sw_daily(trade_date='20230705', fields='ts_code,name,open,close,vol,pe,pb')
```

## 实际返回示例（官方文档）

```text
ts_code      name      open     close         vol      pe    pb
0    801001.SI      申万50   2972.86   2946.53   275984.00   13.99  1.91
1    801002.SI      申万中小   6963.37   6896.69  1540720.00   21.19  2.47
2    801003.SI      申万Ａ指   3793.91   3769.63  6294567.00   16.56  1.78
3    801005.SI      申万创业   2841.32   2815.48  1220719.00   35.90  3.72
4    801010.SI      农林牧渔   2986.75   2946.60    83532.00   28.32  2.66
..         ...       ...       ...       ...         ...     ...   ...
434  859811.SI      生活用纸   1438.09   1418.16     2542.00   23.25  2.32
435  859821.SI  化妆品制造及其他   2674.85   2674.57     2069.00   40.63  2.33
436  859822.SI     品牌化妆品  12094.45  11877.03     2809.00   44.55  5.52
437  859852.SI      培训教育    780.30    770.10    20889.00  106.12  5.73
438  859951.SI     电视广播Ⅲ   1121.00   1122.06    24413.00   51.46  1.05
```

## claw-quant 存储契约

该接口采用两阶段持久化：上游响应先无损写入 `tushare_raw_record`，随后按契约转换到
强类型标准表 `tushare_norm_sw_daily`。标准表字段、类型、日期列、系统血缘字段和
稳定性规则见[标准化表契约](../tables/sw_daily.md)。转换失败记录进入
`sys_tushare_normalization_error`，契约外字段保存在 `_extra_payload` 并登记到
`sys_tushare_schema_drift`；原始响应始终可用于修复后重放。

> 权限状态来自实际 Token 探测；示例中的 Token 仅为环境变量占位符，不包含真实密钥。
