# `stk_week_month_adj` — 股票周/月线行情(复权--每日更新)

- 分类：股票数据/行情数据
- 功能：股票周/月线行情(复权--每日更新)
- Token 权限：**有权限**（接口返回成功）
- 官方权限要求：用户需要至少2000积分才可以调取，具体请参阅 积分获取办法
- 官方文档：[doc 365](https://tushare.pro/document/2?doc_id=365)
- HTTP：`POST http://api.tushare.pro`
- claw-quant：已实现（契约通用采集器：原始层+强类型标准表）；代码：[collectors/tushare_raw.py:CatalogRawCollector](../../../collectors/tushare_raw.py)

## 输入契约

| 参数 | 类型 | 必选 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | N | TS代码 |
| `trade_date` | str | N | 交易日期（格式：YYYYMMDD，每周或每月最后一天的日期） |
| `start_date` | str | N | 开始交易日期 |
| `end_date` | str | N | 结束交易日期 |
| `freq` | str | Y | 频率week周，month月 |

## 输出契约

| 字段 | 类型 | 默认显示 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | Y | 股票代码 |
| `trade_date` | str | Y | 交易日期（每周五或者月末日期） |
| `end_date` | str | Y | 计算截至日期 |
| `freq` | str | Y | 频率(周week,月month) |
| `open` | float | Y | (周/月)开盘价 |
| `high` | float | Y | (周/月)最高价 |
| `low` | float | Y | (周/月)最低价 |
| `close` | float | Y | (周/月)收盘价 |
| `pre_close` | float | Y | 上一(周/月)收盘价【除权价，前复权】 |
| `open_qfq` | float | Y | 前复权(周/月)开盘价 |
| `high_qfq` | float | Y | 前复权(周/月)最高价 |
| `low_qfq` | float | Y | 前复权(周/月)最低价 |
| `close_qfq` | float | Y | 前复权(周/月)收盘价 |
| `open_hfq` | float | Y | 后复权(周/月)开盘价 |
| `high_hfq` | float | Y | 后复权(周/月)最高价 |
| `low_hfq` | float | Y | 后复权(周/月)最低价 |
| `close_hfq` | float | Y | 后复权(周/月)收盘价 |
| `vol` | float | Y | (周/月)成交量 |
| `amount` | float | Y | (周/月)成交额 |
| `change` | float | Y | (周/月)涨跌额 |
| `pct_chg` | float | Y | (周/月)涨跌幅 【基于除权后的昨收计算的涨跌幅：（今收-除权昨收）/除权昨收 】 |

## HTTP 请求示例

```bash
curl -X POST 'http://api.tushare.pro' \
  -H 'Content-Type: application/json' \
  -d '{
  "api_name": "stk_week_month_adj",
  "token": "${TUSHARE_TOKEN}",
  "params": {
    "freq": "D"
  },
  "fields": ""
}'
```

## 官方 SDK 示例

```python
pro = ts.pro_api()

df=pro.stk_week_month_adj(ts_code='000001.SZ',freq='week')
```

## 实际返回示例（官方文档）

```text
ts_code  trade_date  freq   open   high    low  close  pre_close  open_qfq  high_qfq  low_qfq  close_qfq  open_hfq  high_hfq  low_hfq  close_hfq         vol      amount  change  pct_chg
0     000001.SZ   20250117  week  11.25  11.59  11.08  11.45      11.30     11.25     11.59    11.08      11.45   1437.57   1481.02  1415.85    1463.13  4353954.80  4963695.53    0.15     0.01
1     000001.SZ   20250110  week  11.38  11.63  11.22  11.30      11.38     11.38     11.63    11.22      11.30   1454.18   1486.13  1433.74    1443.96  4445402.00  5079074.95   -0.08    -0.01
2     000001.SZ   20250103  week  11.78  11.99  11.36  11.38      11.83     11.78     11.99    11.36      11.38   1505.30   1532.13  1451.63    1454.18  5801491.12  6781578.23   -0.45    -0.04
3     000001.SZ   20241227  week  11.64  12.02  11.64  11.83      11.62     11.64     12.02    11.64      11.83   1487.41   1535.96  1487.41    1511.69  6775611.59  8011303.78    0.21     0.02
4     000001.SZ   20241220  week  11.56  11.74  11.52  11.62      11.56     11.56     11.74    11.52      11.62   1477.18   1500.19  1472.07    1484.85  4036452.70  4689640.57    0.06     0.01
...         ...        ...   ...    ...    ...    ...    ...        ...       ...       ...      ...        ...       ...       ...      ...        ...         ...         ...     ...      ...
1687  000001.SZ   19910503  week  43.90  43.90  43.24  43.24      44.34      0.34      0.48     0.34       0.48     43.90     61.24    43.68      60.93       11.00       48.00   -1.10    -0.02
1688  000001.SZ   19910426  week  45.00  45.00  44.34  44.34      45.46      0.35      0.35     0.35       0.35     45.00     45.00    44.34      44.34       67.00      300.00   -1.12    -0.02
1689  000001.SZ   19910419  week  46.38  46.38  45.69  45.69      47.08      0.36      0.36     0.36       0.36     46.38     46.38    45.69      45.69        9.00       41.00   -1.39    -0.03
1690  000001.SZ   19910412  week  48.04  48.04  47.08  47.08      48.52      0.38      0.38     0.37       0.37     48.04     48.04    47.08      47.08       29.00      138.00   -1.44    -0.03
1691  000001.SZ   19910405  week  48.76  48.76  48.52  48.52      49.00      0.38      0.38     0.38       0.38     48.76     48.76    48.52      48.52        5.00       25.00   -0.48    -0.01
```

## claw-quant 存储契约

该接口采用两阶段持久化：上游响应先无损写入 `tushare_raw_record`，随后按契约转换到
强类型标准表 `tushare_norm_stk_week_month_adj`。标准表字段、类型、日期列、系统血缘字段和
稳定性规则见[标准化表契约](../tables/stk_week_month_adj.md)。转换失败记录进入
`sys_tushare_normalization_error`，契约外字段保存在 `_extra_payload` 并登记到
`sys_tushare_schema_drift`；原始响应始终可用于修复后重放。

> 权限状态来自实际 Token 探测；示例中的 Token 仅为环境变量占位符，不包含真实密钥。
