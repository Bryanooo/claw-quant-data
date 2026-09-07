# `fut_settle` — 结算参数

- 分类：期货数据
- 功能：获取每日结算参数数据，包括交易和交割费率等
- Token 权限：**有权限**（接口返回成功）
- 官方权限要求：用户需要至少2000积分才可以调取，具体请参阅 积分获取办法
- 官方文档：[doc 141](https://tushare.pro/document/2?doc_id=141)
- HTTP：`POST http://api.tushare.pro`
- claw-quant：已实现（契约通用采集器：原始层+强类型标准表）；代码：[collectors/tushare_raw.py:CatalogRawCollector](../../../collectors/tushare_raw.py)

## 输入契约

| 参数 | 类型 | 必选 | 说明 |
|---|---|:---:|---|
| `trade_date` | str | N | 交易日期 （trade_date/ts_code至少需要输入一个参数） |
| `ts_code` | str | N | 合约代码 |
| `start_date` | str | N | 开始日期(YYYYMMDD格式，下同) |
| `end_date` | str | N | 结束日期 |
| `exchange` | str | N | 交易所代码 |

## 输出契约

| 字段 | 类型 | 默认显示 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | Y | 合约代码 |
| `trade_date` | str | Y | 交易日期 |
| `settle` | float | Y | 结算价 |
| `trading_fee_rate` | float | Y | 交易手续费率 |
| `trading_fee` | float | Y | 交易手续费 |
| `delivery_fee` | float | Y | 交割手续费 |
| `b_hedging_margin_rate` | float | Y | 买套保交易保证金率 |
| `s_hedging_margin_rate` | float | Y | 卖套保交易保证金率 |
| `long_margin_rate` | float | Y | 买投机交易保证金率 |
| `short_margin_rate` | float | Y | 卖投机交易保证金率 |
| `offset_today_fee` | float | N | 平今仓手续率 |
| `exchange` | str | N | 交易所 |

## HTTP 请求示例

```bash
curl -X POST 'http://api.tushare.pro' \
  -H 'Content-Type: application/json' \
  -d '{
  "api_name": "fut_settle",
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

df = pro.fut_settle(trade_date='20181114', exchange='SHFE')
```

## 实际返回示例（官方文档）

```text
ts_code     trade_date    settle  trading_fee_rate  trading_fee  \
0    CU1811.SHF   20181114  48840.00             0.050           0.0
1    CU1812.SHF   20181114  48990.00             0.050           0.0
2    CU1901.SHF   20181114  48980.00             0.050           0.0
3    CU1902.SHF   20181114  48980.00             0.050           0.0
4    CU1903.SHF   20181114  49020.00             0.050           0.0
5    CU1904.SHF   20181114  49040.00             0.050           0.0
6    CU1905.SHF   20181114  49150.00             0.050           0.0
7    CU1906.SHF   20181114  49260.00             0.050           0.0
8    CU1907.SHF   20181114  49200.00             0.050           0.0
9    CU1908.SHF   20181114  49370.00             0.050           0.0
10   CU1909.SHF   20181114  49350.00             0.050           0.0
11   CU1910.SHF   20181114  49490.00             0.050           0.0
12   AL1811.SHF   20181114  13695.00             0.000           3.0
13   AL1812.SHF   20181114  13770.00             0.000           3.0
14   AL1901.SHF   20181114  13775.00             0.000           3.0
15   AL1902.SHF   20181114  13810.00             0.000           3.0
16   AL1903.SHF   20181114  13860.00             0.000           3.0
17   AL1904.SHF   20181114  13905.00             0.000           3.0
18   AL1905.SHF   20181114  13950.00             0.000           3.0
19   AL1906.SHF   20181114  13965.00             0.000           3.0
20   AL1907.SHF   20181114  14015.00             0.000           3.0

     delivery_fee  b_hedging_margin_rate  s_hedging_margin_rate  \
0            2.00                   0.20                   0.20
1            2.00                   0.10                   0.10
2            2.00                   0.07                   0.07
3            2.00                   0.07                   0.07
4            2.00                   0.07                   0.07
5            2.00                   0.07                   0.07
6            2.00                   0.07                   0.07
7            2.00                   0.07                   0.07
8            2.00                   0.07                   0.07
9            2.00                   0.07                   0.07
10           2.00                   0.07                   0.07
11           2.00                   0.07                   0.07
12           2.00                   0.20                   0.20
13           2.00                   0.10                   0.10
14           2.00                   0.07                   0.07
15           2.00                   0.07                   0.07
16           2.00                   0.07                   0.07
17           2.00                   0.07                   0.07
18           2.00                   0.07                   0.07
19           2.00                   0.07                   0.07
20           2.00                   0.07                   0.07

     long_margin_rate  short_margin_rate
0                0.20               0.20
1                0.10               0.10
2                0.07               0.07
3                0.07               0.07
4                0.07               0.07
5                0.07               0.07
6                0.07               0.07
7                0.07               0.07
8                0.07               0.07
9                0.07               0.07
10               0.07               0.07
11               0.07               0.07
12               0.20               0.20
13               0.10               0.10
14               0.07               0.07
15               0.07               0.07
16               0.07               0.07
17               0.07               0.07
18               0.07               0.07
19               0.07               0.07
20               0.07               0.07
```

## claw-quant 存储契约

该接口采用两阶段持久化：上游响应先无损写入 `tushare_raw_record`，随后按契约转换到
强类型标准表 `tushare_norm_fut_settle`。标准表字段、类型、日期列、系统血缘字段和
稳定性规则见[标准化表契约](../tables/fut_settle.md)。转换失败记录进入
`sys_tushare_normalization_error`，契约外字段保存在 `_extra_payload` 并登记到
`sys_tushare_schema_drift`；原始响应始终可用于修复后重放。

> 权限状态来自实际 Token 探测；示例中的 Token 仅为环境变量占位符，不包含真实密钥。
