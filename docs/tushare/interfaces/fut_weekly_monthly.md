# `fut_weekly_monthly` — 期货周/月线行情(每日更新)

- 分类：期货数据
- 功能：期货周/月线行情(每日更新)
- Token 权限：**有权限**（接口返回成功）
- 官方权限要求：官方页面未单独声明
- 官方文档：[doc 337](https://tushare.pro/document/2?doc_id=337)
- HTTP：`POST http://api.tushare.pro`
- claw-quant：已实现（契约通用采集器：原始层+强类型标准表）；代码：[collectors/tushare_raw.py:CatalogRawCollector](../../../collectors/tushare_raw.py)

## 输入契约

| 参数 | 类型 | 必选 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | N | TS代码 |
| `trade_date` | str | N | 交易日期 |
| `start_date` | str | N | 开始交易日期 |
| `end_date` | str | N | 结束交易日期 |
| `freq` | str | Y | 频率week周，month月 |
| `exchange` | str | N | 交易所 |

## 输出契约

| 字段 | 类型 | 默认显示 | 说明 |
|---|---|:---:|---|
| `ts_code` | str | Y | 期货代码 |
| `trade_date` | str | Y | 交易日期（每周五或者月末日期） |
| `end_date` | str | Y | 计算截至日期 |
| `freq` | str | Y | 频率(周week,月month) |
| `open` | float | Y | (周/月)开盘价 |
| `high` | float | Y | (周/月)最高价 |
| `low` | float | Y | (周/月)最低价 |
| `close` | float | Y | (周/月)收盘价 |
| `pre_close` | float | Y | 前一(周/月)收盘价 |
| `settle` | float | Y | (周/月)结算价 |
| `pre_settle` | float | Y | 前一(周/月)结算价 |
| `vol` | float | Y | (周/月)成交量(手) |
| `amount` | float | Y | (周/月)成交金额(万元) |
| `oi` | float | Y | (周/月)持仓量(手) |
| `oi_chg` | float | Y | (周/月)持仓量变化 |
| `exchange` | str | Y | 交易所 |
| `change1` | float | Y | (周/月)涨跌1 收盘价-昨结算价 |
| `change2` | float | Y | (周/月)涨跌2 结算价-昨结算价 |

## HTTP 请求示例

```bash
curl -X POST 'http://api.tushare.pro' \
  -H 'Content-Type: application/json' \
  -d '{
  "api_name": "fut_weekly_monthly",
  "token": "${TUSHARE_TOKEN}",
  "params": {
    "freq": "D"
  },
  "fields": ""
}'
```

## claw-quant 存储契约

该接口采用两阶段持久化：上游响应先无损写入 `tushare_raw_record`，随后按契约转换到
强类型标准表 `tushare_norm_fut_weekly_monthly`。标准表字段、类型、日期列、系统血缘字段和
稳定性规则见[标准化表契约](../tables/fut_weekly_monthly.md)。转换失败记录进入
`sys_tushare_normalization_error`，契约外字段保存在 `_extra_payload` 并登记到
`sys_tushare_schema_drift`；原始响应始终可用于修复后重放。

> 权限状态来自实际 Token 探测；示例中的 Token 仅为环境变量占位符，不包含真实密钥。
