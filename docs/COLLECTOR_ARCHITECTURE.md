# 采集器架构

采集器采用模块化单体加持久化 Worker 的设计。一个接口不等于一个 Python 类：
参数化通用采集器可以安全承载多个接口，专项采集器则负责规范化业务表。

## 统一执行契约

所有采集器共享以下生命周期：

```text
CollectorSpec + CollectorRequest
             ↓
          fetch
             ↓
   raw request + raw records
             ↓
       transform/validate
             ↓
           store
             ↓
       CollectorResult
             ↓
   V2 task execution + coverage audit
```

- `CollectorSpec` 静态声明 API、表、主键、分页、写入、空数据和资源类别。
- `CollectorRequest` 固化本次请求参数和分区，运行期间不可被调用方修改。
- `CollectorResult` 返回获取/写入行数、真实请求次数、空数据原因、采集器版本和证据。
- `run()` 是标准入口；`collect()` 暂时保留整数返回值，兼容旧脚本。
- 财务采集器同样使用 `run(period=...)`；`fetch_period()` 与 `save()` 仅作兼容。

核心定义见 [collectors/contracts.py](../collectors/contracts.py) 和
[collectors/base.py](../collectors/base.py)。

## 通用与专项采集器

| 类型 | 数量口径 | 数据落点 | 适用场景 |
|---|---:|---|---|
| 通用契约采集 | 1 个参数化类承载 95 个 API | 原始表 + 95 张强类型标准表 | 完整覆盖、审计、重放和稳定查询 |
| 专项/等价专项 | 约 98 个类覆盖 106 个 API | 统一原始审计层 + 领域规范化表 | 查询、分析、完整性审计 |

部分普通接口与 VIP 接口共用一个专项实现；同一个上游接口也可能派生多个业务表，
因此“类数量”“唯一 API 数量”“业务表数量”不会相等。

数据服务物理落点是193张表：97张领域专项表、95张契约标准表和1张统一原始记录表；
另有 `tushare_raw_request` 保存每次传输请求证据。原始层只承担无损落地、审计和
重放；`tushare_norm_*` 使用明确的 `DATE`、
`NUMERIC`、`BIGINT`、`TIMESTAMP` 和 `TEXT` 字段。REST Dataset Registry 从
`CollectorContract` 与 `NormalizationContract` 生成静态允许列表。CI 和
PostgreSQL 集成测试会同时检查表注册、字段类型、主键、过滤列和日期列。

字段转换失败不会污染标准表：失败行进入 `sys_tushare_normalization_error`；字段
新增或缺失进入 `sys_tushare_schema_drift`；契约外字段仍保存在 `_extra_payload`。
生产默认直接从内存响应规范化，异常时才归档逐行原文；修复契约后可使用
`scripts/normalize_tushare_raw.py` 对异常归档或存量原始数据幂等重放。

## 性能与隔离

- 通用 UPSERT 使用 `execute_values` 批量写入，不再逐条拼接请求。
- 冲突更新使用 `IS DISTINCT FROM`，相同数据不会产生无意义更新。
- HTTP transport 不做隐藏 POST 重试；每次重试都重新通过 Token 全局限流。
- HTTP 使用独立的建连/读取超时（默认 5/60 秒），网络不可达会快速交回持久化
  队列；`index_daily` 与 `stk_limit` 使用实测可完整返回的 5000 行大页，减少分页请求。
- 请求参数、状态、返回行数和响应哈希永久保留；生产默认仅在规范化、校验或业务落库
  异常时保存逐行 JSONB。`TUSHARE_RAW_RECORD_CAPTURE_MODE=all` 仅用于短期排障，
  `none` 则完全关闭逐行原文；三种模式都保留请求级证据。
- 原始表不建立业务未使用的 payload GIN 或 collected_at 重复索引；对外查询走规范化
  业务表，避免原始层每次 UPSERT 承担无意义的索引与热存储写放大。
- V2 执行实例保存 `priority` 与 `resource_class`。`priority` 只负责资源池内部排序，
  `resource_class` 则由 PostgreSQL 领取事务强制过滤。
- Docker 默认只运行两个 V2 Worker 池：`worker-v2-routine` 领取日常及参考类实例，
  `worker-v2-backfill` 领取初始化、历史补采和修复实例。已经开始的长回填不会占用
  日常执行槽；需要扩容时可独立 `--scale` 历史 Worker。
- 所有 Worker 仍共享数据库 Token 全局/接口级时间槽，并发执行不会绕过 Tushare
  限流；V2 租约、超时、完成证据和失败重试逻辑在各资源池中完全一致。
- 数据库事务只包围队列状态、检查点或批量写入，不在远程 API 等待期间持有事务。
- 上游必须按证券或市场拆分时，拆分只属于一个 V2 实例的 acquire 节点内部请求计划，
  不再生成“扇出任务”或“叶任务”。请求宇宙按观察期过滤上市/终止日期，并随实例
  冻结；分页、批次和断点都由节点内检查点恢复。
- `fund_nav` 按最近一年自然日、`fund_portfolio` 按最新已披露报告期执行全市场
  offset 穷尽采集并持久化分页检查点；实测确认分页互不重复，避免按三万余只基金扇出；
  `stk_rewards` 按官方支持的多代码契约每 20 只一组。
- `index_weight` 按指数扇出后对月度窗口执行 offset 穷尽；`fut_weekly_monthly`
  与 `stk_week_month_adj` 的上游 offset 存在页间重叠，因此初始化只采最近 7 天的
  已闭合周/月窗口，保持每个子任务低于响应上限。
- `index_daily` 除当日晚间采集外，工作日 09:35 再执行一次 T+1 穷尽复采，吸收
  上游晚到的指数市场记录；两次都保持幂等写入。

## 三层覆盖口径

1. **实现覆盖**：接口存在专项实现或通用安全实现。
2. **编排覆盖**：接口已经进入安全的日/周/月/季度自动任务。
3. **数据覆盖**：当前数据库存在正行数，并通过对应分区完整性审计。

运行以下命令可重新生成逐接口数据证据报告：

```bash
docker compose exec api python scripts/report_tushare_data_presence.py
```

输出位于 `reports/tushare_data_presence_latest.json` 和
`reports/tushare_data_presence_latest.md`。报告只陈述正行数证据；合法空分区仍需结合任务
的 V2 节点证据和覆盖审计判断，不能简单当成失败。
