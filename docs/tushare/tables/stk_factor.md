# `stk_factor` 标准化表契约

- 功能：获取股票每日技术面因子数据，用于跟踪股票当前走势情况，数据由Tushare社区自产，覆盖全历史
- PostgreSQL 表：`tushare_norm_stk_factor`
- 契约版本：`1`
- 技术主键：`_record_hash`（原始 payload SHA-256）
- 主日期字段：`trade_date`
- 必填身份字段：`trade_date, ts_code`
- 业务身份字段：`trade_date, ts_code`
- 业务身份可信度：`heuristic`
- 当前数据视图：未创建（业务身份仍为启发式，REST 保留全部 payload 版本）
- 原始数据表：`tushare_raw_record`（`api_name=stk_factor`）
- REST：`GET /api/v1/datasets/stk_factor/records`
- 接口 REST：`GET /api/v1/interfaces/stk_factor/records`
- 标准化实现：[service/tushare_normalization.py](../../../service/tushare_normalization.py)

## 业务字段

| 字段 | 上游类型 | PostgreSQL 类型 | 说明 |
|---|---|---|---|
| `ts_code` | `str` | `TEXT` | 股票代码 |
| `trade_date` | `str` | `DATE` | 交易日期 |
| `close` | `float` | `NUMERIC` | 收盘价 |
| `open` | `float` | `NUMERIC` | 开盘价 |
| `high` | `float` | `NUMERIC` | 最高价 |
| `low` | `float` | `NUMERIC` | 最低价 |
| `pre_close` | `float` | `NUMERIC` | 昨收价 |
| `change` | `float` | `NUMERIC` | 涨跌额 |
| `pct_change` | `float` | `NUMERIC` | 涨跌幅 |
| `vol` | `float` | `NUMERIC` | 成交量 （手） |
| `amount` | `float` | `NUMERIC` | 成交额 （千元） |
| `adj_factor` | `float` | `NUMERIC` | 复权因子 |
| `open_hfq` | `float` | `NUMERIC` | 开盘价后复权 |
| `open_qfq` | `float` | `NUMERIC` | 开盘价前复权 |
| `close_hfq` | `float` | `NUMERIC` | 收盘价后复权 |
| `close_qfq` | `float` | `NUMERIC` | 收盘价前复权 |
| `high_hfq` | `float` | `NUMERIC` | 最高价后复权 |
| `high_qfq` | `float` | `NUMERIC` | 最高价前复权 |
| `low_hfq` | `float` | `NUMERIC` | 最低价后复权 |
| `low_qfq` | `float` | `NUMERIC` | 最低价前复权 |
| `pre_close_hfq` | `float` | `NUMERIC` | 昨收价后复权 |
| `pre_close_qfq` | `float` | `NUMERIC` | 昨收价前复权 |
| `macd_dif` | `float` | `NUMERIC` | MACD_DIF (基于前复权价格计算，下同) |
| `macd_dea` | `float` | `NUMERIC` | MACD_DEA |
| `macd` | `float` | `NUMERIC` | MACD |
| `kdj_k` | `float` | `NUMERIC` | KDJ_K |
| `kdj_d` | `float` | `NUMERIC` | KDJ_D |
| `kdj_j` | `float` | `NUMERIC` | KDJ_J |
| `rsi_6` | `float` | `NUMERIC` | RSI_6 |
| `rsi_12` | `float` | `NUMERIC` | RSI_12 |
| `rsi_24` | `float` | `NUMERIC` | RSI_24 |
| `boll_upper` | `float` | `NUMERIC` | BOLL_UPPER |
| `boll_mid` | `float` | `NUMERIC` | BOLL_MID |
| `boll_lower` | `float` | `NUMERIC` | BOLL_LOWER |
| `cci` | `float` | `NUMERIC` | CCI |

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
