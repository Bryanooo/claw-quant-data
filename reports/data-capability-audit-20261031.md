# claw-quant-data 数据能力盘点（2026-10-31）

盘点口径：容器内代码 + PostgreSQL 实际状态 + 控制台 API 返回值三者交叉核对。
数据日期 2026-10-31（周六），最近交易日 2026-10-30。

---

## 一、数据源 / 接口 / 采集能力

### 1.1 数据源（8 个）

| 数据源 | 注册端点 | 说明 |
|---|---|---|
| tushare | 202 | 主力，唯一批量落库的源 |
| financial_data | 8 | 白名单路由 163 条，**仅透传查询，响应不落库** |
| sina | 3 | 期权，query_through |
| chinabond | 2 | 收益率曲线 |
| chinamoney | 2 | LPR / repo |
| cninfo / sse / pboc | 各 1 | 互动易 / 上证 e 互动 / 社融 |

合计注册端点 **220** 个。

### 1.2 接口契约与权限（tushare）

- 契约接口 **244** 个，其中 **202 可采集**、**38 无权限**、1 个已下线、1 个有限频、1 个当前限频
- 采集器实现：**99** 个 Collector 类（`collectors/`）
- Cadence 分布（注册端点）：daily 124 / weekly 33 / monthly 8 / quarterly 6 / manual 31

### 1.3 上游硬性约束

| 约束 | 值 |
|---|---|
| cyq_perf 频率 | 20000 次/天（5000 积分档） |
| 单次返回上限 | 6000 行 |
| ts_code | **必填**，不能按 trade_date 一次拉全市场 |
| 批量方式 | ts_code + start_date/end_date，系统 fanout 窗口上限 31 天 |
| 全市场一天成本 | ≈ 5570 次调用（逐股）；区间批量后一周 ≈ 5570 次 |

---

## 二、已配置的采集任务

V2 active 任务定义 **205** 个：

| 调度模式 | 数量 | 含义 |
|---|---|---|
| cron | 167 | 定时跑 |
| **disabled** | **33** | 定义存在但**永不自动执行** |
| dependency | 4 | 派生任务（上游就绪后触发） |
| manual | 1 | 手工触发 |

33 个被禁用调度中影响较大的：
财报类 `balancesheet / cashflow / income / express / financial_indicator / fina_mainbz / fina_audit`、
`fund_basic`、`fut_basic / fut_holding / fut_index_daily`、`index_weight / index_member_all`、
`us_daily`、`ccass_hold_detail`、`pledge_stat`、`stk_mins`、`stk_rewards`、`stock_hsgt`、`tdx_member`。

**完全没有任务的接口（7 个，可采集但永不执行）**：
`balancesheet / cashflow / express / fina_indicator / fina_mainbz / income / forecast`（非 VIP 键）。

当前实例：活跃 122（1 running / 101 queued / 20 retrying），**attention 65**。

---

## 三、数据集采集情况

207 个可审计数据集，206 个有新鲜度记录。

### 3.1 新鲜度分布

| 状态 | 数量 |
|---|---|
| fresh | 87 |
| event_driven（无 SLA，不判过期） | 70 |
| not_applicable | 31 |
| **stale** | **10** |
| empty（0 行） | 7 |

### 3.2 确认的缺数据清单

| 数据集 | 情况 | 严重度 |
|---|---|---|
| **cyq_perf** | 数据止于 **10-23**，缺 10-26~10-30 共 5 个交易日；控制台未标记 | 高（因子在用） |
| **cyq_chips** | 缺 10-26~10-30（5 天）+ 1990 个 partial；正在全历史回补 | 高 |
| **us_daily** | **9249 个缺失分区**，最新仅到 10-16；任务调度 disabled | 中 |
| **local_factor_snapshot** | 10-19~10-30 连续 20 天 partial，validation 未通过 | 中 |
| **factor_value** | 10-19~10-22 partial + 10-21 缺失；任务调度 disabled | 中 |
| **dc_hot / ggt_daily / kpl_list / ths_hot** | 任务每天 success 但 `rows_fetched=0`；数据停在 09-24~09-30 | 中（静默空采） |
| **forex_daily / hk_hold / stk_auction_c/o** | 同上，停在 09-24 / 09-30 | 中 |
| **ant_* 6 个** | 0 行（financial_data 透传源，本就不落库） | 低（设计如此） |

