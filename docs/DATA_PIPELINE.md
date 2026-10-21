# 数据生产与质量

本文合并说明采集器、任务执行、完整性审计和数据查询治理。

## 一个实例的边界

一个 `task_execution` 对应一个可独立验收的逻辑周期：交易日、自然周、自然月、报告期
或快照。分页、日期窗口收缩、证券/市场枚举都在 `acquire` 节点内部完成，不拆成调度层
叶任务。

采集任务固定包含：

1. `condition`：判断交易日、发布时间和运行条件；
2. `scope_plan`：冻结业务日期、分区、请求参数和幂等身份；
3. `acquire`：穷尽分页/范围、幂等落库并保存请求证据；
4. `validate`：独立审计业务表、实体覆盖和传输完整性；
5. `publish`：验证通过后发布数据集状态。

派生任务使用 `condition → dependencies → scope_plan → transform → validate → publish`，
只读取已发布为 ready 的输入状态，不访问上游。输入状态版本会冻结到实例中；上游修复
重新发布后会产生新的可追溯派生实例。

## 控制面

`orchestration_v2` 使用五张表：

| 表 | 职责 |
|---|---|
| `acquisition_endpoint` | 来源 Endpoint 契约、handler 引用和凭据引用 |
| `task_definition` | 草稿、生效版本和历史版本 |
| `task_execution` | 实例范围、节点状态、租约、重试和最终错误 |
| `task_execution_event` | 追加式节点、请求、验证和状态证据 |
| `dataset_state` | 按数据日期/报告期发布的严格数据状态 |

Scheduler 只创建实例，不直接调用上游。例行、历史修复和派生任务使用独立资源池；历史
资源池在交易日 08:30–16:00 不领取新任务，避免与盘中日常采集争抢资源。

## 采集器契约

```text
CollectorSpec + CollectorRequest
             ↓
 fetch → transform/validate → store
             ↓
 CollectorResult + request evidence
```

- `CollectorSpec` 声明 API、业务表、主键、分页、空数据和资源类别。
- `CollectorRequest` 固化本次范围，运行中不可被调用方改变。
- `CollectorResult` 返回获取/写入行数、请求次数、空数据原因和证据。
- 通用采集器处理可参数化的稳定契约；专项采集器处理特殊分页、转换或多接口合并。
- 接口、采集器类、任务和业务表不是一一对应关系，数量只能从机器目录读取。

`tushare_raw_request` 始终保存脱敏参数、状态、行数和摘要；`tushare_raw_record` 仅保存
异常原文和历史存量归档。规范化错误与字段漂移分别进入专用错误表，不污染标准表。

## 重试、检查点与隔离

- 网络、超时、限流和数据库瞬时错误分类退避；参数、权限和契约错误不盲目重试。
- Worker 使用租约和心跳；进程退出后实例可安全回收。
- acquire 节点保存请求级检查点，重试跳过已经验证完成的请求。
- 远程等待期间不持有数据库事务；批量 UPSERT 使用幂等主键。
- 所有 Worker 共享全局和接口级限流，并发不会绕过供应商额度。
- `cyq_perf`、`index_weight` 作为配额保护任务按接口串行领取。
- `us_daily` 保留存量数据和查询契约，但当前研究范围不包含美股日线；任务定义、日常调度、
  初始化和缺口恢复均已停用，避免每小时一次的接口限制持续消耗额度。
- `cyq_chips`、ETF 成分和 `moneyflow_dc` 按周使用受控日期窗口采集，
  一个实体请求覆盖整周日频记录，避免按“证券 × 日期”重复调用。
- `factor_value` 按交易日和受控因子列表采集；单因子跨多日可能达到上游 6,000 行截断，
  因而不能合并成周窗口。
- 错误终态保留为历史，通过 supersede 和新定义创建替代实例。

无日期的手工快照任务必须在 `frozen_scope.manual_parameters` 中显式保存参数；空对象表示
经过评审的全市场快照，不等于允许任意无界请求。这样 `fund_basic` 一类手工接口也能走
完整的 acquire、分页检查点、validate 和 publish 链路。

## 数据审计

`task_execution.status=success` 只表示工作流走完，不能证明数据完整。完整性由业务表、
请求证据、代码所有的审计规则和 `dataset_state` 共同决定。

| 审计模式 | 适用对象 | 完成证明 |
|---|---|---|
| `expected_partition` | 稳定发布的日/周/月/季度数据 | 应有分区、实体覆盖和传输证据 |
| `observed_scope_transport` | 稀疏事件数据 | 声明范围终态、分页穷尽且无未解决失败 |
| `exhaustive_snapshot` | 无日期快照 | 非空快照或供应商权威空结果及穷尽证据 |
| `dependency_scoped` | 派生数据 | 输入就绪且输出业务范围通过验证 |

数据状态包括 `pending`、`complete`、`empty_verified`、`gaps`、`partial` 和
`indeterminate`。只有精确范围请求成功、零行且证据可验证时，才能发布
`empty_verified`。

全盘扫描只按当前规则版本生成修复建议。初始化也是“严格审计 → repair 实例 → 同一
采集与验证链 → 再审计”，不维护第二套采集器。

