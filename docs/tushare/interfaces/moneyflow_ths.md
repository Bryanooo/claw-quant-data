# `moneyflow_ths` — 个股资金流向（THS）

- 分类：股票数据/资金流向数据
- 功能：获取同花顺个股资金流向数据，每日盘后更新
- Token 权限：**有权限**（接口返回成功）
- 官方权限要求：6000积分可调取，具体请参阅 积分获取办法
- 官方文档：[doc 348](https://tushare.pro/document/2?doc_id=348)
- HTTP：`POST http://api.tushare.pro`
- claw-quant：已实现；代码：[collectors/stock/moneyflow/moneyflow_ths.py:MoneyflowThsCollector](../../../collectors/stock/moneyflow/moneyflow_ths.py)

## 输入契约

| 参数 | 类型 | 必选 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | N | 股票代码 |
| `trade_date` | str | N | 交易日期（YYYYMMDD格式，下同） |
| `start_date` | str | N | 开始日期 |
| `end_date` | str | N | 结束日期 |

## 输出契约

| 字段 | 类型 | 默认显示 | 说明 |
|---|---|:---:|---|
| `trade_date` | str | Y | 交易日期 |
| `ts_code` | str | Y | 股票代码 |
| `name` | str | Y | 股票名称 |
| `pct_change` | float | Y | 涨跌幅 |
| `latest` | float | Y | 最新价 |
| `net_amount` | float | Y | 资金净流入(万元) |
| `net_d5_amount` | float | Y | 5日主力净额(万元) |
| `buy_lg_amount` | float | Y | 今日大单净流入额(万元) |
| `buy_lg_amount_rate` | float | Y | 今日大单净流入占比(%) |
| `buy_md_amount` | float | Y | 今日中单净流入额(万元) |
| `buy_md_amount_rate` | float | Y | 今日中单净流入占比(%) |
| `buy_sm_amount` | float | Y | 今日小单净流入额(万元) |
| `buy_sm_amount_rate` | float | Y | 今日小单净流入占比(%) |

## HTTP 请求示例

```bash
curl -X POST 'http://api.tushare.pro' \
  -H 'Content-Type: application/json' \
  -d '{
  "api_name": "moneyflow_ths",
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

#获取单日全部股票数据
df = pro.moneyflow_ths(trade_date='20241011')

#获取单个股票数据
df = pro.moneyflow_ths(ts_code='002149.SZ', start_date='20241001', end_date='20241011')
```

## 实际返回示例（官方文档）

```text
trade_date ts_code  name  pct_change  ...  buy_md_amount  buy_md_amount_rate  buy_sm_amount  buy_sm_amount_rate
0   20241011  002149.SZ  西部材料        2.47  ...         -589.0                5.43         -191.0                1.76
1   20241010  002149.SZ  西部材料        1.22  ...        -2732.0               15.38        -1031.0                5.81
2   20241009  002149.SZ  西部材料        7.00  ...        -1941.0                9.25        -2079.0                9.90
3   20241008  002149.SZ  西部材料        5.17  ...        -2985.0                7.93        -2507.0                6.66
```

## claw-quant 存储契约

该接口由专用采集器写入规范化业务表，主键和字段转换以链接代码为准。

> 权限状态来自实际 Token 探测；示例中的 Token 仅为环境变量占位符，不包含真实密钥。
