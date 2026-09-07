# `us_tycr` — 国债收益率曲线利率（日频）

- 分类：宏观经济/国际宏观/美国利率
- 功能：获取美国每日国债收益率曲线利率
- Token 权限：**有权限**（接口返回成功）
- 官方权限要求：用户积累120积分可以使用，积分越高频次越高。具体请参阅 积分获取办法
- 官方文档：[doc 219](https://tushare.pro/document/2?doc_id=219)
- HTTP：`POST http://api.tushare.pro`
- claw-quant：已实现（契约通用采集器：原始层+强类型标准表）；代码：[collectors/tushare_raw.py:CatalogRawCollector](../../../collectors/tushare_raw.py)

## 输入契约

| 参数 | 类型 | 必选 | 说明 |
|---|---|:---:|---|
| `date` | str | N | 日期 （YYYYMMDD格式，下同） |
| `start_date` | str | N | 开始日期 |
| `end_date` | str | N | 结束日期 |
| `fields` | str | N | 指定输出字段（e.g. fields='m1,y1'） |

## 输出契约

| 字段 | 类型 | 默认显示 | 说明 |
|---|---|:---:|---|
| `date` | str | Y | 日期 |
| `m1` | float | Y | 1月期 |
| `m2` | float | Y | 2月期 |
| `m3` | float | Y | 3月期 |
| `m4` | float | Y | 4月期（数据从20221019开始） |
| `m6` | float | Y | 6月期 |
| `y1` | float | Y | 1年期 |
| `y2` | float | Y | 2年期 |
| `y3` | float | Y | 3年期 |
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
  "api_name": "us_tycr",
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

df = pro.us_tycr(start_date='20180101', end_date='20200327')


#获取1月期和1年期数据
df = pro.us_tycr(start_date='20180101', end_date='20200327', fields='m1,y1')
```

## 实际返回示例（官方文档）

```text
date    m1    m2    m3    m6    y1    y2    y3    y5    y7   y10   y20   y30
0     20200327  0.01  0.03  0.03  0.02  0.11  0.25  0.30  0.41  0.60  0.72  1.09  1.29
1     20200326  0.01  0.01  0.00  0.04  0.13  0.30  0.36  0.51  0.72  0.83  1.20  1.42
2     20200325  0.00  0.00  0.00  0.07  0.19  0.34  0.41  0.56  0.77  0.88  1.23  1.45
3     20200324  0.01  0.01  0.01  0.09  0.25  0.38  0.44  0.52  0.75  0.84  1.19  1.39
4     20200323  0.01  0.04  0.02  0.08  0.17  0.28  0.31  0.38  0.63  0.76  1.12  1.33
...        ...   ...   ...   ...   ...   ...   ...   ...   ...   ...   ...   ...   ...
1995  20120405  0.07  None  0.08  0.14  0.19  0.35  0.50  1.01  1.56  2.19  2.97  3.32
1996  20120404  0.08  None  0.08  0.14  0.19  0.35  0.53  1.05  1.62  2.25  3.02  3.37
1997  20120403  0.07  None  0.08  0.15  0.20  0.36  0.56  1.10  1.68  2.30  3.07  3.41
1998  20120402  0.05  None  0.08  0.14  0.18  0.33  0.50  1.03  1.60  2.22  3.00  3.35
1999  20120330  0.05  None  0.07  0.15  0.19  0.33  0.51  1.04  1.61  2.23  3.00  3.35
```

## claw-quant 存储契约

该接口采用两阶段持久化：上游响应先无损写入 `tushare_raw_record`，随后按契约转换到
强类型标准表 `tushare_norm_us_tycr`。标准表字段、类型、日期列、系统血缘字段和
稳定性规则见[标准化表契约](../tables/us_tycr.md)。转换失败记录进入
`sys_tushare_normalization_error`，契约外字段保存在 `_extra_payload` 并登记到
`sys_tushare_schema_drift`；原始响应始终可用于修复后重放。

> 权限状态来自实际 Token 探测；示例中的 Token 仅为环境变量占位符，不包含真实密钥。