`index_basic` 是发现目录，含不由 `index_daily` 发布的系列且没有统一失效日期，不能作为
指数日线的当日完整分母。`index_daily` 使用前后 14 日内最近 6 个已观测截面的最大值作为
基线，并保留 85% 阈值；漏掉一个 5,000 行分页会被检出，供应商支持范围变化不会制造
永久假缺口。若旧执行已保存分页穷尽证据而只因旧业务规则进入 attention，修订审计规则时
复用该传输证据，不重复调用供应商。

## Dashboard 语义

- 今日运营：业务日应执行的例行任务及交付验证；
- 采集任务：任务定义和内部节点；
- 执行实例：所有实例、节点事件、尝试和重试；
- 异常中心：尚未被后续成功状态覆盖的 attention；
- 数据日历：按 `observation_date` 展示数据状态，不按任务创建日期；
- 初始化：全量审计、修复和再次审计。

主要入口：

```text
GET /api/v1/ops/orchestration-v2/summary
GET /api/v1/ops/orchestration-v2/executions
GET /api/v1/ops/delivery/data-calendar
GET /api/v1/ops/data-health
GET /api/v1/ops/initialization
GET /api/v1/ops/coverage
```

## 数据查询治理

标准数据查询默认只允许业务键和来源键。低选择性指标字段需要显式
`filter_mode=advanced`，并附带日期范围或至少一个标准业务键，防止无界全表扫描。

浅分页支持有限 `offset`；深分页使用绑定数据集和稳定排序列的不透明 `next_cursor`。
cursor 不可跨数据集复用，也不能与非零 offset 或总数扫描组合。

大型热表索引使用经审核的 `CREATE INDEX CONCURRENTLY` 迁移，在容量检查后显式发布。
发布后必须观察 `pg_stat_progress_create_index` 并用真实查询的
`EXPLAIN (ANALYZE, BUFFERS)` 验证，不能只看索引是否存在。

## 验证入口

```bash
python3 scripts/check_documentation.py
PYTHONPATH=. .venv/bin/python scripts/generate_dataset_audit_report.py
PYTHONPATH=. .venv/bin/python scripts/report_tushare_data_presence.py
PYTHONPATH=. .venv/bin/python scripts/audit_factor_lab_supply.py \
  --output reports/factor-lab-supply-YYYYMMDD
```

研究接口另由 `scripts/validate_research.py` 验证问题、API、数据集和底层表的穿透关系；
研究验收不能替代底层数据审计。
`audit_factor_lab_supply.py` 是只读验收，不会自动提交补采；它逐领域核对注册、输入契约、
严格覆盖结果并测量代表性查询延迟。失败项必须先形成明确补采范围，再交给 V2 执行。

## ETF 下游数据验收

`scripts/backfill_etf_rotation.py` 对固定 ETF 池按证券和年度补采，JSONL 记录每个请求范围的成功、失败和空响应。采集完成不等于数据具备回测能力。`GET /api/v1/data/etf-rotation/contract` 提供 `config/etf_rotation_events.json` 中核验过的停牌、拆分与合并证据及内容哈希；其中份额登记日、价格生效日和公告日期分别保存。

该证据包只解释已核验事件，不能替代完整的公司行为、盘中停牌或历史涨跌停数据源。股票接口空响应不能证明 ETF 没有事件。下游须对每次新增行情重新验收；遇到未解释缺口或复权变化时停止发布，并保留旧版本。

`GET /api/v1/data/etf-rotation/daily-facts?symbol=510300.SH&start_date=2019-01-01&end_date=2026-10-20`
提供单只 ETF 的日级派生事实。原始行情、分红保留在原表；派生数据不回写为供应商原始数据：

- 总回报采用税费前、除息日收盘价理论再投资口径，第一根收盘价基准为 100、首日收益为空。
  拆分使用基金公告的实际份额比例，现金使用 `fund_div`，并与东方财富分红历史按日期、
  每份金额、支付日交叉核对。支付日单独保留，不能拿理论指数替代实际现金到账账本。
- 涨跌停使用行情的 `pre_close` 参考价、历史有效规则与 Decimal 四舍五入至 0.001 元。
  不使用前一根实际收盘价替代除权或上市日参考价。159915 自 2020-08-24 使用 20%，
  588000 自上市使用 20%，池内其他 ETF 使用 10%。每条明确标记 `exchange_rule_derived`。
  原 `stk_limit` 表仅有两位小数，不能作为 ETF 千分位价格的验收依据；原记录保留供追溯。
- 状态区分当日成交、公告确认全天停牌；另附已核验盘中事件。正成交量不能证明全天可交易。
  159915 的 2021-02-09 开市停牌至 10:30 已附公告与确认资料，其余盘中未知不能填零。

2026-10-20 核验范围内有 21,874 条成交日线、5 个全天停牌日、22 次现金分红、8 次份额变动。
第三方交叉核对原文及哈希保存在 `reports/etf-rotation-20261020/crosscheck/`。
`scripts/audit_etf_dividend_history.py --output 新目录` 可重取独立证据；它不自动批准证据。
扩展日期前必须重新核对现金事件和规则有效期，更新配置中的审查范围；超出范围接口返回 422，
下游保持旧版本，避免把一次历史审查冒充永久覆盖。

股票 2026-01-05 至 2026-10-15 缺少的 187 个交易日是 `fama_french_daily` 派生记录，
不是全部股票行情缺失。已通过 V2 修复执行 130937..131123 补算，187 个执行均成功。
FF3 使用本项目已声明的日度分组方法与零无风险利率口径，不冒充官方 Fama–French 数据。

