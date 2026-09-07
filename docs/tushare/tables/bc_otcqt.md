# `bc_otcqt` 标准化表契约

- 功能：柜台流通式债券报价
- PostgreSQL 表：`tushare_norm_bc_otcqt`
- 契约版本：`1`
- 技术主键：`_record_hash`（原始 payload SHA-256）
- 主日期字段：`trade_date`
- 必填身份字段：`trade_date, ts_code`
- 业务身份字段：`trade_date, qt_time, bank, ts_code`
- 业务身份可信度：`contract_reviewed`
- 当前数据视图：`tushare_current_bc_otcqt`
- 原始数据表：`tushare_raw_record`（`api_name=bc_otcqt`）
- REST：`GET /api/v1/datasets/bc_otcqt/records`
- 接口 REST：`GET /api/v1/interfaces/bc_otcqt/records`
- 标准化实现：[service/tushare_normalization.py](../../../service/tushare_normalization.py)

## 业务字段

| 字段 | 上游类型 | PostgreSQL 类型 | 说明 |
|---|---|---|---|
| `trade_date` | `str` | `DATE` | 报价日期 |
| `qt_time` | `str` | `TIME WITHOUT TIME ZONE` | 报价时间 |
| `bank` | `str` | `TEXT` | 报价机构 |
| `ts_code` | `str` | `TEXT` | 债券编码 |
| `name` | `str` | `TEXT` | 债券简称 |
| `maturity` | `str` | `TEXT` | 期限 |
| `remain_maturity` | `str` | `TEXT` | 剩余期限 |
| `bond_type` | `str` | `TEXT` | 债券类型 |
| `coupon_rate` | `float` | `NUMERIC` | 票面利率（%） |
| `buy_price` | `float` | `NUMERIC` | 投资者买入全价 |
| `sell_price` | `float` | `NUMERIC` | 投资者卖出全价 |
| `buy_yield` | `float` | `NUMERIC` | 投资者买入到期收益率（%） |
| `sell_yield` | `float` | `NUMERIC` | 投资者卖出到期收益率（%） |

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
