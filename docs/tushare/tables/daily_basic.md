# `daily_basic` 标准化表契约

- 功能：获取全部股票每日重要的基本面指标，可用于选股分析、报表展示等。单次请求最大返回6000条数据，可按日线循环提取全部历史。
- PostgreSQL 表：`tushare_norm_daily_basic`
- 契约版本：`1`
- 技术主键：`_record_hash`（原始 payload SHA-256）
- 主日期字段：`trade_date`
- 必填身份字段：`trade_date, ts_code`
- 业务身份字段：`trade_date, ts_code`
- 业务身份可信度：`contract_reviewed`
- 当前数据视图：`tushare_current_daily_basic`
- 原始数据表：`tushare_raw_record`（`api_name=daily_basic`）
- REST：`GET /api/v1/datasets/daily_basic/records`
- 接口 REST：`GET /api/v1/interfaces/daily_basic/records`
- 标准化实现：[service/tushare_normalization.py](../../../service/tushare_normalization.py)

## 业务字段

| 字段 | 上游类型 | PostgreSQL 类型 | 说明 |
|---|---|---|---|
| `ts_code` | `str` | `TEXT` | TS股票代码 |
| `trade_date` | `str` | `DATE` | 交易日期 |
| `close` | `float` | `NUMERIC` | 当日收盘价 |
| `turnover_rate` | `float` | `NUMERIC` | 换手率 (成交量/无限售流通股数) |
| `turnover_rate_f` | `float` | `NUMERIC` | 换手率（自由流通股）(成交量/自由流通股数) |
| `volume_ratio` | `float` | `NUMERIC` | 量比 VOL/MA |
| `pe` | `float` | `NUMERIC` | 市盈率（总市值/净利润， 亏损的PE为空） |
| `pe_ttm` | `float` | `NUMERIC` | 市盈率（ 总市值/净利润TTM，亏损的PE为空） |
| `pb` | `float` | `NUMERIC` | 市净率（总市值/(净资产-其他权益工具)） |
| `ps` | `float` | `NUMERIC` | 市销率 (总市值/营业收入(最新年报)) |
| `ps_ttm` | `float` | `NUMERIC` | 市销率（TTM）(总市值/营业收入TTM) |
| `dv_ratio` | `float` | `NUMERIC` | 股息率 （%），除息日发生在去年期间的派现 |
| `dv_ttm` | `float` | `NUMERIC` | 股息率（TTM）（%），除息日在近12个月且分红报告期在12个月以内的派现 |
| `total_share` | `float` | `NUMERIC` | 总股本 （万股） |
| `float_share` | `float` | `NUMERIC` | 流通股本 （万股） |
| `free_share` | `float` | `NUMERIC` | 自由流通股本 （万） |
| `total_mv` | `float` | `NUMERIC` | 总市值 （万元） |
| `circ_mv` | `float` | `NUMERIC` | 流通市值（万元） |
| `limit_status` | `int` | `BIGINT` | 收盘涨跌状态：0-平盘，1-上涨(不含涨停)，2-涨停(不含一字涨停)，3-一字涨停，4-下跌(不含跌停)，5-跌停(不含一字跌停)，6-一字跌停 |

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
