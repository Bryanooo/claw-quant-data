# `cn_pmi` 标准化表契约

- 功能：采购经理人指数
- PostgreSQL 表：`tushare_norm_cn_pmi`
- 契约版本：`1`
- 技术主键：`_record_hash`（原始 payload SHA-256）
- 主日期字段：`无`
- 必填身份字段：`month`
- 业务身份字段：`month`
- 业务身份可信度：`heuristic`
- 当前数据视图：未创建（业务身份仍为启发式，REST 保留全部 payload 版本）
- 原始数据表：`tushare_raw_record`（`api_name=cn_pmi`）
- REST：`GET /api/v1/datasets/cn_pmi/records`
- 接口 REST：`GET /api/v1/interfaces/cn_pmi/records`
- 标准化实现：[service/tushare_normalization.py](../../../service/tushare_normalization.py)

## 业务字段

| 字段 | 上游类型 | PostgreSQL 类型 | 说明 |
|---|---|---|---|
| `month` | `str` | `TEXT` | 月份YYYYMM |
| `pmi010000` | `float` | `NUMERIC` | 制造业PMI |
| `pmi010100` | `float` | `NUMERIC` | 制造业PMI:企业规模/大型企业 |
| `pmi010200` | `float` | `NUMERIC` | 制造业PMI:企业规模/中型企业 |
| `pmi010300` | `float` | `NUMERIC` | 制造业PMI:企业规模/小型企业 |
| `pmi010400` | `float` | `NUMERIC` | 制造业PMI:构成指数/生产指数 |
| `pmi010401` | `float` | `NUMERIC` | 制造业PMI:构成指数/生产指数:企业规模/大型企业 |
| `pmi010402` | `float` | `NUMERIC` | 制造业PMI:构成指数/生产指数:企业规模/中型企业 |
| `pmi010403` | `float` | `NUMERIC` | 制造业PMI:构成指数/生产指数:企业规模/小型企业 |
| `pmi010500` | `float` | `NUMERIC` | 制造业PMI:构成指数/新订单指数 |
| `pmi010501` | `float` | `NUMERIC` | 制造业PMI:构成指数/新订单指数:企业规模/大型企业 |
| `pmi010502` | `float` | `NUMERIC` | 制造业PMI:构成指数/新订单指数:企业规模/中型企业 |
| `pmi010503` | `float` | `NUMERIC` | 制造业PMI:构成指数/新订单指数:企业规模/小型企业 |
| `pmi010600` | `float` | `NUMERIC` | 制造业PMI:构成指数/供应商配送时间指数 |
| `pmi010601` | `float` | `NUMERIC` | 制造业PMI:构成指数/供应商配送时间指数:企业规模/大型企业 |
| `pmi010602` | `float` | `NUMERIC` | 制造业PMI:构成指数/供应商配送时间指数:企业规模/中型企业 |
| `pmi010603` | `float` | `NUMERIC` | 制造业PMI:构成指数/供应商配送时间指数:企业规模/小型企业 |
| `pmi010700` | `float` | `NUMERIC` | 制造业PMI:构成指数/原材料库存指数 |
| `pmi010701` | `float` | `NUMERIC` | 制造业PMI:构成指数/原材料库存指数:企业规模/大型企业 |
| `pmi010702` | `float` | `NUMERIC` | 制造业PMI:构成指数/原材料库存指数:企业规模/中型企业 |
| `pmi010703` | `float` | `NUMERIC` | 制造业PMI:构成指数/原材料库存指数:企业规模/小型企业 |
| `pmi010800` | `float` | `NUMERIC` | 制造业PMI:构成指数/从业人员指数 |
| `pmi010801` | `float` | `NUMERIC` | 制造业PMI:构成指数/从业人员指数:企业规模/大型企业 |
| `pmi010802` | `float` | `NUMERIC` | 制造业PMI:构成指数/从业人员指数:企业规模/中型企业 |
| `pmi010803` | `float` | `NUMERIC` | 制造业PMI:构成指数/从业人员指数:企业规模/小型企业 |
| `pmi010900` | `float` | `NUMERIC` | 制造业PMI:其他/新出口订单 |
| `pmi011000` | `float` | `NUMERIC` | 制造业PMI:其他/进口 |
| `pmi011100` | `float` | `NUMERIC` | 制造业PMI:其他/采购量 |
| `pmi011200` | `float` | `NUMERIC` | 制造业PMI:其他/主要原材料购进价格 |
| `pmi011300` | `float` | `NUMERIC` | 制造业PMI:其他/出厂价格 |
| `pmi011400` | `float` | `NUMERIC` | 制造业PMI:其他/产成品库存 |
| `pmi011500` | `float` | `NUMERIC` | 制造业PMI:其他/在手订单 |
| `pmi011600` | `float` | `NUMERIC` | 制造业PMI:其他/生产经营活动预期 |
| `pmi011700` | `float` | `NUMERIC` | 制造业PMI:分行业/装备制造业 |
| `pmi011800` | `float` | `NUMERIC` | 制造业PMI:分行业/高技术制造业 |
| `pmi011900` | `float` | `NUMERIC` | 制造业PMI:分行业/基础原材料制造业 |
| `pmi012000` | `float` | `NUMERIC` | 制造业PMI:分行业/消费品制造业 |
| `pmi020100` | `float` | `NUMERIC` | 非制造业PMI:商务活动 |
| `pmi020101` | `float` | `NUMERIC` | 非制造业PMI:商务活动:分行业/建筑业 |
| `pmi020102` | `float` | `NUMERIC` | 非制造业PMI:商务活动:分行业/服务业业 |
| `pmi020200` | `float` | `NUMERIC` | 非制造业PMI:新订单指数 |
| `pmi020201` | `float` | `NUMERIC` | 非制造业PMI:新订单指数:分行业/建筑业 |
| `pmi020202` | `float` | `NUMERIC` | 非制造业PMI:新订单指数:分行业/服务业 |
| `pmi020300` | `float` | `NUMERIC` | 非制造业PMI:投入品价格指数 |
| `pmi020301` | `float` | `NUMERIC` | 非制造业PMI:投入品价格指数:分行业/建筑业 |
| `pmi020302` | `float` | `NUMERIC` | 非制造业PMI:投入品价格指数:分行业/服务业 |
| `pmi020400` | `float` | `NUMERIC` | 非制造业PMI:销售价格指数 |
| `pmi020401` | `float` | `NUMERIC` | 非制造业PMI:销售价格指数:分行业/建筑业 |
| `pmi020402` | `float` | `NUMERIC` | 非制造业PMI:销售价格指数:分行业/服务业 |
| `pmi020500` | `float` | `NUMERIC` | 非制造业PMI:从业人员指数 |
| `pmi020501` | `float` | `NUMERIC` | 非制造业PMI:从业人员指数:分行业/建筑业 |
| `pmi020502` | `float` | `NUMERIC` | 非制造业PMI:从业人员指数:分行业/服务业 |
| `pmi020600` | `float` | `NUMERIC` | 非制造业PMI:业务活动预期指数 |
| `pmi020601` | `float` | `NUMERIC` | 非制造业PMI:业务活动预期指数:分行业/建筑业 |
| `pmi020602` | `float` | `NUMERIC` | 非制造业PMI:业务活动预期指数:分行业/服务业 |
| `pmi020700` | `float` | `NUMERIC` | 非制造业PMI:新出口订单 |
| `pmi020800` | `float` | `NUMERIC` | 非制造业PMI:在手订单 |
| `pmi020900` | `float` | `NUMERIC` | 非制造业PMI:存货 |
| `pmi021000` | `float` | `NUMERIC` | 非制造业PMI:供应商配送时间 |
| `pmi030000` | `float` | `NUMERIC` | 中国综合PMI:产出指数 |

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
