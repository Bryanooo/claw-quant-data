# `fut_basic` 标准化表契约

- 功能：获取期货合约列表数据
- PostgreSQL 表：`tushare_norm_fut_basic`
- 契约版本：`1`
- 技术主键：`_record_hash`（原始 payload SHA-256）
- 主日期字段：`无`
- 必填身份字段：`ts_code`
- 业务身份字段：`ts_code`
- 业务身份可信度：`contract_reviewed`
- 当前数据视图：`tushare_current_fut_basic`
- 原始数据表：`tushare_raw_record`（`api_name=fut_basic`）
- REST：`GET /api/v1/datasets/fut_basic/records`
- 接口 REST：`GET /api/v1/interfaces/fut_basic/records`
- 标准化实现：[service/tushare_normalization.py](../../../service/tushare_normalization.py)

## 业务字段

| 字段 | 上游类型 | PostgreSQL 类型 | 说明 |
|---|---|---|---|
| `ts_code` | `str` | `TEXT` | 合约代码 |
| `symbol` | `str` | `TEXT` | 交易标识 |
| `exchange` | `str` | `TEXT` | 交易市场 |
| `name` | `str` | `TEXT` | 中文简称 |
| `fut_code` | `str` | `TEXT` | 合约产品代码 |
| `multiplier` | `float` | `NUMERIC` | 合约乘数(只适用于国债期货、指数期货) |
| `trade_unit` | `str` | `TEXT` | 交易计量单位 |
| `per_unit` | `float` | `NUMERIC` | 交易单位(每手) |
| `quote_unit` | `str` | `TEXT` | 报价单位 |
| `quote_unit_desc` | `str` | `TEXT` | 最小报价单位说明 |
| `d_mode_desc` | `str` | `TEXT` | 交割方式说明 |
| `list_date` | `str` | `DATE` | 上市日期 |
| `delist_date` | `str` | `DATE` | 最后交易日期 |
| `d_month` | `str` | `TEXT` | 交割月份 |
| `last_ddate` | `str` | `TEXT` | 最后交割日 |
| `trade_time_desc` | `str` | `TEXT` | 交易时间说明 |

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
