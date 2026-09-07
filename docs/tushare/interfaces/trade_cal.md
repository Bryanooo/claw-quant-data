# `trade_cal` — 交易日历

- 分类：股票数据/基础数据
- 功能：获取各大交易所交易日历数据,默认提取的是上交所
- Token 权限：**有权限**（接口返回成功）
- 官方权限要求：需2000积分
- 官方文档：[doc 26](https://tushare.pro/document/2?doc_id=26)
- HTTP：`POST http://api.tushare.pro`
- claw-quant：已实现；代码：[collectors/stock/basic/trade_cal.py:TradeCalCollector](../../../collectors/stock/basic/trade_cal.py)

## 输入契约

| 参数 | 类型 | 必选 | 说明 |
|---|---|:---:|---|
| `exchange` | str | N | 交易所 SSE上交所,SZSE深交所,CFFEX 中金所,SHFE 上期所,CZCE 郑商所,DCE 大商所,INE 上能源 |
| `start_date` | str | N | 开始日期 （格式：YYYYMMDD 下同） |
| `end_date` | str | N | 结束日期 |
| `is_open` | str | N | 是否交易 '0'休市 '1'交易 |

## 输出契约

| 字段 | 类型 | 默认显示 | 说明 |
|---|---|:---:|---|
| `exchange` | str | Y | 交易所 SSE上交所 SZSE深交所 |
| `cal_date` | str | Y | 日历日期 |
| `is_open` | str | Y | 是否交易 0休市 1交易 |
| `pretrade_date` | str | Y | 上一个交易日 |

## HTTP 请求示例

```bash
curl -X POST 'http://api.tushare.pro' \
  -H 'Content-Type: application/json' \
  -d '{
  "api_name": "trade_cal",
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


df = pro.trade_cal(exchange='', start_date='20180101', end_date='20181231')
```

## 实际返回示例（官方文档）

```text
exchange  cal_date  is_open
0           SSE  20180101        0
1           SSE  20180102        1
2           SSE  20180103        1
3           SSE  20180104        1
4           SSE  20180105        1
5           SSE  20180106        0
6           SSE  20180107        0
7           SSE  20180108        1
8           SSE  20180109        1
9           SSE  20180110        1
10          SSE  20180111        1
11          SSE  20180112        1
12          SSE  20180113        0
13          SSE  20180114        0
14          SSE  20180115        1
15          SSE  20180116        1
16          SSE  20180117        1
17          SSE  20180118        1
18          SSE  20180119        1
19          SSE  20180120        0
20          SSE  20180121        0
```

## claw-quant 存储契约

该接口由专用采集器写入规范化业务表，主键和字段转换以链接代码为准。

> 权限状态来自实际 Token 探测；示例中的 Token 仅为环境变量占位符，不包含真实密钥。
