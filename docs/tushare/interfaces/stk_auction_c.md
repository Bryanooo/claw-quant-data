# `stk_auction_c` — 股票收盘集合竞价数据

- 分类：股票数据/特色数据
- 功能：股票收盘15:00集合竞价数据，每天盘后更新
- Token 权限：**有权限**（接口返回成功）
- 官方权限要求：本接口是单独开权限的数据，具体参考 权限说明
- 官方文档：[doc 354](https://tushare.pro/document/2?doc_id=354)
- HTTP：`POST http://api.tushare.pro`
- claw-quant：已实现；代码：[collectors/stock/extra/stk_auction_c.py:StkAuctionCCollector](../../../collectors/stock/extra/stk_auction_c.py)

## 输入契约

| 参数 | 类型 | 必选 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | N | 股票代码 |
| `trade_date` | str | N | 交易日期(YYYYMMDD) |
| `start_date` | str | N | 开始日期(YYYYMMDD) |
| `end_date` | str | N | 结束日期(YYYYMMDD) |

## 输出契约

| 字段 | 类型 | 默认显示 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | Y | 股票代码 |
| `trade_date` | str | Y | 交易日期 |
| `close` | float | Y | 收盘集合竞价收盘价 |
| `open` | float | Y | 收盘集合竞价开盘价 |
| `high` | float | Y | 收盘集合竞价最高价 |
| `low` | float | Y | 收盘集合竞价最低价 |
| `vol` | float | Y | 收盘集合竞价成交量 |
| `amount` | float | Y | 收盘集合竞价成交额 |
| `vwap` | float | Y | 收盘集合竞价均价 |

## HTTP 请求示例

```bash
curl -X POST 'http://api.tushare.pro' \
  -H 'Content-Type: application/json' \
  -d '{
  "api_name": "stk_auction_c",
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

df=pro.stk_auction_c(trade_date='20241122')
```

## 实际返回示例（官方文档）

```text
ts_code     trade_date close  ...   vol        amount      vwap
0     603102.SH   20241122  36.16  ...    557900.0   20347168.0  36.471
1     600696.SH   20241122  13.91  ...   3600489.0   50550184.0  14.040
2     600769.SH   20241122  12.75  ...   7940892.0  102510940.0  12.909
3     601900.SH   20241122  14.91  ...   6348300.0   95537632.0  15.049
4     600502.SH   20241122   4.88  ...   9718900.0   47690748.0   4.907
...         ...        ...    ...  ...         ...          ...     ...
5719  300504.SZ   20241122  16.34  ...   2037000.0   33653784.0  16.521
5720  300535.SZ   20241122  14.45  ...    638735.0    9340342.0  14.623
5721  300588.SZ   20241122  15.39  ...   3232050.0   50313180.0  15.567
5722  300592.SZ   20241122  14.43  ...   9910880.0  143872140.0  14.517
5723  300657.SZ   20241122  21.13  ...  10916225.0  235013090.0  21.529
```

## claw-quant 存储契约

该接口由专用采集器写入规范化业务表，主键和字段转换以链接代码为准。

> 权限状态来自实际 Token 探测；示例中的 Token 仅为环境变量占位符，不包含真实密钥。
