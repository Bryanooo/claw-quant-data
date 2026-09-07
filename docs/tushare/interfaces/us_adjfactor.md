# `us_adjfactor` — 美股复权因子

- 分类：美股数据
- 功能：获取美股每日复权因子数据，在每天美股收盘后滚动刷新
- Token 权限：**无权限**（Tushare 明确返回无访问权限）
- 官方权限要求：本接口是在开通美股日线权限后自动获取权限，权限请参考 权限说明文档
- 官方文档：[doc 402](https://tushare.pro/document/2?doc_id=402)
- HTTP：`POST http://api.tushare.pro`
- claw-quant：未实现；代码：无

## 输入契约

| 参数 | 类型 | 必选 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | N | 股票代码 |
| `trade_date` | str | N | 交易日期（格式：YYYYMMDD，下同） |
| `start_date` | str | N | 开始日期 |
| `end_date` | str | N | 结束日期 |

## 输出契约

| 字段 | 类型 | 默认显示 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | Y | 股票代码 |
| `trade_date` | str | Y | 交易日期 |
| `exchange` | str | Y | 交易所 |
| `cum_adjfactor` | float | Y | 累计复权因子 |
| `close_price` | float | Y | 收盘价 |

## HTTP 请求示例

```bash
curl -X POST 'http://api.tushare.pro' \
  -H 'Content-Type: application/json' \
  -d '{
  "api_name": "us_adjfactor",
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

#获取美股单一股票复权因子
df = pro.us_adjfactor(ts_code='AAPL', start_date='20240101', end_date='20251022')

#获取美股某一日全部股票的复权因子
df = pro.us_adjfactor(trade_date='20251031')
```

## 实际返回示例（官方文档）

```text
ts_code trade_date exchange cum_adjfactor close_price
0       TAGOF   20251031      OTC      1.000000        None
1        BABA   20251031      NYS      1.000000  170.430000
2         CZR   20251031      NAS      1.000000   20.100000
3        DEEP   20251031      ARC      1.000000   35.025100
4        AVAL   20251031      NYS      1.000000    4.220000
...       ...        ...      ...           ...         ...
14995   MRETF   20251031      OTC      1.000000    7.150000
14996     CHI   20251031      NAS      1.000000   11.390000
14997    TBHC   20251031      NAS      1.000000    1.510000
14998   MQMIF   20251031      OTC      1.000000    0.127600
14999     TAC   20251031      NYS      1.000000   17.670000
```

## claw-quant 存储契约

当前 Token 不可采集或接口不可直接调用，因此没有启用运行时采集。

> 权限状态来自实际 Token 探测；示例中的 Token 仅为环境变量占位符，不包含真实密钥。
