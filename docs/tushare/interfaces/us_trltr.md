# `us_trltr` — 国债实际长期利率平均值

- 分类：宏观经济/国际宏观/美国利率
- 功能：国债实际长期利率平均值
- Token 权限：**有权限**（接口返回成功）
- 官方权限要求：用户积累120积分可以使用，积分越高频次越高。具体请参阅 积分获取办法
- 官方文档：[doc 223](https://tushare.pro/document/2?doc_id=223)
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
| `ltr_avg` | float | Y | 实际平均利率LT Real Average (10> Yrs) |

## HTTP 请求示例

```bash
curl -X POST 'http://api.tushare.pro' \
  -H 'Content-Type: application/json' \
  -d '{
  "api_name": "us_trltr",
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

df = pro.us_trltr(start_date='20180101', end_date='20200327')


#获取指定字段
df = pro.us_trltr(start_date='20180101', end_date='20200327', fields='ltr_avg')
```

## 实际返回示例（官方文档）

```text
date ltr_avg
0     20200327   -0.02
1     20200326   -0.05
2     20200325    0.01
3     20200324   -0.04
4     20200323    0.04
...        ...     ...
1995  20120404    0.57
1996  20120403    0.58
1997  20120402    0.53
1998  20120330    0.57
1999  20120329    0.51
```

## claw-quant 存储契约

该接口采用两阶段持久化：上游响应先无损写入 `tushare_raw_record`，随后按契约转换到
强类型标准表 `tushare_norm_us_trltr`。标准表字段、类型、日期列、系统血缘字段和
稳定性规则见[标准化表契约](../tables/us_trltr.md)。转换失败记录进入
`sys_tushare_normalization_error`，契约外字段保存在 `_extra_payload` 并登记到
`sys_tushare_schema_drift`；原始响应始终可用于修复后重放。

> 权限状态来自实际 Token 探测；示例中的 Token 仅为环境变量占位符，不包含真实密钥。
