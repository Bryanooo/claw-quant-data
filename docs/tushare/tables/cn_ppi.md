# `cn_ppi` 标准化表契约

- 功能：获取PPI工业生产者出厂价格指数数据
- PostgreSQL 表：`tushare_norm_cn_ppi`
- 契约版本：`1`
- 技术主键：`_record_hash`（原始 payload SHA-256）
- 主日期字段：`无`
- 必填身份字段：`month`
- 业务身份字段：`month`
- 业务身份可信度：`heuristic`
- 当前数据视图：未创建（业务身份仍为启发式，REST 保留全部 payload 版本）
- 原始数据表：`tushare_raw_record`（`api_name=cn_ppi`）
- REST：`GET /api/v1/datasets/cn_ppi/records`
- 接口 REST：`GET /api/v1/interfaces/cn_ppi/records`
- 标准化实现：[service/tushare_normalization.py](../../../service/tushare_normalization.py)

## 业务字段

| 字段 | 上游类型 | PostgreSQL 类型 | 说明 |
|---|---|---|---|
| `month` | `str` | `TEXT` | 月份YYYYMM |
| `ppi_yoy` | `float` | `NUMERIC` | PPI：全部工业品：当月同比 |
| `ppi_mp_yoy` | `float` | `NUMERIC` | PPI：生产资料：当月同比 |
| `ppi_mp_qm_yoy` | `float` | `NUMERIC` | PPI：生产资料：采掘业：当月同比 |
| `ppi_mp_rm_yoy` | `float` | `NUMERIC` | PPI：生产资料：原料业：当月同比 |
| `ppi_mp_p_yoy` | `float` | `NUMERIC` | PPI：生产资料：加工业：当月同比 |
| `ppi_cg_yoy` | `float` | `NUMERIC` | PPI：生活资料：当月同比 |
| `ppi_cg_f_yoy` | `float` | `NUMERIC` | PPI：生活资料：食品类：当月同比 |
| `ppi_cg_c_yoy` | `float` | `NUMERIC` | PPI：生活资料：衣着类：当月同比 |
| `ppi_cg_adu_yoy` | `float` | `NUMERIC` | PPI：生活资料：一般日用品类：当月同比 |
| `ppi_cg_dcg_yoy` | `float` | `NUMERIC` | PPI：生活资料：耐用消费品类：当月同比 |
| `ppi_mom` | `float` | `NUMERIC` | PPI：全部工业品：环比 |
| `ppi_mp_mom` | `float` | `NUMERIC` | PPI：生产资料：环比 |
| `ppi_mp_qm_mom` | `float` | `NUMERIC` | PPI：生产资料：采掘业：环比 |
| `ppi_mp_rm_mom` | `float` | `NUMERIC` | PPI：生产资料：原料业：环比 |
| `ppi_mp_p_mom` | `float` | `NUMERIC` | PPI：生产资料：加工业：环比 |
| `ppi_cg_mom` | `float` | `NUMERIC` | PPI：生活资料：环比 |
| `ppi_cg_f_mom` | `float` | `NUMERIC` | PPI：生活资料：食品类：环比 |
| `ppi_cg_c_mom` | `float` | `NUMERIC` | PPI：生活资料：衣着类：环比 |
| `ppi_cg_adu_mom` | `float` | `NUMERIC` | PPI：生活资料：一般日用品类：环比 |
| `ppi_cg_dcg_mom` | `float` | `NUMERIC` | PPI：生活资料：耐用消费品类：环比 |
| `ppi_accu` | `float` | `NUMERIC` | PPI：全部工业品：累计同比 |
| `ppi_mp_accu` | `float` | `NUMERIC` | PPI：生产资料：累计同比 |
| `ppi_mp_qm_accu` | `float` | `NUMERIC` | PPI：生产资料：采掘业：累计同比 |
| `ppi_mp_rm_accu` | `float` | `NUMERIC` | PPI：生产资料：原料业：累计同比 |
| `ppi_mp_p_accu` | `float` | `NUMERIC` | PPI：生产资料：加工业：累计同比 |
| `ppi_cg_accu` | `float` | `NUMERIC` | PPI：生活资料：累计同比 |
| `ppi_cg_f_accu` | `float` | `NUMERIC` | PPI：生活资料：食品类：累计同比 |
| `ppi_cg_c_accu` | `float` | `NUMERIC` | PPI：生活资料：衣着类：累计同比 |
| `ppi_cg_adu_accu` | `float` | `NUMERIC` | PPI：生活资料：一般日用品类：累计同比 |
| `ppi_cg_dcg_accu` | `float` | `NUMERIC` | PPI：生活资料：耐用消费品类：累计同比 |

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
