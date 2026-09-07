# `stk_weekly_monthly` — 股票周/月线行情(每日更新)

- 分类：股票数据/行情数据
- 功能：股票周/月线行情(每日更新)
- Token 权限：**有权限**（接口返回成功）
- 官方权限要求：用户需要至少2000积分才可以调取，具体请参阅 积分获取办法
- 官方文档：[doc 336](https://tushare.pro/document/2?doc_id=336)
- HTTP：`POST http://api.tushare.pro`
- claw-quant：已实现；代码：[collectors/stock/market/stk_weekly_monthly.py](../../../collectors/stock/market/stk_weekly_monthly.py)、[collectors/stock/market/stk_weekly_monthly.py:StkWeeklyMonthlyCollector](../../../collectors/stock/market/stk_weekly_monthly.py)

## 输入契约

| 参数 | 类型 | 必选 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | N | TS代码 |
| `trade_date` | str | N | 交易日期(格式：YYYYMMDD，每周或每月最后一天的日期） |
| `start_date` | str | N | 开始交易日期 |
| `end_date` | str | N | 结束交易日期 |
| `freq` | str | Y | 频率week周，month月 |

## 输出契约

| 字段 | 类型 | 默认显示 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | Y | 股票代码 |
| `trade_date` | str | Y | 交易日期 |
| `end_date` | str | Y | 计算截至日期 |
| `freq` | str | Y | 频率(周week,月month) |
| `open` | float | Y | (周/月)开盘价 |
| `high` | float | Y | (周/月)最高价 |
| `low` | float | Y | (周/月)最低价 |
| `close` | float | Y | (周/月)收盘价 |
| `pre_close` | float | Y | 上一(周/月)收盘价 |
| `vol` | float | Y | (周/月)成交量 |
| `amount` | float | Y | (周/月)成交额 |
| `change` | float | Y | (周/月)涨跌额 |
| `pct_chg` | float | Y | (周/月)涨跌幅(未复权,如果是复权请用 通用行情接口) |

## HTTP 请求示例

```bash
curl -X POST 'http://api.tushare.pro' \
  -H 'Content-Type: application/json' \
  -d '{
  "api_name": "stk_weekly_monthly",
  "token": "${TUSHARE_TOKEN}",
  "params": {
    "freq": "D"
  },
  "fields": ""
}'
```

## 官方 SDK 示例

```python
pro = ts.pro_api()

#获取20251024这周周线数据
df=pro.stk_weekly_monthly(trade_date='20251024',freq='week')

#获取202510月月线数据
df=pro.stk_weekly_monthly(trade_date='20251031',freq='month')
```

## 实际返回示例（官方文档）

```text
ts_code trade_date  end_date  ...      amount  change  pct_chg
    0     600137.SH   20251024  20251023  ...   429206.49    2.18    11.93
    1     600236.SH   20251024  20251023  ...   510772.77    0.25     3.49
    2     301262.SZ   20251024  20251023  ...  1140060.52    5.69    24.69
    3     600114.SH   20251024  20251023  ...  1786514.91   -0.41    -1.39
    4     301509.SZ   20251024  20251023  ...   225023.73    0.47     1.34
    ...         ...        ...       ...  ...         ...     ...      ...
    5428  920061.BJ   20251024  20251023  ...   153251.70   -0.51    -1.47
    5429  920100.BJ   20251024  20251023  ...   674924.90    5.01     7.45
    5430  603196.SH   20251024  20251023  ...   316237.47    0.85     3.69
    5431  603599.SH   20251024  20251023  ...   370038.63   -0.13    -1.10
    5432  301195.SZ   20251024  20251023  ...   186490.18    1.86     5.66
```

## claw-quant 存储契约

该接口由专用采集器写入规范化业务表，主键和字段转换以链接代码为准。

> 权限状态来自实际 Token 探测；示例中的 Token 仅为环境变量占位符，不包含真实密钥。
