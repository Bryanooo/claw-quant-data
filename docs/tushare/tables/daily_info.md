# `daily_info` 标准化表契约

- 功能：获取交易所股票交易统计，包括各板块明细
- PostgreSQL 表：`tushare_norm_daily_info`
- 契约版本：`1`
- 技术主键：`_record_hash`（原始 payload SHA-256）
- 主日期字段：`trade_date`
- 必填身份字段：`trade_date, ts_code`
- 业务身份字段：`trade_date, ts_code`
- 业务身份可信度：`heuristic`
- 当前数据视图：未创建（业务身份仍为启发式，REST 保留全部 payload 版本）
- 原始数据表：`tushare_raw_record`（`api_name=daily_info`）
- REST：`GET /api/v1/datasets/daily_info/records`
- 接口 REST：`GET /api/v1/interfaces/daily_info/records`
- 标准化实现：[service/tushare_normalization.py](../../../service/tushare_normalization.py)

## 业务字段

| 字段 | 上游类型 | PostgreSQL 类型 | 说明 |
|---|---|---|---|
| `trade_date` | `str` | `DATE` | 交易日期 |
| `ts_code` | `str` | `TEXT` | 市场代码 |
| `ts_name` | `str` | `TEXT` | 市场名称 |
| `com_count` | `int` | `BIGINT` | 挂牌数 |
| `total_share` | `float` | `NUMERIC` | 总股本（亿股） |
| `float_share` | `float` | `NUMERIC` | 流通股本（亿股） |
| `total_mv` | `float` | `NUMERIC` | 总市值（亿元） |
| `float_mv` | `float` | `NUMERIC` | 流通市值（亿元） |
| `amount` | `float` | `NUMERIC` | 交易金额（亿元） |
| `vol` | `float` | `NUMERIC` | 成交量（亿股） |
| `trans_count` | `int` | `BIGINT` | 成交笔数（万笔） |
| `pe` | `float` | `NUMERIC` | 平均市盈率 |
| `tr` | `float` | `NUMERIC` | 换手率（％），注：深交所暂无此列 |
| `exchange` | `str` | `TEXT` | 交易所（SH上交所 SZ深交所） |

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
