# `wz_index` 标准化表契约

- 功能：温州民间借贷利率，即温州指数
- PostgreSQL 表：`tushare_norm_wz_index`
- 契约版本：`1`
- 技术主键：`_record_hash`（原始 payload SHA-256）
- 主日期字段：`date`
- 必填身份字段：`date`
- 业务身份字段：`date`
- 业务身份可信度：`heuristic`
- 当前数据视图：未创建（业务身份仍为启发式，REST 保留全部 payload 版本）
- 原始数据表：`tushare_raw_record`（`api_name=wz_index`）
- REST：`GET /api/v1/datasets/wz_index/records`
- 接口 REST：`GET /api/v1/interfaces/wz_index/records`
- 标准化实现：[service/tushare_normalization.py](../../../service/tushare_normalization.py)

## 业务字段

| 字段 | 上游类型 | PostgreSQL 类型 | 说明 |
|---|---|---|---|
| `date` | `str` | `DATE` | 日期 |
| `comp_rate` | `float` | `NUMERIC` | 温州民间融资综合利率指数 (%，下同) |
| `center_rate` | `float` | `NUMERIC` | 民间借贷服务中心利率 |
| `micro_rate` | `float` | `NUMERIC` | 小额贷款公司放款利率 |
| `cm_rate` | `float` | `NUMERIC` | 民间资本管理公司融资价格 |
| `sdb_rate` | `float` | `NUMERIC` | 社会直接借贷利率 |
| `om_rate` | `float` | `NUMERIC` | 其他市场主体利率 |
| `aa_rate` | `float` | `NUMERIC` | 农村互助会互助金费率 |
| `m1_rate` | `float` | `NUMERIC` | 温州地区民间借贷分期限利率（一月期） |
| `m3_rate` | `float` | `NUMERIC` | 温州地区民间借贷分期限利率（三月期） |
| `m6_rate` | `float` | `NUMERIC` | 温州地区民间借贷分期限利率（六月期） |
| `m12_rate` | `float` | `NUMERIC` | 温州地区民间借贷分期限利率（一年期） |
| `long_rate` | `float` | `NUMERIC` | 温州地区民间借贷分期限利率（长期） |

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
