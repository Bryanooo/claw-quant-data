# `us_tltr` — 国债长期利率

- 分类：宏观经济/国际宏观/美国利率
- 功能：国债长期利率
- Token 权限：**有权限**（接口返回成功）
- 官方权限要求：用户积累120积分可以使用，积分越高频次越高。具体请参阅 积分获取办法
- 官方文档：[doc 222](https://tushare.pro/document/2?doc_id=222)
- HTTP：`POST http://api.tushare.pro`
- claw-quant：已实现（契约通用采集器：原始层+强类型标准表）；代码：[collectors/tushare_raw.py:CatalogRawCollector](../../../collectors/tushare_raw.py)

## 输入契约

| 参数 | 类型 | 必选 | 说明 |
|---|---|:---:|---|
| `date` | str | N | 日期 |
| `start_date` | str | N | 开始日期 |
| `end_date` | str | N | 结束日期 |
| `fields` | str | N | 指定字段 |

## 输出契约

| 字段 | 类型 | 默认显示 | 说明 |
|---|---|:---:|---|
| `date` | str | Y | 日期 |
| `ltc` | float | Y | 收益率 LT COMPOSITE (>10 Yrs) |
| `cmt` | float | Y | 20年期CMT利率(TREASURY 20-Yr CMT) |
| `e_factor` | float | Y | 外推因子EXTRAPOLATION FACTOR |

## HTTP 请求示例

```bash
curl -X POST 'http://api.tushare.pro' \
  -H 'Content-Type: application/json' \
  -d '{
  "api_name": "us_tltr",
  "token": "${TUSHARE_TOKEN}",
  "params": {
    "start_date": "20260730",
    "end_date": "20260829"
  },
  "fields": ""
}'
```

## 官方 SDK 示例

```python
pro = ts.pro_api()

df = pro.us_tltr(start_date='20180101', end_date='20200327')


#获取5年期和20年期数据
df = pro.us_tltr(start_date='20180101', end_date='20200327', fields='ltc,cmt')
```

## 实际返回示例（官方文档）

```text
date   ltc   cmt e_factor
0     20200327  1.19  1.09     None
1     20200326  1.32  1.20     None
2     20200325  1.35  1.23     None
3     20200324  1.30  1.19     None
4     20200323  1.25  1.12     None
...        ...   ...   ...      ...
1995  20120404  2.98  3.02     None
1996  20120403  3.02  3.07     None
1997  20120402  2.96  3.00     None
1998  20120330  2.96  3.00     None
1999  20120329  2.89  2.93     None
```

## claw-quant 存储契约

该接口采用两阶段持久化：上游响应先无损写入 `tushare_raw_record`，随后按契约转换到
强类型标准表 `tushare_norm_us_tltr`。标准表字段、类型、日期列、系统血缘字段和
稳定性规则见[标准化表契约](../tables/us_tltr.md)。转换失败记录进入
`sys_tushare_normalization_error`，契约外字段保存在 `_extra_payload` 并登记到
`sys_tushare_schema_drift`；原始响应始终可用于修复后重放。

> 权限状态来自实际 Token 探测；示例中的 Token 仅为环境变量占位符，不包含真实密钥。
