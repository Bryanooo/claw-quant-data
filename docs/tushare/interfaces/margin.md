# `margin` — 融资融券交易汇总

- 分类：股票数据/两融及转融通
- 功能：获取融资融券每日交易汇总数据，交易所于每天8点30左右更新上一日数据，本接口最晚9点05分会更新完数据。
- Token 权限：**有权限**（接口返回成功）
- 官方权限要求：2000积分可获得本接口权限，积分越高权限越大，具体参考 权限说明
- 官方文档：[doc 58](https://tushare.pro/document/2?doc_id=58)
- HTTP：`POST http://api.tushare.pro`
- claw-quant：已实现；代码：[collectors/stock/margin/margin.py:MarginCollector](../../../collectors/stock/margin/margin.py)

## 输入契约

| 参数 | 类型 | 必选 | 说明 |
|---|---|:---:|---|
| `trade_date` | str | N | 交易日期（格式：YYYYMMDD，下同） |
| `start_date` | str | N | 开始日期 |
| `end_date` | str | N | 结束日期 |
| `exchange_id` | str | N | 交易所代码（SSE上交所SZSE深交所BSE北交所） |

## 输出契约

| 字段 | 类型 | 默认显示 | 说明 |
|---|---|:---:|---|
| `trade_date` | str | 交易日期 |  |
| `exchange_id` | str | 交易所代码（SSE上交所SZSE深交所BSE北交所） |  |
| `rzye` | float | 融资余额(元) |  |
| `rzmre` | float | 融资买入额(元) |  |
| `rzche` | float | 融资偿还额(元) |  |
| `rqye` | float | 融券余额(元) |  |
| `rqmcl` | float | 融券卖出量(股,份,手) |  |
| `rzrqye` | float | 融资融券余额(元) |  |
| `rqyl` | float | 融券余量(股,份,手) |  |

## HTTP 请求示例

```bash
curl -X POST 'http://api.tushare.pro' \
  -H 'Content-Type: application/json' \
  -d '{
  "api_name": "margin",
  "token": "${TUSHARE_TOKEN}",
  "params": {
    "trade_date": "20260829"
  },
  "fields": ""
}'
```

## 官方 SDK 示例

```python
pro = ts.pro_api()

df = pro.margin(trade_date='20180802')
```

## 实际返回示例（官方文档）

```text
trade_date exchange_id          rzye         rzmre         rzche  \
0   20180802        SZSE  3.495054e+11  1.347549e+10  1.463921e+10
1   20180802         SSE  5.311746e+11  1.484584e+10  1.573947e+10

           rqye       rqmcl        rzrqye
0  1.083380e+09  24418046.0  3.505888e+11
1  6.029618e+09  83721012.0  5.372042e+11
```

## claw-quant 存储契约

该接口由专用采集器写入规范化业务表，主键和字段转换以链接代码为准。

> 权限状态来自实际 Token 探测；示例中的 Token 仅为环境变量占位符，不包含真实密钥。
