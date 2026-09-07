# `fund_company` 标准化表契约

- 功能：获取公募基金管理人列表
- PostgreSQL 表：`tushare_norm_fund_company`
- 契约版本：`1`
- 技术主键：`_record_hash`（原始 payload SHA-256）
- 主日期字段：`end_date`
- 必填身份字段：`name`
- 业务身份字段：`name`
- 业务身份可信度：`contract_reviewed`
- 当前数据视图：`tushare_current_fund_company`
- 原始数据表：`tushare_raw_record`（`api_name=fund_company`）
- REST：`GET /api/v1/datasets/fund_company/records`
- 接口 REST：`GET /api/v1/interfaces/fund_company/records`
- 标准化实现：[service/tushare_normalization.py](../../../service/tushare_normalization.py)

## 业务字段

| 字段 | 上游类型 | PostgreSQL 类型 | 说明 |
|---|---|---|---|
| `name` | `str` | `TEXT` | 基金公司名称 |
| `shortname` | `str` | `TEXT` | 简称 |
| `short_enname` | `str` | `TEXT` | 英文缩写 |
| `province` | `str` | `TEXT` | 省份 |
| `city` | `str` | `TEXT` | 城市 |
| `address` | `str` | `TEXT` | 注册地址 |
| `phone` | `str` | `TEXT` | 电话 |
| `office` | `str` | `TEXT` | 办公地址 |
| `website` | `str` | `TEXT` | 公司网址 |
| `chairman` | `str` | `TEXT` | 法人代表 |
| `manager` | `str` | `TEXT` | 总经理 |
| `reg_capital` | `float` | `NUMERIC` | 注册资本 |
| `setup_date` | `str` | `DATE` | 成立日期 |
| `end_date` | `str` | `DATE` | 公司终止日期 |
| `employees` | `float` | `NUMERIC` | 员工总数 |
| `main_business` | `str` | `TEXT` | 主要产品及业务 |
| `org_code` | `str` | `TEXT` | 组织机构代码 |
| `credit_code` | `str` | `TEXT` | 统一社会信用代码 |

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
