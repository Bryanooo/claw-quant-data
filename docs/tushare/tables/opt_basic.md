# `opt_basic` 标准化表契约

- 功能：获取期权合约信息
- PostgreSQL 表：`tushare_norm_opt_basic`
- 契约版本：`1`
- 技术主键：`_record_hash`（原始 payload SHA-256）
- 主日期字段：`无`
- 必填身份字段：`ts_code`
- 业务身份字段：`ts_code`
- 业务身份可信度：`heuristic`
- 当前数据视图：未创建（业务身份仍为启发式，REST 保留全部 payload 版本）
- 原始数据表：`tushare_raw_record`（`api_name=opt_basic`）
- REST：`GET /api/v1/datasets/opt_basic/records`
- 接口 REST：`GET /api/v1/interfaces/opt_basic/records`
- 标准化实现：[service/tushare_normalization.py](../../../service/tushare_normalization.py)

## 业务字段

| 字段 | 上游类型 | PostgreSQL 类型 | 说明 |
|---|---|---|---|
| `ts_code` | `str` | `TEXT` | TS代码 |
| `symbol` | `str` | `TEXT` | 交易代码 |
| `exchange` | `str` | `TEXT` | 交易市场 |
| `name` | `str` | `TEXT` | 合约名称 |
| `per_unit` | `str` | `TEXT` | 合约单位 |
| `opt_code` | `str` | `TEXT` | 标的合约代码 |
| `opt_type` | `str` | `TEXT` | 合约类型 |
| `call_put` | `str` | `TEXT` | 期权类型 |
| `exercise_type` | `str` | `TEXT` | 行权方式 |
| `exercise_price` | `float` | `NUMERIC` | 行权价格，经过除权除息调整 |
| `opt_multiplier` | `float` | `NUMERIC` | 合约单位，经过除权除息调整 |
| `s_month` | `str` | `TEXT` | 结算月 |
| `maturity_date` | `str` | `DATE` | 到期日 |
| `list_price` | `float` | `NUMERIC` | 挂牌基准价 |
| `list_date` | `str` | `DATE` | 开始交易日期 |
| `delist_date` | `str` | `DATE` | 最后交易日期 |
| `last_edate` | `str` | `TEXT` | 最后行权日期 |
| `last_ddate` | `str` | `TEXT` | 最后交割日期 |
| `quote_unit` | `str` | `TEXT` | 报价单位 |
| `min_price_chg` | `str` | `TEXT` | 最小价格波幅 |

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
