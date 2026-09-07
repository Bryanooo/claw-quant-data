# `moneyflow_dc` — 个股资金流向（DC）

- 分类：股票数据/资金流向数据
- 功能：获取东方财富个股资金流向数据，每日盘后更新，数据开始于20230911
- Token 权限：**有权限**（接口返回成功）
- 官方权限要求：用户需要至少5000积分才可以调取，具体请参阅 积分获取办法
- 官方文档：[doc 349](https://tushare.pro/document/2?doc_id=349)
- HTTP：`POST http://api.tushare.pro`
- claw-quant：已实现；代码：[collectors/stock/moneyflow/moneyflow_dc.py:MoneyflowDcCollector](../../../collectors/stock/moneyflow/moneyflow_dc.py)

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
| `close` | float | Y | 最新价 |
| `net_amount` | float | Y | 今日主力净流入额（万元） |
| `net_amount_rate` | float | Y | 今日主力净流入净占比（%） |
| `buy_elg_amount` | float | Y | 今日超大单净流入额（万元） |
| `buy_elg_amount_rate` | float | Y | 今日超大单净流入占比（%） |
| `buy_lg_amount` | float | Y | 今日大单净流入额（万元） |
| `buy_lg_amount_rate` | float | Y | 今日大单净流入占比（%） |
| `buy_md_amount` | float | Y | 今日中单净流入额（万元） |
| `buy_md_amount_rate` | float | Y | 今日中单净流入占比（%） |
| `buy_sm_amount` | float | Y | 今日小单净流入额（万元） |
| `buy_sm_amount_rate` | float | Y | 今日小单净流入占比（%） |

## HTTP 请求示例

```bash
curl -X POST 'http://api.tushare.pro' \
  -H 'Content-Type: application/json' \
  -d '{
  "api_name": "moneyflow_dc",
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
df = pro.moneyflow_dc(trade_date='20241011')

#获取单个股票数据
df = pro.moneyflow_dc(ts_code='002149.SZ', start_date='20240901', end_date='20240913')
```

## 实际返回示例（官方文档）

```text
trade_date ts_code  name  pct_change  ...  buy_md_amount  buy_md_amount_rate  buy_sm_amount  buy_sm_amount_rate
0   20240913  002149.SZ  西部材料       -1.34  ...         -12.65               -0.35         -62.43               -1.72
1   20240912  002149.SZ  西部材料        1.43  ...          13.71                0.33        -388.43               -9.25
2   20240911  002149.SZ  西部材料       -0.79  ...         -26.10               -1.68          95.69                6.15
3   20240910  002149.SZ  西部材料       -0.08  ...        -199.50               -7.26         -69.29               -2.52
4   20240909  002149.SZ  西部材料        1.12  ...          66.76                2.48        -198.12               -7.37
5   20240906  002149.SZ  西部材料       -2.49  ...        -104.57               -2.74         769.65               20.19
6   20240905  002149.SZ  西部材料       -0.70  ...        -307.62               -8.11         346.51                9.14
7   20240904  002149.SZ  西部材料       -0.92  ...         370.98                9.56         -23.25               -0.60
8   20240903  002149.SZ  西部材料        0.93  ...        -195.45               -3.87         643.41               12.75
9   20240902  002149.SZ  西部材料       -3.44  ...         195.50                2.32         988.69               11.71
```

## claw-quant 存储契约

该接口由专用采集器写入规范化业务表，主键和字段转换以链接代码为准。

> 权限状态来自实际 Token 探测；示例中的 Token 仅为环境变量占位符，不包含真实密钥。