### 3.3 正在进行的回补

`cyq_chips` 全历史回补：128 个窗口（101 排队 / 24 已完成 / 1 retrying / 2 superseded），
约 1 个窗口/小时 → 预计 4 天左右完成。

### 3.4 正常的（对照组）

`adj_factor / moneyflow / stk_factor / daily_basic / index_daily(除 10-19~20)` 等核心日频数据集
均 complete 且 fresh 到 10-30/10-31。

---

## 四、控制台 vs 实际：6 处不一致

### ① 控制台"接口"415 个 ≠ 实际可采集 202 个

- 415 = tushare 244 + financial_data 163 + 其他 8
- financial_data 的 163 条是 **on-demand 透传路由**（官方口径："provider response records are not stored"）
- 只有 `acquisition_kind=scheduled` 的 202 条才是真正会落库的采集能力
- **原因**：`/api/v1/data/dependencies/interfaces` 把"契约/查询路由"和"采集能力"合并成一个列表返回

### ② 10 个接口显示"已调度"，实际任务调度 disabled

最典型 `us_daily`：控制台 `cadence=daily / scheduled`，实际 `schedule_mode=disabled`，
数据缺 9249 个分区、最新只到 10-16。同类还有：

| 接口 | 控制台显示 | 实际 |
|---|---|---|
| us_daily | daily / scheduled | disabled |
| factor_value | daily / scheduled | disabled |
| balancesheet_vip / cashflow_vip / express_vip / fina_indicator_vip / fina_mainbz_vip / income_vip | weekly | manual + disabled |
| monthly / weekly (stk_weekly_monthly) | daily | disabled |

- **原因**：接口视图的 cadence 来自**契约策略推导**（`tushare_policy`），是否真跑取决于 **V2 任务定义的 `schedule.mode`**。两套配置独立维护，没有回写校验。

### ③ cyq_perf 落后 5 个交易日，控制台显示 complete

- 实际：数据到 10-23；10-26~10-30 无
- 控制台：coverage `status=complete`（审计只覆盖到 10-25）、freshness `event_driven`（SLA=null，永不判过期）
- **原因 1**：10-21 改为 **weekly 批量采集**（cron `30 20 * * 5`），收"已闭周"→ 当周数据要下周才采，天然滞后一周
- **原因 2**：审计 horizon 跟到"最后一次发布状态"（W43 = 至 10-25），未发布的周不在审计范围 → 缺口不可见
- **原因 3**：weekly cadence 被归为 event_driven，失去 freshness SLA

### ④ 控制台两个面板口径不一致（2026-10-31 已修复）

- `/ops/coverage`：`with_gaps = 4`（cyq_chips / factor_value / local_factor_snapshot / us_daily）
- `/ops/data-health` 与 `/system/overview`：`datasets_with_gaps = 2`（只算 cyq_chips / local_factor_snapshot）
- **原因**：health 把 `DEFERRED_RESEARCH_DATASETS`（`us_daily`、`factor_value`）且当前没有活跃任务的
  数据集从「运行范围」里剔除，只报剩下的部分，字段名却没有体现这个范围，于是看起来像与 coverage 打架
- **修复**：summary 增加 `coverage_scope`（总 / 已审计 / 运行范围 / 延后数据集清单）与
  `deferred_*`、`total_*` 三组字段。实测 `total_datasets_with_gaps = 4`、
  `total_missing_partitions = 9255`、`total_partial_partitions = 2034`，与 `/ops/coverage` 逐项对齐；
  报警语义不变（延后的两个仍不进 issues）

### ⑤ 任务"成功"但数据不更新（静默空采）

