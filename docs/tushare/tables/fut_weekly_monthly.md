# `fut_weekly_monthly` 标准化表契约

- 功能：期货周/月线行情(每日更新)
- PostgreSQL 表：`tushare_norm_fut_weekly_monthly`
- 契约版本：`1`
- 技术主键：`_record_hash`（原始 payload SHA-256）
- 主日期字段：`trade_date`
- 必填身份字段：`trade_date, ts_code`
- 业务身份字段：`trade_date, ts_code`
- 业务身份可信度：`heuristic`
- 当前数据视图：未创建（业务身份仍为启发式，REST 保留全部 payload 版本）
- 原始数据表：`tushare_raw_record`（`api_name=fut_weekly_monthly`）
- REST：`GET /api/v1/datasets/fut_weekly_monthly/records`
- 接口 REST：`GET /api/v1/interfaces/fut_weekly_monthly/records`
- 标准化实现：[service/tushare_normalization.py](../../../service/tushare_normalization.py)

## 业务字段

| 字段 | 上游类型 | PostgreSQL 类型 | 说明 |
|---|---|---|---|
| `ts_code` | `str` | `TEXT` | 期货代码 |
| `trade_date` | `str` | `DATE` | 交易日期（每周五或者月末日期） |
| `end_date` | `str` | `DATE` | 计算截至日期 |
| `freq` | `str` | `TEXT` | 频率(周week,月month) |
| `open` | `float` | `NUMERIC` | (周/月)开盘价 |
| `high` | `float` | `NUMERIC` | (周/月)最高价 |
| `low` | `float` | `NUMERIC` | (周/月)最低价 |
| `close` | `float` | `NUMERIC` | (周/月)收盘价 |
| `pre_close` | `float` | `NUMERIC` | 前一(周/月)收盘价 |
| `settle` | `float` | `NUMERIC` | (周/月)结算价 |
| `pre_settle` | `float` | `NUMERIC` | 前一(周/月)结算价 |
| `vol` | `float` | `NUMERIC` | (周/月)成交量(手) |
| `amount` | `float` | `NUMERIC` | (周/月)成交金额(万元) |
| `oi` | `float` | `NUMERIC` | (周/月)持仓量(手) |
| `oi_chg` | `float` | `NUMERIC` | (周/月)持仓量变化 |
| `exchange` | `str` | `TEXT` | 交易所 |
| `change1` | `float` | `NUMERIC` | (周/月)涨跌1 收盘价-昨结算价 |
| `change2` | `float` | `NUMERIC` | (周/月)涨跌2 结算价-昨结算价 |

## 系统字段

| 字段 | PostgreSQL 类型 | 说明 |
|---|---|---|
| `_record_hash` | `CHAR(64)` | 原始 payload 的 SHA-256 技术主键 |
| `_request_hash` | `CHAR(64)` | 去除分页参数后的请求 SHA-256 |
| `_source_doc_id` | `INTEGER` | Tushare 官方文档编号 |
| `_source_collected_at` | `TIMESTAMPTZ` | 原始数据采集时间 |
| `_first_seen_at` | `TIMESTAMPTZ` | 首次标准化时间 |
| `_last_seen_at` | `TIMESTAMPTZ` | 最近一次标准化时间 |
| `_schema_version` | `INTEGER` | 标准化契约版本 |
| `_extra_payload` | `JSONB` | 契约外字段，保留且触发 Schema Drift |

## 稳定性契约

- 原始记录先提交，标准化失败不会造成上游响应丢失。
- 同一 payload 使用 `_record_hash` 幂等 UPSERT，重复采集只更新最近观测时间。
- 契约外字段完整保存在 `_extra_payload` 并登记 Schema Drift。
- 类型转换失败的整行进入隔离表，修复契约后可以从原始层重放。
- 未经确认的业务键不会被猜测成唯一约束；当前主键是可验证的技术主键。
- `contract_reviewed` 接口的 REST 查询使用 `tushare_current_*` 视图；原始标准表仍保留全部版本。
