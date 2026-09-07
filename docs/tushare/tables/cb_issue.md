# `cb_issue` 标准化表契约

- 功能：获取可转债发行数据
- PostgreSQL 表：`tushare_norm_cb_issue`
- 契约版本：`1`
- 技术主键：`_record_hash`（原始 payload SHA-256）
- 主日期字段：`ann_date`
- 必填身份字段：`ts_code`
- 业务身份字段：`ts_code`
- 业务身份可信度：`heuristic`
- 当前数据视图：未创建（业务身份仍为启发式，REST 保留全部 payload 版本）
- 原始数据表：`tushare_raw_record`（`api_name=cb_issue`）
- REST：`GET /api/v1/datasets/cb_issue/records`
- 接口 REST：`GET /api/v1/interfaces/cb_issue/records`
- 标准化实现：[service/tushare_normalization.py](../../../service/tushare_normalization.py)

## 业务字段

| 字段 | 上游类型 | PostgreSQL 类型 | 说明 |
|---|---|---|---|
| `ts_code` | `str` | `TEXT` | 转债代码 |
| `ann_date` | `str` | `DATE` | 发行公告日 |
| `res_ann_date` | `str` | `DATE` | 发行结果公告日 |
| `plan_issue_size` | `float` | `NUMERIC` | 计划发行总额（元） |
| `issue_size` | `float` | `NUMERIC` | 发行总额（元） |
| `issue_price` | `float` | `NUMERIC` | 发行价格 |
| `issue_type` | `str` | `TEXT` | 发行方式 |
| `issue_cost` | `float` | `NUMERIC` | 发行费用（元） |
| `onl_code` | `str` | `TEXT` | 网上申购代码 |
| `onl_name` | `str` | `TEXT` | 网上申购简称 |
| `onl_date` | `str` | `DATE` | 网上发行日期 |
| `onl_size` | `float` | `NUMERIC` | 网上发行总额（张） |
| `onl_pch_vol` | `float` | `NUMERIC` | 网上发行有效申购数量（张） |
| `onl_pch_num` | `int` | `BIGINT` | 网上发行有效申购户数 |
| `onl_pch_excess` | `float` | `NUMERIC` | 网上发行超额认购倍数 |
| `onl_winning_rate` | `float` | `NUMERIC` | 网上发行中签率（%） |
| `shd_ration_code` | `str` | `TEXT` | 老股东配售代码 |
| `shd_ration_name` | `str` | `TEXT` | 老股东配售简称 |
| `shd_ration_date` | `str` | `DATE` | 老股东配售日 |
| `shd_ration_record_date` | `str` | `DATE` | 老股东配售股权登记日 |
| `shd_ration_pay_date` | `str` | `DATE` | 老股东配售缴款日 |
| `shd_ration_price` | `float` | `NUMERIC` | 老股东配售价格 |
| `shd_ration_ratio` | `float` | `NUMERIC` | 老股东配售比例 |
| `shd_ration_size` | `float` | `NUMERIC` | 老股东配售数量（张） |
| `shd_ration_vol` | `float` | `NUMERIC` | 老股东配售有效申购数量（张） |
| `shd_ration_num` | `int` | `BIGINT` | 老股东配售有效申购户数 |
| `shd_ration_excess` | `float` | `NUMERIC` | 老股东配售超额认购倍数 |
| `offl_size` | `float` | `NUMERIC` | 网下发行总额（张） |
| `offl_deposit` | `float` | `NUMERIC` | 网下发行定金比例（%） |
| `offl_pch_vol` | `float` | `NUMERIC` | 网下发行有效申购数量（张） |
| `offl_pch_num` | `int` | `BIGINT` | 网下发行有效申购户数 |
| `offl_pch_excess` | `float` | `NUMERIC` | 网下发行超额认购倍数 |
| `offl_winning_rate` | `float` | `NUMERIC` | 网下发行中签率 |
| `lead_underwriter` | `str` | `TEXT` | 主承销商 |
| `lead_underwriter_vol` | `float` | `NUMERIC` | 主承销商包销数量（张） |

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
