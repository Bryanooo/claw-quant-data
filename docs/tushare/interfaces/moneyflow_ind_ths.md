# `moneyflow_ind_ths` — 同花顺行业资金流向（THS）

- 分类：股票数据/资金流向数据
- 功能：获取同花顺行业资金流向，每日盘后更新
- Token 权限：**有权限**（接口返回成功）
- 官方权限要求：6000积分可以调取，具体请参阅 积分获取办法
- 官方文档：[doc 343](https://tushare.pro/document/2?doc_id=343)
- HTTP：`POST http://api.tushare.pro`
- claw-quant：已实现；代码：[collectors/stock/moneyflow/moneyflow_ind_ths.py:MoneyflowIndThsCollector](../../../collectors/stock/moneyflow/moneyflow_ind_ths.py)

## 输入契约

| 参数 | 类型 | 必选 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | N | 代码 |
| `trade_date` | str | N | 交易日期(YYYYMMDD格式，下同) |
| `start_date` | str | N | 开始日期 |
| `end_date` | str | N | 结束日期 |

## 输出契约

| 字段 | 类型 | 默认显示 | 说明 |
|---|---|:---:|---|
| `trade_date` | str | Y | 交易日期 |
| `ts_code` | str | Y | 板块代码 |
| `industry` | str | Y | 板块名称 |
| `lead_stock` | str | Y | 领涨股票名称 |
| `close` | float | Y | 收盘指数 |
| `pct_change` | float | Y | 指数涨跌幅 |
| `company_num` | int | Y | 公司数量 |
| `pct_change_stock` | float | Y | 领涨股涨跌幅 |
| `close_price` | float | Y | 领涨股最新价 |
| `net_buy_amount` | float | Y | 流入资金(亿元) |
| `net_sell_amount` | float | Y | 流出资金(亿元) |
| `net_amount` | float | Y | 净额(亿元) |

## HTTP 请求示例

```bash
curl -X POST 'http://api.tushare.pro' \
  -H 'Content-Type: application/json' \
  -d '{
  "api_name": "moneyflow_ind_ths",
  "token": "${TUSHARE_TOKEN}",
  "params": {
    "trade_date": "20260829"
  },
  "fields": ""
}'
```

## 官方 SDK 示例

```python
#获取当日所有同花顺行业资金流向
df = pro.moneyflow_ind_ths(trade_date='20240927')
```

## 实际返回示例（官方文档）

```text
trade_date   ts_code industry     close  company_num net_buy_amount net_sell_amount net_amount
0    20240927  881267.TI     能源金属  15021.70           16         490.00           46.00       3.00
1    20240927  881273.TI       白酒   3251.85           20        1890.00          179.00      10.00
2    20240927  881279.TI     光伏设备   5940.19           70        1120.00           94.00      17.00
3    20240927  881157.TI       证券   1407.41           50        3680.00          319.00      49.00
4    20240927  877137.TI     软件开发   1375.49          137        2260.00          204.00      22.00
..        ...        ...      ...       ...          ...            ...             ...        ...
85   20240927  881148.TI     港口航运    901.87           37         190.00           20.00      -1.00
86   20240927  881105.TI   煤炭开采加工   2271.57           34         220.00           26.00      -4.00
87   20240927  881169.TI      贵金属   2141.46           12         240.00           32.00      -8.00
88   20240927  881149.TI   公路铁路运输   1224.59           31         210.00           29.00      -7.00
89   20240927  877035.TI       银行   1080.14           84        1190.00          159.00     -40.00

[90 rows x 8 columns]
```

## claw-quant 存储契约

该接口由专用采集器写入规范化业务表，主键和字段转换以链接代码为准。

> 权限状态来自实际 Token 探测；示例中的 Token 仅为环境变量占位符，不包含真实密钥。
