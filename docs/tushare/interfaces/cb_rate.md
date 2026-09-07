# `cb_rate` — 可转债票面利率

- 分类：债券专题
- 功能：获取可转债票面利率
- Token 权限：**有权限**（接口返回成功）
- 官方权限要求：用户需要至少5000积分才可以调取，具体请参阅 积分获取办法
- 官方文档：[doc 305](https://tushare.pro/document/2?doc_id=305)
- HTTP：`POST http://api.tushare.pro`
- claw-quant：已实现（契约通用采集器：原始层+强类型标准表）；代码：[collectors/tushare_raw.py:CatalogRawCollector](../../../collectors/tushare_raw.py)

## 输入契约

| 参数 | 类型 | 必选 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | Y | 转债代码，支持多值输入 |

## 输出契约

| 字段 | 类型 | 默认显示 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | Y | 转债代码 |
| `rate_freq` | int | N | 付息频率(次/年) |
| `rate_start_date` | str | N | 付息开始日期 |
| `rate_end_date` | str | N | 付息结束日期 |
| `coupon_rate` | float | N | 票面利率(%) |

## HTTP 请求示例

```bash
curl -X POST 'http://api.tushare.pro' \
  -H 'Content-Type: application/json' \
  -d '{
  "api_name": "cb_rate",
  "token": "${TUSHARE_TOKEN}",
  "params": {
    "ts_code": "110000.SH"
  },
  "fields": ""
}'
```

## 官方 SDK 示例

```python
pro = ts.pro_api(your token)
#获取可转债基础信息列表
df = pro.cb_rate(ts_code='123046.SZ,127064.SZ',fields="ts_code,rate_freq,rate_start_date,rate_end_date,coupon_rate")
```

## 实际返回示例（官方文档）

```text
ts_code  rate_freq rate_start_date rate_end_date coupon_rate
0   123046.SZ          1        20200319      20210318    0.500000
1   123046.SZ          1        20210319      20220318    0.700000
2   123046.SZ          1        20220319      20230318    1.000000
3   123046.SZ          1        20230319      20240318    1.500000
4   123046.SZ          1        20240319      20250318    2.500000
5   123046.SZ          1        20250319      20260318    3.000000
6   127064.SZ          1        20220519      20230518    0.200000
7   127064.SZ          1        20230519      20240518    0.400000
8   127064.SZ          1        20240519      20250518    0.600000
9   127064.SZ          1        20250519      20260518    1.500000
10  127064.SZ          1        20260519      20270518    1.800000
11  127064.SZ          1        20270519      20280518    2.000000
```

## claw-quant 存储契约

该接口采用两阶段持久化：上游响应先无损写入 `tushare_raw_record`，随后按契约转换到
强类型标准表 `tushare_norm_cb_rate`。标准表字段、类型、日期列、系统血缘字段和
稳定性规则见[标准化表契约](../tables/cb_rate.md)。转换失败记录进入
`sys_tushare_normalization_error`，契约外字段保存在 `_extra_payload` 并登记到
`sys_tushare_schema_drift`；原始响应始终可用于修复后重放。

> 权限状态来自实际 Token 探测；示例中的 Token 仅为环境变量占位符，不包含真实密钥。
