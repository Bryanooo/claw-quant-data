# `daily_basic` — 每日指标

- 分类：股票数据/行情数据
- 功能：获取全部股票每日重要的基本面指标，可用于选股分析、报表展示等。单次请求最大返回6000条数据，可按日线循环提取全部历史。
- Token 权限：**有权限**（接口返回成功）
- 官方权限要求：至少2000积分才可以调取，5000积分无总量限制，具体请参阅 积分获取办法
- 官方文档：[doc 32](https://tushare.pro/document/2?doc_id=32)
- HTTP：`POST http://api.tushare.pro`
- claw-quant：已实现（契约通用采集器：原始层+强类型标准表）；代码：[collectors/tushare_raw.py:CatalogRawCollector](../../../collectors/tushare_raw.py)

## 输入契约

| 参数 | 类型 | 必选 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | Y | 股票代码（二选一） |
| `trade_date` | str | N | 交易日期 （二选一） |
| `start_date` | str | N | 开始日期(YYYYMMDD) |
| `end_date` | str | N | 结束日期(YYYYMMDD) |

## 输出契约

| 字段 | 类型 | 默认显示 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | Y | TS股票代码 |
| `trade_date` | str | Y | 交易日期 |
| `close` | float | Y | 当日收盘价 |
| `turnover_rate` | float | Y | 换手率 (成交量/无限售流通股数) |
| `turnover_rate_f` | float | Y | 换手率（自由流通股）(成交量/自由流通股数) |
| `volume_ratio` | float | Y | 量比 VOL/MA |
| `pe` | float | Y | 市盈率（总市值/净利润， 亏损的PE为空） |
| `pe_ttm` | float | Y | 市盈率（ 总市值/净利润TTM，亏损的PE为空） |
| `pb` | float | Y | 市净率（总市值/(净资产-其他权益工具)） |
| `ps` | float | Y | 市销率 (总市值/营业收入(最新年报)) |
| `ps_ttm` | float | Y | 市销率（TTM）(总市值/营业收入TTM) |
| `dv_ratio` | float | Y | 股息率 （%），除息日发生在去年期间的派现 |
| `dv_ttm` | float | Y | 股息率（TTM）（%），除息日在近12个月且分红报告期在12个月以内的派现 |
| `total_share` | float | Y | 总股本 （万股） |
| `float_share` | float | Y | 流通股本 （万股） |
| `free_share` | float | Y | 自由流通股本 （万） |
| `total_mv` | float | Y | 总市值 （万元） |
| `circ_mv` | float | Y | 流通市值（万元） |
| `limit_status` | int | N | 收盘涨跌状态：0-平盘，1-上涨(不含涨停)，2-涨停(不含一字涨停)，3-一字涨停，4-下跌(不含跌停)，5-跌停(不含一字跌停)，6-一字跌停 |

## HTTP 请求示例

```bash
curl -X POST 'http://api.tushare.pro' \
  -H 'Content-Type: application/json' \
  -d '{
  "api_name": "daily_basic",
  "token": "${TUSHARE_TOKEN}",
  "params": {
    "ts_code": "000001.SZ"
  },
  "fields": ""
}'
```

## 官方 SDK 示例

```python
pro = ts.pro_api()

df = pro.daily_basic(ts_code='', trade_date='20180726', fields='ts_code,trade_date,turnover_rate,volume_ratio,pe,pb')
```

## 实际返回示例（官方文档）

```text
ts_code     trade_date  turnover_rate  volume_ratio        pe       pb
0     600230.SH   20180726         2.4584          0.72    8.6928   3.7203
1     600237.SH   20180726         1.4737          0.88  166.4001   1.8868
2     002465.SZ   20180726         0.7489          0.72   71.8943   2.6391
3     300732.SZ   20180726         6.7083          0.77   21.8101   3.2513
4     600007.SH   20180726         0.0381          0.61   23.7696   2.3774
5     300068.SZ   20180726         1.4583          0.52   27.8166   1.7549
6     300552.SZ   20180726         2.0728          0.95   56.8004   2.9279
7     601369.SH   20180726         0.2088          0.95   44.1163   1.8001
8     002518.SZ   20180726         0.5814          0.76   15.1004   2.5626
9     002913.SZ   20180726        12.1096          1.03   33.1279   2.9217
10    601818.SH   20180726         0.1893          0.86    6.3064   0.7209
11    600926.SH   20180726         0.6065          0.46    9.1772   0.9808
12    002166.SZ   20180726         0.7582          0.82   16.9868   3.3452
13    600841.SH   20180726         0.3754          1.02   66.2647   2.2302
14    300634.SZ   20180726        23.1127          1.26  120.3053  14.3168
15    300126.SZ   20180726         1.2304          1.11  348.4306   1.5171
16    300718.SZ   20180726        17.6612          0.92   32.0239   3.8661
17    000708.SZ   20180726         0.5575          0.70   10.3674   1.0276
18    002626.SZ   20180726         0.6187          0.83   22.7580   4.2446
19    600816.SH   20180726         0.6745          0.65   11.0778   3.2214
```

## claw-quant 存储契约

该接口采用两阶段持久化：上游响应先无损写入 `tushare_raw_record`，随后按契约转换到
强类型标准表 `tushare_norm_daily_basic`。标准表字段、类型、日期列、系统血缘字段和
稳定性规则见[标准化表契约](../tables/daily_basic.md)。转换失败记录进入
`sys_tushare_normalization_error`，契约外字段保存在 `_extra_payload` 并登记到
`sys_tushare_schema_drift`；原始响应始终可用于修复后重放。

> 权限状态来自实际 Token 探测；示例中的 Token 仅为环境变量占位符，不包含真实密钥。
