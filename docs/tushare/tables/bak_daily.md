# `bak_daily` 标准化表契约

- 功能：获取备用行情，包括特定的行情指标(数据从2017年中左右开始，早期有几天数据缺失，近期正常)
- PostgreSQL 表：`tushare_norm_bak_daily`
- 契约版本：`1`
- 技术主键：`_record_hash`（原始 payload SHA-256）
- 主日期字段：`trade_date`
- 必填身份字段：`trade_date, ts_code`
- 业务身份字段：`trade_date, ts_code`
- 业务身份可信度：`heuristic`
- 当前数据视图：未创建（业务身份仍为启发式，REST 保留全部 payload 版本）
- 原始数据表：`tushare_raw_record`（`api_name=bak_daily`）
- REST：`GET /api/v1/datasets/bak_daily/records`
- 接口 REST：`GET /api/v1/interfaces/bak_daily/records`
- 标准化实现：[service/tushare_normalization.py](../../../service/tushare_normalization.py)

## 业务字段

| 字段 | 上游类型 | PostgreSQL 类型 | 说明 |
|---|---|---|---|
| `ts_code` | `str` | `TEXT` | 股票代码 |
| `trade_date` | `str` | `DATE` | 交易日期 |
| `name` | `str` | `TEXT` | 股票名称 |
| `pct_change` | `float` | `NUMERIC` | 涨跌幅 |
| `close` | `float` | `NUMERIC` | 收盘价 |
| `change` | `float` | `NUMERIC` | 涨跌额 |
| `open` | `float` | `NUMERIC` | 开盘价 |
| `high` | `float` | `NUMERIC` | 最高价 |
| `low` | `float` | `NUMERIC` | 最低价 |
| `pre_close` | `float` | `NUMERIC` | 昨收价 |
| `vol_ratio` | `float` | `NUMERIC` | 量比 |
| `turn_over` | `float` | `NUMERIC` | 换手率 |
| `swing` | `float` | `NUMERIC` | 振幅 |
| `vol` | `float` | `NUMERIC` | 成交量 |
| `amount` | `float` | `NUMERIC` | 成交额 |
| `selling` | `float` | `NUMERIC` | 内盘（主动卖，手） |
| `buying` | `float` | `NUMERIC` | 外盘（主动买， 手） |
| `total_share` | `float` | `NUMERIC` | 总股本(亿) |
| `float_share` | `float` | `NUMERIC` | 流通股本(亿) |
| `pe` | `float` | `NUMERIC` | 市盈(动) |
| `industry` | `str` | `TEXT` | 所属行业 |
| `area` | `str` | `TEXT` | 所属地域 |
| `float_mv` | `float` | `NUMERIC` | 流通市值 |
| `total_mv` | `float` | `NUMERIC` | 总市值 |
| `avg_price` | `float` | `NUMERIC` | 平均价 |
| `strength` | `float` | `NUMERIC` | 强弱度(%) |
| `activity` | `float` | `NUMERIC` | 活跃度(%) |
| `avg_turnover` | `float` | `NUMERIC` | 笔换手 |
| `attack` | `float` | `NUMERIC` | 攻击波(%) |
| `interval_3` | `float` | `NUMERIC` | 近3月涨幅 |
| `interval_6` | `float` | `NUMERIC` | 近6月涨幅 |

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
