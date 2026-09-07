# `sw_mins` — SW指数历史分钟

- 分类：指数专题
- 功能：获取申万指数历史分钟数据
- Token 权限：**无权限**（Tushare 明确返回无访问权限）
- 官方权限要求：本接口是单独的权限，具体请参阅 积分获取办法
- 官方文档：[doc 469](https://tushare.pro/document/2?doc_id=469)
- HTTP：`POST http://api.tushare.pro`
- claw-quant：未实现；代码：无

## 输入契约

| 参数 | 类型 | 必选 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | Y | 指数代码 |
| `freq` | str | Y | 分钟频度（1min/5min/15min/30min/60min） |
| `start_date` | datetime | N | 开始日期 格式：2023-08-25 09:00:00 |
| `end_date` | datetime | N | 结束时间 格式：2023-08-25 19:00:00 |

## 输出契约

| 字段 | 类型 | 默认显示 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | Y | 指数代码 |
| `trade_time` | str | Y | 交易时间 |
| `open` | float | Y | 开盘点数 |
| `close` | float | Y | 收盘点数 |
| `high` | float | Y | 最高点数 |
| `low` | float | Y | 最低点数 |
| `amount` | float | Y | 成交金额（元） |
| `vol` | float | Y | 成交量（股） |

## HTTP 请求示例

```bash
curl -X POST 'http://api.tushare.pro' \
  -H 'Content-Type: application/json' \
  -d '{
  "api_name": "sw_mins",
  "token": "${TUSHARE_TOKEN}",
  "params": {
    "ts_code": "000001.SH",
    "freq": "D"
  },
  "fields": ""
}'
```

## 官方 SDK 示例

```python
pro = ts.pro_api()

#获取申万Ａ指指数2026-06-03的1分钟数据
df = pro.sw_mins(ts_code='801003.SI', freq='1min', start_date='2026-06-03 09:00:00', end_date='2026-06-03 19:00:00')
```

## 实际返回示例（官方文档）

```text
ts_code         trade_time      open     close      high       low        amount    vol
0    801003.SI  2026-06-03 15:00:00  5028.279  5027.740  5028.279  5027.740  2.694226e+10  1.449213e+09
1    801003.SI  2026-06-03 14:59:00  5031.757  5031.757  5031.757  5031.757  0.000000e+00  0.000000e+00
2    801003.SI  2026-06-03 14:58:00  5031.633  5031.757  5031.757  5031.633  1.078606e+09  6.064699e+07
3    801003.SI  2026-06-03 14:57:00  5029.491  5031.280  5031.280  5029.491  1.712534e+10  9.325039e+08
4    801003.SI  2026-06-03 14:56:00  5028.709  5029.367  5029.429  5028.708  1.485450e+10  7.643498e+08
```

## claw-quant 存储契约

当前 Token 不可采集或接口不可直接调用，因此没有启用运行时采集。

> 权限状态来自实际 Token 探测；示例中的 Token 仅为环境变量占位符，不包含真实密钥。
