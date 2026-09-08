# `ccass_hold` — 中央结算系统持股汇总

- 分类：股票数据/特色数据
- 功能：获取中央结算系统持股汇总数据，覆盖全部历史数据，通常于下一交易日早上9点前更新
- Token 权限：**有权限**（2026-09-08 生产 Token 实测返回成功）
- 官方权限要求：5000积分每分钟300次，8000积分以上每分钟500次
- 官方文档：[doc 295](https://tushare.pro/document/2?doc_id=295)
- HTTP：`POST http://api.tushare.pro`
- claw-quant：已实现；代码：[collectors/stock/extra/ccass_hold.py:CcassHoldCollector](../../../collectors/stock/extra/ccass_hold.py)

## 输入契约

| 参数 | 类型 | 必选 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | N | 股票代码 |
| `hk_code` | str | N | 港交所代码 |
| `trade_date` | str | N | 交易日期 |
| `start_date` | str | N | 开始日期 |
| `end_date` | str | N | 结束日期 |

## 输出契约

| 字段 | 类型 | 默认显示 | 说明 |
|---|---|:---:|---|
| `trade_date` | str | Y | 交易日期 |
| `ts_code` | str | Y | 股票代码 |
| `name` | str | Y | 股票名称 |
| `shareholding` | str | Y | 中央结算系统持股量 |
| `hold_nums` | str | Y | 参与者数目 |
| `hold_ratio` | str | Y | 持股占比 |

## HTTP 请求示例

```bash
curl -X POST 'http://api.tushare.pro' \
  -H 'Content-Type: application/json' \
  -d '{
  "api_name": "ccass_hold",
  "token": "${TUSHARE_TOKEN}",
  "params": {
    "trade_date": "20260907"
  },
  "fields": ""
}'
```

## 官方 SDK 示例

```python
df = pro.ccass_hold(trade_date='20260907')
```

## claw-quant 存储契约

该接口由专用采集器写入规范化业务表，主键和字段转换以链接代码为准。

> 权限状态来自实际 Token 探测；示例中的 Token 仅为环境变量占位符，不包含真实密钥。
