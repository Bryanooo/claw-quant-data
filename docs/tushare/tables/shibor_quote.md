# `shibor_quote` 标准化表契约

- 功能：Shibor报价数据
- PostgreSQL 表：`tushare_norm_shibor_quote`
- 契约版本：`1`
- 技术主键：`_record_hash`（原始 payload SHA-256）
- 主日期字段：`date`
- 必填身份字段：`date`
- 业务身份字段：`date, bank`
- 业务身份可信度：`contract_reviewed`
- 当前数据视图：`tushare_current_shibor_quote`
- 原始数据表：`tushare_raw_record`（`api_name=shibor_quote`）
- REST：`GET /api/v1/datasets/shibor_quote/records`
- 接口 REST：`GET /api/v1/interfaces/shibor_quote/records`
- 标准化实现：[service/tushare_normalization.py](../../../service/tushare_normalization.py)

## 业务字段

| 字段 | 上游类型 | PostgreSQL 类型 | 说明 |
|---|---|---|---|
| `date` | `str` | `DATE` | 日期 |
| `bank` | `str` | `TEXT` | 报价银行 |
| `on_b` | `float` | `NUMERIC` | 隔夜_Bid |
| `on_a` | `float` | `NUMERIC` | 隔夜_Ask |
| `1w_b` | `float` | `NUMERIC` | 1周_Bid |
| `1w_a` | `float` | `NUMERIC` | 1周_Ask |
| `2w_b` | `float` | `NUMERIC` | 2周_Bid |
| `2w_a` | `float` | `NUMERIC` | 2周_Ask |
| `1m_b` | `float` | `NUMERIC` | 1月_Bid |
| `1m_a` | `float` | `NUMERIC` | 1月_Ask |
| `3m_b` | `float` | `NUMERIC` | 3月_Bid |
| `3m_a` | `float` | `NUMERIC` | 3月_Ask |
| `6m_b` | `float` | `NUMERIC` | 6月_Bid |
| `6m_a` | `float` | `NUMERIC` | 6月_Ask |
| `9m_b` | `float` | `NUMERIC` | 9月_Bid |
| `9m_a` | `float` | `NUMERIC` | 9月_Ask |
| `1y_b` | `float` | `NUMERIC` | 1年_Bid |
| `1y_a` | `float` | `NUMERIC` | 1年_Ask |

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
