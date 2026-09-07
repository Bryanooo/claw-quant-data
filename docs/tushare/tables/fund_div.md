# `fund_div` 标准化表契约

- 功能：获取公募基金分红数据
- PostgreSQL 表：`tushare_norm_fund_div`
- 契约版本：`1`
- 技术主键：`_record_hash`（原始 payload SHA-256）
- 主日期字段：`ann_date`
- 必填身份字段：`ts_code`
- 业务身份字段：`ts_code`
- 业务身份可信度：`heuristic`
- 当前数据视图：未创建（业务身份仍为启发式，REST 保留全部 payload 版本）
- 原始数据表：`tushare_raw_record`（`api_name=fund_div`）
- REST：`GET /api/v1/datasets/fund_div/records`
- 接口 REST：`GET /api/v1/interfaces/fund_div/records`
- 标准化实现：[service/tushare_normalization.py](../../../service/tushare_normalization.py)

## 业务字段

| 字段 | 上游类型 | PostgreSQL 类型 | 说明 |
|---|---|---|---|
| `ts_code` | `str` | `TEXT` | TS代码 |
| `ann_date` | `str` | `DATE` | 公告日期 |
| `imp_anndate` | `str` | `DATE` | 分红实施公告日 |
| `base_date` | `str` | `DATE` | 分配收益基准日 |
| `div_proc` | `str` | `TEXT` | 方案进度 |
| `record_date` | `str` | `DATE` | 权益登记日 |
| `ex_date` | `str` | `DATE` | 除息日 |
| `pay_date` | `str` | `DATE` | 派息日 |
| `earpay_date` | `str` | `DATE` | 收益支付日 |
| `net_ex_date` | `str` | `DATE` | 净值除权日 |
| `div_cash` | `float` | `NUMERIC` | 每股派息(元) |
| `base_unit` | `float` | `NUMERIC` | 基准基金份额(万份) |
| `ear_distr` | `float` | `NUMERIC` | 可分配收益(元) |
| `ear_amount` | `float` | `NUMERIC` | 收益分配金额(元) |
| `account_date` | `str` | `DATE` | 红利再投资到账日 |
| `base_year` | `str` | `TEXT` | 份额基准年度 |

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
