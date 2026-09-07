# `disclosure_date` — 财报披露计划

- 分类：股票数据/财务数据
- 功能：获取财报披露计划日期
- Token 权限：**有权限**（接口返回成功）
- 官方权限要求：用户需要至少2000积分才可以调取，积分越多权限越大，具体请参阅 积分获取办法
- 官方文档：[doc 162](https://tushare.pro/document/2?doc_id=162)
- HTTP：`POST http://api.tushare.pro`
- claw-quant：已实现；代码：[collectors/stock/finance/disclosure_date.py:DisclosureDateCollector](../../../collectors/stock/finance/disclosure_date.py)

## 输入契约

| 参数 | 类型 | 必选 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | N | TS股票代码 |
| `end_date` | str | N | 财报周期（每个季度最后一天的日期，比如20181231表示2018年年报，20180630表示中报) |
| `pre_date` | str | N | 计划披露日期 |
| `ann_date` | str | N | 最新披露公告日 |
| `actual_date` | str | N | 实际披露日期 |

## 输出契约

| 字段 | 类型 | 默认显示 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | Y | TS代码 |
| `ann_date` | str | Y | 最新披露公告日 |
| `end_date` | str | Y | 报告期 |
| `pre_date` | str | Y | 预计披露日期 |
| `actual_date` | str | Y | 实际披露日期 |
| `modify_date` | str | N | 披露日期修正记录 |

## HTTP 请求示例

```bash
curl -X POST 'http://api.tushare.pro' \
  -H 'Content-Type: application/json' \
  -d '{
  "api_name": "disclosure_date",
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

df = pro.disclosure_date(end_date='20181231')
```

## 实际返回示例（官方文档）

```text
ts_code  ann_date  end_date  pre_date actual_date modify_date
0     300619.SZ  20181228  20181231  20190122    20190122        None
1     300125.SZ  20181228  20181231  20190129    20190129        None
2     601619.SH  20181227  20181231  20190129    20190129        None
3     000055.SZ  20181228  20181231  20190130    20190130        None
4     002910.SZ  20181228  20181231  20190131        None        None
5     002188.SZ  20181228  20181231  20190131        None        None
6     600738.SH  20190124  20181231  20190131        None        None
7     002107.SZ  20181228  20181231  20190201        None        None
8     300748.SZ  20181228  20181231  20190201        None        None
9     002675.SZ  20181228  20181231  20190201        None        None
10    002167.SZ  20181228  20181231  20190201        None        None
11    002211.SZ  20190125  20181231  20190201        None        None
12    002240.SZ  20181228  20181231  20190201        None        None
13    002245.SZ  20181228  20181231  20190201        None        None
14    002552.SZ  20181228  20181231  20190201        None        None
15    002825.SZ  20181228  20181231  20190201        None        None
```

## claw-quant 存储契约

该接口由专用采集器写入规范化业务表，主键和字段转换以链接代码为准。

> 权限状态来自实际 Token 探测；示例中的 Token 仅为环境变量占位符，不包含真实密钥。
