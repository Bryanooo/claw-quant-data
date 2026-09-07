# `dc_daily` — 概念板块行情

- 分类：股票数据/打板专题数据
- 功能：获取概念板块、行业指数板块、地域板块行情数据，历史数据开始于2020年
- Token 权限：**有权限**（接口返回成功）
- 官方权限要求：用户积累6000积分可调取，具体请参阅 积分获取办法
- 官方文档：[doc 382](https://tushare.pro/document/2?doc_id=382)
- HTTP：`POST http://api.tushare.pro`
- claw-quant：已实现；代码：[collectors/stock/board/dc_daily.py:DcDailyCollector](../../../collectors/stock/board/dc_daily.py)

## 输入契约

| 参数 | 类型 | 必选 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | N | 板块代码（格式：xxxxx.DC) |
| `trade_date` | str | N | 交易日期(格式：YYYYMMDD下同） |
| `start_date` | str | N | 开始日期 |
| `end_date` | str | N | 结束日期 |
| `idx_type` | str | N | 板块类型： 概念板块、行业板块、地域板块 |

## 输出契约

| 字段 | 类型 | 默认显示 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | Y | 板块代码 |
| `trade_date` | str | Y | 交易日 |
| `close` | float | Y | 收盘点位 |
| `open` | float | Y | 开盘点位 |
| `high` | float | Y | 最高点位 |
| `low` | float | Y | 最低点位 |
| `change` | float | Y | 涨跌点位 |
| `pct_change` | float | Y | 涨跌幅 |
| `vol` | float | Y | 成交量(股) |
| `amount` | float | Y | 成交额(元) |
| `swing` | float | Y | 振幅 |
| `turnover_rate` | float | Y | 换手率 |
| `category` | str | Y | 分类板块 |

## HTTP 请求示例

```bash
curl -X POST 'http://api.tushare.pro' \
  -H 'Content-Type: application/json' \
  -d '{
  "api_name": "dc_daily",
  "token": "${TUSHARE_TOKEN}",
  "params": {
    "trade_date": "20260829"
  },
  "fields": ""
}'
```

## 官方 SDK 示例

```python
#获取2025年5月13日概念板块行情
df = pro.dc_daily(trade_date='20250513')
```

## 实际返回示例（官方文档）

```text
ts_code trade_date       close        open        high         low pct_change
0    BK1063.DC   20250513    792.5200    793.5200    795.0400    786.9000     0.8700
1    BK1051.DC   20250513  12408.8600  12510.2500  12573.2800  12350.8900     4.3700
2    BK0816.DC   20250513     65.8600     66.6700     67.0200     65.4500     3.7700
3    BK0547.DC   20250513  12810.7600  12745.7200  12823.3500  12691.3900     0.6000
4    BK1082.DC   20250513   1306.9800   1337.2300   1342.8900   1302.9700    -1.3900
..         ...        ...         ...         ...         ...         ...        ...
430  BK0915.DC   20250513   1136.7400   1159.1800   1162.3600   1133.9400    -1.0200
431  BK1084.DC   20250513   1481.1500   1514.2300   1517.7200   1476.3200    -0.6100
432  BK0957.DC   20250513   1277.3800   1295.2900   1303.0000   1275.1900    -0.3500
433  BK1156.DC   20250513   1350.4700   1356.8500   1372.2800   1344.9400     0.0100
434  BK0881.DC   20250513   1156.1600   1181.2600   1184.1800   1154.0800    -0.5700
```

## claw-quant 存储契约

该接口由专用采集器写入规范化业务表，主键和字段转换以链接代码为准。

> 权限状态来自实际 Token 探测；示例中的 Token 仅为环境变量占位符，不包含真实密钥。
