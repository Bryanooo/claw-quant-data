# `us_trycr` — 国债实际收益率曲线利率

- 分类：宏观经济/国际宏观/美国利率
- 功能：国债实际收益率曲线利率
- Token 权限：**有权限**（接口返回成功）
- 官方权限要求：用户积累120积分可以使用，积分越高频次越高。具体请参阅 积分获取办法
- 官方文档：[doc 220](https://tushare.pro/document/2?doc_id=220)
- HTTP：`POST http://api.tushare.pro`
- claw-quant：已实现（契约通用采集器：原始层+强类型标准表）；代码：[collectors/tushare_raw.py:CatalogRawCollector](../../../collectors/tushare_raw.py)

## 输入契约

| 参数 | 类型 | 必选 | 说明 |
|---|---|:---:|---|
| `date` | str | N | 日期 （YYYYMMDD格式，下同） |
| `start_date` | str | N | 开始日期 |
| `end_date` | str | N | 结束日期 |
| `fields` | str | N | 指定输出字段 |

## 输出契约

| 字段 | 类型 | 默认显示 | 说明 |
|---|---|:---:|---|
| `date` | str | Y | 日期 |
| `y5` | float | Y | 5年期 |
| `y7` | float | Y | 7年期 |
| `y10` | float | Y | 10年期 |
| `y20` | float | Y | 20年期 |
| `y30` | float | Y | 30年期 |

## HTTP 请求示例

```bash
curl -X POST 'http://api.tushare.pro' \
  -H 'Content-Type: application/json' \
  -d '{
  "api_name": "us_trycr",
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

df = pro.us_trycr(start_date='20180101', end_date='20200327')


#获取5年期和20年期数据
df = pro.us_trycr(start_date='20180101', end_date='20200327', fields='y5,y20')
```

## 实际返回示例（官方文档）

```text
date     y5     y7    y10    y20    y30
0     20200327  -0.13  -0.20  -0.22  -0.12  -0.03
1     20200326  -0.21  -0.24  -0.24  -0.14  -0.05
2     20200325  -0.13  -0.18  -0.19  -0.09   0.00
3     20200324  -0.03  -0.11  -0.13  -0.09  -0.07
4     20200323   0.01  -0.03  -0.04  -0.02  -0.01
...        ...    ...    ...    ...    ...    ...
1995  20120404  -0.91  -0.46  -0.05   0.62   0.94
1996  20120403  -0.94  -0.48  -0.06   0.62   0.94
1997  20120402  -1.01  -0.55  -0.14   0.56   0.89
1998  20120330  -0.98  -0.53  -0.09   0.61   0.93
1999  20120329  -0.98  -0.53  -0.13   0.55   0.87
```

## claw-quant 存储契约

该接口采用两阶段持久化：上游响应先无损写入 `tushare_raw_record`，随后按契约转换到
强类型标准表 `tushare_norm_us_trycr`。标准表字段、类型、日期列、系统血缘字段和
稳定性规则见[标准化表契约](../tables/us_trycr.md)。转换失败记录进入
`sys_tushare_normalization_error`，契约外字段保存在 `_extra_payload` 并登记到
`sys_tushare_schema_drift`；原始响应始终可用于修复后重放。

> 权限状态来自实际 Token 探测；示例中的 Token 仅为环境变量占位符，不包含真实密钥。
