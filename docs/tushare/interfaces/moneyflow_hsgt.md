# `moneyflow_hsgt` — 沪深港通资金流向

- 分类：股票数据/资金流向数据
- 功能：获取沪股通、深股通、港股通每日资金流向数据
- Token 权限：**有权限**（2026-09-08 生产 Token 实测返回成功）
- 官方权限要求：2000积分起，5000积分每分钟500次
- 官方文档：[doc 47](https://tushare.pro/document/2?doc_id=47)
- HTTP：`POST http://api.tushare.pro`
- claw-quant：已实现；代码：[collectors/stock/moneyflow/moneyflow_hsgt.py:MoneyflowHsgtCollector](../../../collectors/stock/moneyflow/moneyflow_hsgt.py)

## 输入契约

| 参数 | 类型 | 必选 | 说明 |
|---|---|:---:|---|
| `trade_date` | str | N | 交易日期 |
| `start_date` | str | N | 开始日期 |
| `end_date` | str | N | 结束日期 |

## 输出契约

| 字段 | 类型 | 默认显示 | 说明 |
|---|---|:---:|---|
| `trade_date` | str | Y | 交易日期 |
| `ggt_ss` | float | Y | 港股通（上海） |
| `ggt_sz` | float | Y | 港股通（深圳） |
| `hgt` | float | Y | 沪股通 |
| `sgt` | float | Y | 深股通 |
| `north_money` | float | Y | 北向资金 |
| `south_money` | float | Y | 南向资金 |

## HTTP 请求示例

```bash
curl -X POST 'http://api.tushare.pro' \
  -H 'Content-Type: application/json' \
  -d '{
  "api_name": "moneyflow_hsgt",
  "token": "${TUSHARE_TOKEN}",
  "params": {
    "trade_date": "20260907"
  },
  "fields": ""
}'
```

## 官方 SDK 示例

```python
df = pro.moneyflow_hsgt(trade_date='20260907')
```

## claw-quant 存储契约

该接口由专用采集器写入规范化业务表，主键和字段转换以链接代码为准。

> 权限状态来自实际 Token 探测；示例中的 Token 仅为环境变量占位符，不包含真实密钥。
