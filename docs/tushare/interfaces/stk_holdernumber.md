# `stk_holdernumber` — 股东人数

- 分类：股票数据/参考数据
- 功能：获取上市公司股东户数数据，数据不定期公布
- Token 权限：**有权限**（接口返回成功）
- 官方权限要求：2000积分可调取，基础积分每分钟调取200次，5000积分以上频次相对较高。具体请参阅 积分获取办法
- 官方文档：[doc 166](https://tushare.pro/document/2?doc_id=166)
- HTTP：`POST http://api.tushare.pro`
- claw-quant：已实现；代码：[collectors/stock/reference/stk_holdernumber.py:StkHoldernumberCollector](../../../collectors/stock/reference/stk_holdernumber.py)

## 输入契约

| 参数 | 类型 | 必选 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | N | TS股票代码 |
| `ann_date` | str | N | 公告日期 |
| `enddate` | str | N | 截止日期 |
| `start_date` | str | N | 公告开始日期 |
| `end_date` | str | N | 公告结束日期 |

## 输出契约

| 字段 | 类型 | 默认显示 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | Y | TS股票代码 |
| `ann_date` | str | Y | 公告日期 |
| `end_date` | str | Y | 截止日期 |
| `holder_num` | int | Y | 股东户数 |

## HTTP 请求示例

```bash
curl -X POST 'http://api.tushare.pro' \
  -H 'Content-Type: application/json' \
  -d '{
  "api_name": "stk_holdernumber",
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

df = pro.stk_holdernumber(ts_code='300199.SZ', start_date='20160101', end_date='20181231')
```

## 实际返回示例（官方文档）

```text
ts_code  ann_date  end_date  holder_num
0   300199.SZ  20181025  20180930       25135
1   300199.SZ  20180808  20180630       25785
2   300199.SZ  20180426  20180331       23384
3   300199.SZ  20180316  20180228       23490
4   300199.SZ  20180316  20171231       24086
5   300199.SZ  20171026  20170930       24121
6   300199.SZ  20170817  20170630       26271
7   300199.SZ  20170427  20170331       24531
8   300199.SZ  20170427  20161231       22972
9   300199.SZ  20161028  20161027       19787
10  300199.SZ  20161027  20160930       19787
11  300199.SZ  20160804  20160630       20050
12  300199.SZ  20160428  20160331       23367
```

## claw-quant 存储契约

该接口由专用采集器写入规范化业务表，主键和字段转换以链接代码为准。

> 权限状态来自实际 Token 探测；示例中的 Token 仅为环境变量占位符，不包含真实密钥。
