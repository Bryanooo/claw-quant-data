# `cb_basic` 标准化表契约

- 功能：获取可转债基本信息
- PostgreSQL 表：`tushare_norm_cb_basic`
- 契约版本：`1`
- 技术主键：`_record_hash`（原始 payload SHA-256）
- 主日期字段：`无`
- 必填身份字段：`ts_code`
- 业务身份字段：`ts_code`
- 业务身份可信度：`contract_reviewed`
- 当前数据视图：`tushare_current_cb_basic`
- 原始数据表：`tushare_raw_record`（`api_name=cb_basic`）
- REST：`GET /api/v1/datasets/cb_basic/records`
- 接口 REST：`GET /api/v1/interfaces/cb_basic/records`
- 标准化实现：[service/tushare_normalization.py](../../../service/tushare_normalization.py)

## 业务字段

| 字段 | 上游类型 | PostgreSQL 类型 | 说明 |
|---|---|---|---|
| `ts_code` | `str` | `TEXT` | 转债代码 |
| `bond_full_name` | `str` | `TEXT` | 转债名称 |
| `bond_short_name` | `str` | `TEXT` | 转债简称 |
| `cb_code` | `str` | `TEXT` | 转股申报代码 |
| `cb_type` | `str` | `TEXT` | 转债类型: CB-可转债,EB-可交换债 |
| `stk_code` | `str` | `TEXT` | 正股代码 |
| `stk_short_name` | `str` | `TEXT` | 正股简称 |
| `maturity` | `float` | `NUMERIC` | 发行期限（年） |
| `par` | `float` | `NUMERIC` | 面值 |
| `issue_price` | `float` | `NUMERIC` | 发行价格 |
| `issue_size` | `float` | `NUMERIC` | 发行总额（元） |
| `remain_size` | `float` | `NUMERIC` | 债券余额（元） |
| `value_date` | `str` | `DATE` | 起息日期 |
| `maturity_date` | `str` | `DATE` | 到期日期 |
| `rate_type` | `str` | `TEXT` | 利率类型 |
| `coupon_rate` | `float` | `NUMERIC` | 票面利率（%） |
| `add_rate` | `float` | `NUMERIC` | 补偿利率（%） |
| `pay_per_year` | `int` | `BIGINT` | 年付息次数 |
| `list_date` | `str` | `DATE` | 上市日期 |
| `delist_date` | `str` | `DATE` | 摘牌日 |
| `exchange` | `str` | `TEXT` | 上市交易所 |
| `conv_start_date` | `str` | `DATE` | 转股起始日 |
| `conv_end_date` | `str` | `DATE` | 转股截止日 |
| `conv_stop_date` | `str` | `DATE` | 停止转股日(提前到期) |
| `first_conv_price` | `float` | `NUMERIC` | 初始转股价 |
| `conv_price` | `float` | `NUMERIC` | 最新转股价 |
| `rate_clause` | `str` | `TEXT` | 利率说明 |
| `put_clause` | `str` | `TEXT` | 回售条款 |
| `maturity_call_price` | `float` | `NUMERIC` | 到期赎回价格(含税) |
| `maturity_put_price` | `float` | `NUMERIC` | 到期赎回价格(含税)[更名停用，请使用maturity_call_price] |
| `call_clause` | `str` | `TEXT` | 赎回条款 |
| `reset_clause` | `str` | `TEXT` | 特别向下修正条款 |
| `conv_clause` | `str` | `TEXT` | 转股条款 |
| `guarantor` | `str` | `TEXT` | 担保人 |
| `guarantee_type` | `str` | `TEXT` | 担保方式 |
| `issue_rating` | `str` | `TEXT` | 发行信用等级 |
| `newest_rating` | `str` | `TEXT` | 最新信用等级 |
| `rating_comp` | `str` | `TEXT` | 最新评级机构 |

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