`dc_hot / ggt_daily / kpl_list / ths_hot / forex_daily / hk_hold / stk_auction_c/o`：
每天 19:15（UTC 11:15）执行，`rows_fetched=0`、`completion_status=empty` → validate → publish → success。

**实测上游 10-30 确实有数据**（手动调 `ths_hot`、`ggt_daily` 均返回内容）→ 是**采集时点早于上游发布**，
空结果被判为终态成功，之后不再补采。

- 控制台表现：freshness 标 stale（正确），但 executions 面板显示 success（易误判为正常）

### ⑥ 6 个 ant_* 数据集 0 行却列为数据集

`ant_hot_stock_rank / ant_hot_plate_rank / ant_free_float / ant_equity_structure / ant_style_classification / ant_controlling_shareholder / ant_actual_controller`
- **原因**：financial_data 是 query_through，响应不落库；但覆盖规则仍为它们建了审计条目 → 恒定 empty / rate_limited attention

---

## 五、对下游 factor-lab 的影响

`cyq_perf` 改为周频后，factor-lab 的筹码类因子（flow-chip 因子集 5 个筹码因子）
**永远滞后 1 周**，且控制台不会报警。10-31 的截面实际用的是 10-23 的筹码数据。

---

## 六、排查中发现的系统性问题

### ⑦ 覆盖审计 evidence 巨型 jsonb 拖垮整库查询

`sys_data_coverage_audit.evidence` 是 jsonb 大字段，`cyq_chips` 的全历史审计单行 **54 MB**（共 3 条，
占 416 MB 表体积的 1/3 以上）。凡是把 `evidence->>'rule_revision'` 直接写进「审计表 ⋈ 分区表」连接条件的
查询，每命中一行分区都要重新 detoast 一次 evidence：

- `current_problem_partitions`（scheduler 每 30 秒的初始化协调器、worker 补采规划都在调）：
  **实测 203 秒 / 393k 分区 / 14.5M buffer hits**
- 直接后果：`V2 初始化协调器` 单次执行远超 30 秒周期，日志里持续 `skipped: maximum number of running
  instances reached` —— 即该协调器长期只跑得动一个实例，后续调度全部空转
- 数据集审计报告生成器同样卡在同一条查询上，10-21 之后一直跑不出新报告

**已修复**（commit `f87d95c`）：改为 `WITH audit_rev AS MATERIALIZED` 先求值一次 rule_revision 再连接，
同一查询 **203s → 1.3s**，审计报告生成 **跑不完 → 4 秒**。

**仍建议跟进**：evidence 写入侧应限制 payload 体积（当前把逐日 security_dates 明细整个塞进 evidence），
或迁到 sidecar 表；否则任何未来新增的「整表 ⋈」查询都会再次踩坑。

## 七、建议优先级

| 优先级 | 事项 | 理由 |
|---|---|---|
| P0 | `cyq_perf` 恢复日频增量采集（或 T+1 补采当周） | 筹码因子现在恒定滞后一周，控制台不报警 |
| P0 | 「空采 = 成功」改为可重试 | 7 个数据集 19:15 抓取早于上游发布，`rows_fetched=0` 仍判终态成功，数据停在 9 月底 |
| P0 | ~~统一控制台口径~~（2026-10-31 已修复） | `ops/coverage` 的 with_gaps=4 与 `data-health` 的 =2 口径已对齐（新增 `coverage_scope` / `total_*`）；接口视图 cadence 回读 V2 `schedule.mode` 仍未做 |
| P1 | `ant_*` 6 个数据集移出覆盖规则 | query_through 不落库，恒定 empty 只会制造噪音 attention |
| P1 | evidence payload 瘦身 | 见第六节 ⑦，属结构性隐患 |
| P2 | 33 个 disabled 任务逐个定调 | 要么恢复调度，要么在控制台明确标 deferred，不要留「显示 scheduled、实际 disabled」的错位 |
| P2 | `us_daily / cyq_chips / factor_value` 额度方案 | 三者都是额度硬约束，需要明确的降级口径（周频 / 抽样 / 外部预算），不能长期挂在「缺失分区」里 |

