# `margin_secs` — 融资融券标的（盘前更新）

- 分类：股票数据/两融及转融通
- 功能：获取沪深京三大交易所融资融券标的（包括ETF），每天盘前更新
- Token 权限：**有权限**（接口返回成功）
- 官方权限要求：2000积分可调取，5000积分无总量限制，积分越高权限越大，具体参考 权限说明
- 官方文档：[doc 326](https://tushare.pro/document/2?doc_id=326)
- HTTP：`POST http://api.tushare.pro`
- claw-quant：已实现；代码：[collectors/stock/margin/margin.py:MarginSecsCollector](../../../collectors/stock/margin/margin.py)

## 输入契约

| 参数 | 类型 | 必选 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | N | 标的代码 |
| `trade_date` | str | N | 交易日 |
| `exchange` | str | N | 交易所（SSE上交所 SZSE深交所 BSE北交所） |
| `start_date` | str | N | 开始日期 |
| `end_date` | str | N | 结束日期 |

## 输出契约

| 字段 | 类型 | 默认显示 | 说明 |
|---|---|:---:|---|
| `trade_date` | str | Y | 交易日期 |
| `ts_code` | str | Y | 标的代码 |
| `name` | str | Y | 标的名称 |
| `exchange` | str | Y | 交易所 |

## HTTP 请求示例

```bash
curl -X POST 'http://api.tushare.pro' \
  -H 'Content-Type: application/json' \
  -d '{
  "api_name": "margin_secs",
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

#获取2024年4月17日上交所融资融券标的
df = pro.margin_secs(trade_date='20240417', exchange='SSE')
```

## 实际返回示例（官方文档）

```text
trade_date     ts_code      name exchange
0      20240417  510050 .SH    50ETF       SSE
1      20240417  510100 .SH  SZ50ETF       SSE
2      20240417  510150 .SH    消费ETF       SSE
3      20240417  510180 .SH   180ETF       SSE
4      20240417  510210 .SH    综指ETF       SSE
...         ...         ...       ...      ...
1781   20240417  688799 .SH     华纳药厂       SSE
1782   20240417  688800 .SH      瑞可达       SSE
1783   20240417  688819 .SH     天能股份       SSE
1784   20240417  688981 .SH     中芯国际       SSE
1785   20240417  689009 .SH     九号公司       SSE
```

## claw-quant 存储契约

该接口由专用采集器写入规范化业务表，主键和字段转换以链接代码为准。

> 权限状态来自实际 Token 探测；示例中的 Token 仅为环境变量占位符，不包含真实密钥。
