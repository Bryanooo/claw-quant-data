# `stk_auction_o` — 股票开盘集合竞价数据

- 分类：股票数据/特色数据
- 功能：股票开盘9:30集合竞价数据，每天盘后更新
- Token 权限：**有权限**（接口返回成功）
- 官方权限要求：本接口是单独开权限的数据，具体参考 权限说明
- 官方文档：[doc 353](https://tushare.pro/document/2?doc_id=353)
- HTTP：`POST http://api.tushare.pro`
- claw-quant：已实现；代码：[collectors/stock/extra/stk_auction_o.py:StkAuctionOCollector](../../../collectors/stock/extra/stk_auction_o.py)

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
| `close` | float | Y | 开盘集合竞价收盘价 |
| `open` | float | Y | 开盘集合竞价开盘价 |
| `high` | float | Y | 开盘集合竞价最高价 |
| `low` | float | Y | 开盘集合竞价最低价 |
| `vol` | float | Y | 开盘集合竞价成交量 |
| `amount` | float | Y | 开盘集合竞价成交额 |
| `vwap` | float | Y | 开盘集合竞价均价 |

## HTTP 请求示例

```bash
curl -X POST 'http://api.tushare.pro' \
  -H 'Content-Type: application/json' \
  -d '{
  "api_name": "stk_auction_o",
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

df=pro.stk_auction_o(trade_date='20241122')
```

## 实际返回示例（官方文档）

```text
ts_code    trade_date  close  open  ...   low    vol        amount     vwap
0     600502.SH   20241122   5.00   5.00  ...   5.00   45400.0    227000.0   5.000
1     600662.SH   20241122   5.28   5.28  ...   5.28   26800.0    141504.0   5.280
2     601118.SH   20241122   5.63   5.63  ...   5.63  152200.0    856886.0   5.630
3     600938.SH   20241122  26.54  26.54  ...  26.54  340400.0   9034216.0  26.540
4     601900.SH   20241122  15.09  15.09  ...  15.09  287600.0   4339884.0  15.090
...         ...        ...    ...    ...  ...    ...       ...         ...     ...
5719  300504.SZ   20241122  16.80  16.97  ...  16.80   19000.0    320954.0  16.892
5720  300535.SZ   20241122  15.26  15.29  ...  15.26   22800.0    348343.0  15.278
5721  300588.SZ   20241122  15.58  15.60  ...  15.45  117400.0   1830260.0  15.590
5722  300592.SZ   20241122  14.27  14.34  ...  14.23  502600.0   7194406.0  14.314
5723  300657.SZ   20241122  21.73  21.88  ...  21.71  545100.0  11902781.0  21.836
```

## claw-quant 存储契约

该接口由专用采集器写入规范化业务表，主键和字段转换以链接代码为准。

> 权限状态来自实际 Token 探测；示例中的 Token 仅为环境变量占位符，不包含真实密钥。
