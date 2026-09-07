# `hk_adjfactor` — 港股复权因子

- 分类：港股数据
- 功能：获取港股每日复权因子数据，每天滚动刷新
- Token 权限：**无权限**（Tushare 明确返回无访问权限）
- 官方权限要求：本接口是在开通港股日线权限后自动获取权限，权限请参考 权限说明文档
- 官方文档：[doc 401](https://tushare.pro/document/2?doc_id=401)
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
| `cum_adjfactor` | float | Y | 累计复权因子 |
| `close_price` | float | Y | 收盘价 |

## HTTP 请求示例

```bash
curl -X POST 'http://api.tushare.pro' \
  -H 'Content-Type: application/json' \
  -d '{
  "api_name": "hk_adjfactor",
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

#获取港股单一股票复权因子
df = pro.hk_adjfactor(ts_code='00001.HK', start_date='20240101', end_date='20251022')

#获取港股某一日全部股票的复权因子
df = pro.hk_adjfactor(trade_date='20251031')
```

## 实际返回示例（官方文档）

```text
ts_code trade_date cum_adjfactor close_price
0     00380.HK   20251031      1.000000    0.150000
1     00698.HK   20251031      1.000000    4.610000
2     00865.HK   20251031      1.000000    0.038000
3     08111.HK   20251031      1.000000    0.068000
4     00039.HK   20251031      1.000000    0.088000
...        ...        ...           ...         ...
4086  01384.HK   20251031      1.000000  113.700000
4087  02954.HK   20251031      1.000000    0.265000
4088  03460.HK   20251031      1.000000    7.440000
4089  83460.HK   20251031      1.000000    6.840000
4090  09460.HK   20251031      1.000000    0.960000
```

## claw-quant 存储契约

当前 Token 不可采集或接口不可直接调用，因此没有启用运行时采集。

> 权限状态来自实际 Token 探测；示例中的 Token 仅为环境变量占位符，不包含真实密钥。
