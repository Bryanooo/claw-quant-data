# `etf_sz_cons` 标准化表契约

- 功能：获取深交所场内所有ETF每日盘前披露的一篮子组合信息,包括成分股票数量、申赎现金折溢价比例等数据
- PostgreSQL 表：`tushare_norm_etf_sz_cons`
- 契约版本：`1`
- 技术主键：`_record_hash`（原始 payload SHA-256）
- 主日期字段：`trade_date`
- 必填身份字段：`trade_date, ts_code`
- 业务身份字段：`trade_date, ts_code, con_code`
- 业务身份可信度：`contract_reviewed`
- 当前数据视图：`tushare_current_etf_sz_cons`
- 原始数据表：`tushare_raw_record`（`api_name=etf_sz_cons`）
- REST：`GET /api/v1/datasets/etf_sz_cons/records`
- 接口 REST：`GET /api/v1/interfaces/etf_sz_cons/records`
- 标准化实现：[service/tushare_normalization.py](../../../service/tushare_normalization.py)

## 业务字段

| 字段 | 上游类型 | PostgreSQL 类型 | 说明 |
|---|---|---|---|
| `trade_date` | `str` | `DATE` | 交易日期 |
| `ts_code` | `str` | `TEXT` | ETF代码 |
| `con_code` | `str` | `TEXT` | 成分代码 |
| `con_name` | `str` | `TEXT` | 成分名称 |
| `qty` | `int` | `BIGINT` | 股票数量(股) |
| `sub_flag` | `str` | `TEXT` | 现金替代标志 |
| `cpr` | `float` | `NUMERIC` | 申购现金替代保证金率（%） |
| `rdr` | `float` | `NUMERIC` | 赎回现金替代保证金率（%） |
| `sub_cc` | `float` | `NUMERIC` | 申购替代金额(单位：人民币元) |
| `red_cc` | `float` | `NUMERIC` | 赎回替代金额(单位：人民币元) |
| `exchange` | `str` | `TEXT` | 交易所代码HK港交所 SH上交所 SZ深交所 OTH其他 |

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
