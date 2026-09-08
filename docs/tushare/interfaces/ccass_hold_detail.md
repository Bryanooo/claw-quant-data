# `ccass_hold_detail` — 中央结算系统持股明细

- 分类：股票数据/特色数据
- 功能：获取中央结算系统机构席位持股明细；全市场单日数据量可超过百万行，必须使用受控范围
- Token 权限：**有权限**（2026-09-08 生产 Token 实测返回成功）
- 官方权限要求：8000积分可调取，每分钟300次
- 官方文档：[doc 274](https://tushare.pro/document/2?doc_id=274)
- HTTP：`POST http://api.tushare.pro`
- claw-quant：已实现；代码：[collectors/stock/extra/ccass_hold_detail.py:CcassHoldDetailCollector](../../../collectors/stock/extra/ccass_hold_detail.py)

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
| `col_participant_id` | str | Y | 参与者编号 |
| `col_participant_name` | str | Y | 机构名称 |
| `col_shareholding` | str | Y | 持股量 |
| `col_shareholding_percent` | str | Y | 持股占比 |

## HTTP 请求示例

```bash
curl -X POST 'http://api.tushare.pro' \
  -H 'Content-Type: application/json' \
  -d '{
  "api_name": "ccass_hold_detail",
  "token": "${TUSHARE_TOKEN}",
  "params": {
    "ts_code": "600519.SH",
    "trade_date": "20260907"
  },
  "fields": ""
}'
```

## 官方 SDK 示例

```python
df = pro.ccass_hold_detail(ts_code='600519.SH', trade_date='20260907')
```

## claw-quant 存储契约

该接口由专用采集器写入规范化业务表，主键和字段转换以链接代码为准。

> 权限状态来自实际 Token 探测；示例中的 Token 仅为环境变量占位符，不包含真实密钥。
