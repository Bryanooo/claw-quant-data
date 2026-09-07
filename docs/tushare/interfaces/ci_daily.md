# `ci_daily` — 中信行业指数行情

- 分类：指数专题
- 功能：获取中信行业指数日线行情；中信不再披露高开低成交量成交额字段
- Token 权限：**有权限**（接口返回成功）
- 官方权限要求：5000积分可调取，可通过指数代码和日期参数循环获取所有数据
- 官方文档：[doc 308](https://tushare.pro/document/2?doc_id=308)
- HTTP：`POST http://api.tushare.pro`
- claw-quant：已实现（契约通用采集器：原始层+强类型标准表）；代码：[collectors/tushare_raw.py:CatalogRawCollector](../../../collectors/tushare_raw.py)

## 输入契约

| 参数 | 类型 | 必选 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | N | 行业代码 |
| `trade_date` | str | N | 交易日期（YYYYMMDD格式，下同） |
| `start_date` | str | N | 开始日期 |
| `end_date` | str | N | 结束日期 |

## 输出契约

| 字段 | 类型 | 默认显示 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | Y | 指数代码 |
| `trade_date` | str | Y | 交易日期 |
| `open` | float | Y | 开盘点位 |
| `low` | float | Y | 最低点位 |
| `high` | float | Y | 最高点位 |
| `close` | float | Y | 收盘点位 |
| `pre_close` | float | Y | 昨日收盘点位 |
| `change` | float | Y | 涨跌点位 |
| `pct_change` | float | Y | 涨跌幅 |
| `vol` | float | Y | 成交量（万股） |
| `amount` | float | Y | 成交额（万元） |

## HTTP 请求示例

```bash
curl -X POST 'http://api.tushare.pro' \
  -H 'Content-Type: application/json' \
  -d '{
  "api_name": "ci_daily",
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

df = pro.ci_daily(trade_date='20230705', fields='ts_code,trade_date,open,low,high,close')
```

## 实际返回示例（官方文档）

```text
ts_code   trade_date       open        low       high      close
0    CI005001.CI   20230705  2757.5662  2736.8198  2764.1863  2754.2617
1    CI005002.CI   20230705  3006.7166  3000.1382  3039.3916  3029.7837
2    CI005003.CI   20230705  6443.6250  6431.1250  6597.5933  6588.1401
3    CI005004.CI   20230705  2675.3940  2672.7278  2693.6438  2676.9941
4    CI005005.CI   20230705  1575.1489  1571.6997  1597.4792  1593.6205
..           ...        ...        ...        ...        ...        ...
435  CI005920.CI   20230705  6585.6924  6521.1846  6599.1216  6529.9458
436  CI005921.CI   20230705  2759.9133  2753.9324  2781.3979  2757.9863
437  CI005922.CI   20230705  5690.3843  5645.3955  5690.4165  5652.8184
438  CI005923.CI   20230705  5855.1333  5808.8325  5855.1470  5816.7471
439  CI005924.CI   20230705  5782.8662  5737.0601  5782.8984  5744.5962

[440 rows x 6 columns]
```

## claw-quant 存储契约

该接口采用两阶段持久化：上游响应先无损写入 `tushare_raw_record`，随后按契约转换到
强类型标准表 `tushare_norm_ci_daily`。标准表字段、类型、日期列、系统血缘字段和
稳定性规则见[标准化表契约](../tables/ci_daily.md)。转换失败记录进入
`sys_tushare_normalization_error`，契约外字段保存在 `_extra_payload` 并登记到
`sys_tushare_schema_drift`；原始响应始终可用于修复后重放。

> 权限状态来自实际 Token 探测；示例中的 Token 仅为环境变量占位符，不包含真实密钥。
