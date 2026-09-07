# `stk_nineturn` — 神奇九转指标

- 分类：股票数据/特色数据
- 功能：神奇九转（又称“九转序列”）是一种基于技术分析的股票趋势反转指标，其思想来源于技术分析大师汤姆·迪马克（Tom DeMark）的TD序列。该指标的核心功能是通过识别股价在上涨或下跌过程中连续9天的特定走势，来判断股价的潜在反转点，从而帮助投资者提高抄底和逃顶的成功率，日线级别配合60min的九转效果更好，数据从20230101开始。
- Token 权限：**有权限**（接口返回成功）
- 官方权限要求：达到6000积分可以调用
- 官方文档：[doc 364](https://tushare.pro/document/2?doc_id=364)
- HTTP：`POST http://api.tushare.pro`
- claw-quant：已实现；代码：[collectors/stock/extra/stk_nineturn.py:StkNineturnCollector](../../../collectors/stock/extra/stk_nineturn.py)

## 输入契约

| 参数 | 类型 | 必选 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | N | 股票代码 |
| `trade_date` | str | N | 交易日期 （格式：YYYY-MM-DD HH:MM:SS) |
| `freq` | str | N | 频率(日daily) |
| `start_date` | str | N | 开始时间 |
| `end_date` | str | N | 结束时间 |

## 输出契约

| 字段 | 类型 | 默认显示 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | Y | 股票代码 |
| `trade_date` | datetime | Y | 交易日期 |
| `freq` | str | Y | 频率(日daily) |
| `open` | float | Y | 开盘价 |
| `high` | float | Y | 最高价 |
| `low` | float | Y | 最低价 |
| `close` | float | Y | 收盘价 |
| `vol` | float | Y | 成交量 |
| `amount` | float | Y | 成交额 |
| `up_count` | float | Y | 上九转计数 |
| `down_count` | float | Y | 下九转计数 |
| `nine_up_turn` | str | Y | 是否上九转)+9表示上九转 |
| `nine_down_turn` | str | Y | 是否下九转-9表示下九转 |

## HTTP 请求示例

```bash
curl -X POST 'http://api.tushare.pro' \
  -H 'Content-Type: application/json' \
  -d '{
  "api_name": "stk_nineturn",
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

df=pro.stk_nineturn(ts_code='000001.SZ',freq='daily',fields='ts_code,trade_date,freq,up_count,down_count,nine_up_turn,nine_down_turn')
```

## 实际返回示例（官方文档）

```text
ts_code           trade_date     freq  up_count  down_count nine_up_turn nine_down_turn
0    000001.SZ  2025-01-17 00:00:00  daily       3.0         0.0         None           None
1    000001.SZ  2025-01-16 00:00:00  daily       2.0         0.0         None           None
2    000001.SZ  2025-01-15 00:00:00  daily       1.0         0.0         None           None
3    000001.SZ  2025-01-14 00:00:00  daily       0.0         3.0         None           None
4    000001.SZ  2025-01-13 00:00:00  daily       0.0         2.0         None           None
..         ...                  ...    ...       ...         ...          ...            ...
491  000001.SZ  2023-01-09 00:00:00  daily       1.0         0.0         None           None
492  000001.SZ  2023-01-06 00:00:00  daily       0.0         0.0         None           None
493  000001.SZ  2023-01-05 00:00:00  daily       0.0         0.0         None           None
494  000001.SZ  2023-01-04 00:00:00  daily       0.0         0.0         None           None
495  000001.SZ  2023-01-03 00:00:00  daily       0.0         0.0         None           None
```

## claw-quant 存储契约

该接口由专用采集器写入规范化业务表，主键和字段转换以链接代码为准。

> 权限状态来自实际 Token 探测；示例中的 Token 仅为环境变量占位符，不包含真实密钥。
