# `limit_list_ths` 标准化表契约

- 功能：获取同花顺每日涨跌停榜单数据，历史数据从20231101开始提供，增量每天16点左右更新，：分类（limit_type 涨停池、连扳池、冲刺涨停、炸板池、跌停池，默认：涨停池）不同，字段返回有值情况也不同，如仅有涨停池、连扳池 有最大封单 lu_limit_order返回值，其他分类为空
- PostgreSQL 表：`tushare_norm_limit_list_ths`
- 契约版本：`1`
- 技术主键：`_record_hash`（原始 payload SHA-256）
- 主日期字段：`trade_date`
- 必填身份字段：`trade_date, ts_code`
- 业务身份字段：`trade_date, ts_code`
- 业务身份可信度：`contract_reviewed`
- 当前数据视图：`tushare_current_limit_list_ths`
- 原始数据表：`tushare_raw_record`（`api_name=limit_list_ths`）
- REST：`GET /api/v1/datasets/limit_list_ths/records`
- 接口 REST：`GET /api/v1/interfaces/limit_list_ths/records`
- 标准化实现：[service/tushare_normalization.py](../../../service/tushare_normalization.py)

## 业务字段

| 字段 | 上游类型 | PostgreSQL 类型 | 说明 |
|---|---|---|---|
| `trade_date` | `str` | `DATE` | 交易日期 |
| `ts_code` | `str` | `TEXT` | 股票代码 |
| `name` | `str` | `TEXT` | 股票名称 |
| `price` | `float` | `NUMERIC` | 收盘价(元) |
| `pct_chg` | `float` | `NUMERIC` | 涨跌幅% |
| `open_num` | `int` | `BIGINT` | 打开次数 |
| `lu_desc` | `str` | `TEXT` | 涨停原因 |
| `limit_type` | `str` | `TEXT` | 板单类别 |
| `tag` | `str` | `TEXT` | 涨停标签 |
| `status` | `str` | `TEXT` | 涨停状态（N连板、一字板） |
| `first_lu_time` | `str` | `TEXT` | 首次涨停时间 |
| `last_lu_time` | `str` | `TEXT` | 最后涨停时间 |
| `first_ld_time` | `str` | `TEXT` | 首次跌停时间 |
| `last_ld_time` | `str` | `TEXT` | 最后跌停时间 |
| `limit_order` | `float` | `NUMERIC` | 封单量(元 |
| `limit_amount` | `float` | `NUMERIC` | 封单额(元 |
| `turnover_rate` | `float` | `NUMERIC` | 换手率% |
| `free_float` | `float` | `NUMERIC` | 实际流通(元 |
| `lu_limit_order` | `float` | `NUMERIC` | 最大封单(元 |
| `limit_up_suc_rate` | `float` | `NUMERIC` | 近一年涨停封板率 |
| `turnover` | `float` | `NUMERIC` | 成交额 |
| `rise_rate` | `float` | `NUMERIC` | 涨速 |
| `sum_float` | `float` | `NUMERIC` | 总市值（亿元） |
| `market_type` | `str` | `TEXT` | 股票类型：HS沪深主板、GEM创业板、STAR科创板 |

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
