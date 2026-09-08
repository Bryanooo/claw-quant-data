# `hk_hold` — 沪深港股通持股明细

- 分类：股票数据/特色数据
- 功能：获取沪深港股通持股明细；北向日度披露自2024-08-20停止，南向数据仍可返回
- Token 权限：**有权限**（2026-09-08 生产 Token 实测返回成功）
- 官方权限要求：2000积分可正常使用
- 官方文档：[doc 188](https://tushare.pro/document/2?doc_id=188)
- HTTP：`POST http://api.tushare.pro`
- claw-quant：已实现；代码：[collectors/stock/extra/hk_hold.py:HkHoldCollector](../../../collectors/stock/extra/hk_hold.py)

## 输入契约

| 参数 | 类型 | 必选 | 说明 |
|---|---|:---:|---|
| `code` | str | N | 交易所代码 |
| `ts_code` | str | N | TS股票代码 |
| `trade_date` | str | N | 交易日期 |
| `start_date` | str | N | 开始日期 |
| `end_date` | str | N | 结束日期 |
| `exchange` | str | N | SH/SZ/HK |

## 输出契约

| 字段 | 类型 | 默认显示 | 说明 |
|---|---|:---:|---|
| `code` | str | Y | 原始代码 |
| `trade_date` | str | Y | 交易日期 |
| `ts_code` | str | Y | TS代码 |
| `name` | str | Y | 股票名称 |
| `vol` | int | Y | 持股数量 |
| `ratio` | float | Y | 持股占比 |
| `exchange` | str | Y | SH/SZ/HK |

## HTTP 请求示例

```bash
curl -X POST 'http://api.tushare.pro' \
  -H 'Content-Type: application/json' \
  -d '{
  "api_name": "hk_hold",
  "token": "${TUSHARE_TOKEN}",
  "params": {
    "trade_date": "20260907"
  },
  "fields": ""
}'
```

## 官方 SDK 示例

```python
df = pro.hk_hold(trade_date='20260907')
```

## claw-quant 存储契约

该接口由专用采集器写入规范化业务表，主键和字段转换以链接代码为准。

> 权限状态来自实际 Token 探测；示例中的 Token 仅为环境变量占位符，不包含真实密钥。
