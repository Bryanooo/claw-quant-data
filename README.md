# claw-quant-data

分析 Agent、Skill 与报告工具独立维护在 [claw-quant-agents](https://github.com/Bryanooo/claw-quant-agents)，本仓库负责数据与研究 API。

`claw-quant-data` 是面向个人与研究 Agent 的金融数据底座。系统负责多数据源接入、业务表落库、严格完整性审计、缺口恢复和研究层 REST/CLI 服务；因子组合、策略回测与投研工作流应建立在它之上，而不是混入采集控制面。

自 **2026-09-29** 起，Tushare 的日常采集、初始化、历史补采、数据校验和 Dashboard 全部由 V2 编排执行。V1 控制表、运行服务、路由和测试已经退出。

## 当前组成

- PostgreSQL：业务数据、审计证据和 V2 控制面，使用 Docker volume 持久化。
- API/Dashboard：`http://127.0.0.1:8000/dashboard`，所有 REST 路由位于 `/api/*`。
- Scheduler：只负责按日、周、月、季度创建 V2 执行实例，不直接访问上游。
- V2 routine workers：执行实时/例行任务。
- V2 backfill workers：执行初始化、补采和修复；A 股交易时段自动暂停历史负载。
- V2 derived worker：在输入数据通过同日期审计后，执行确定性派生和独立输出审计。
- Auditor：对业务数据独立审计，任务成功不等于数据就绪。
- Intraday worker：A股交易时段按5分钟轮次批量采集宽基ETF、申万一级行业、资金流和已开启观察的自选股，保存指标、信号、结论与质量证据。
- Backup：定时产生 PostgreSQL custom-format 备份及校验侧车文件。

系统当前收录 244 个 Tushare 接口契约，其中 202 个是当前 Token 可执行的只读采集接口。`us_daily` 虽然接口可执行，但因每小时一次的限制且近期不研究美股，当前仅保留存量查询并停止采集。可采集接口映射为 192 个原生采集任务；加上当前已物化的派生结果，共有 196 个可审计数据集。数字不相等是因为一个任务可以组合多个上游接口，也可以产出多个数据集。另有 14 个派生任务定义，其中已具备业务实现的版本才允许发布为 active。

### 盘中观察闭环

盘中观察完整运行在 claw-data：数据采集 → 质量检查 → 指标计算 → 信号分析 → 结论留痕。常态调度为5分钟；供应商对场内基金分钟K只支持 `P_Min1`，因此每轮批量获取最近1分钟K并持久化，分析与展示仍按5分钟轮次推进。每轮同时记录外层 `common_query` 调用数与内部子请求数，便于按两种可能的计费口径审计额度。

- 页面：控制台左侧“盘中观察”。
- 最新结论与历史：`GET /api/v1/intraday/overview`。
- 幂等执行当前5分钟轮次：`POST /api/v1/intraday/run`。
- 自选股观察开关：`PUT /api/v1/intraday/watchlist/{symbol}/observation`。
- 个股只有加入自选并主动开启观察后才进入实时采集范围。
- 结论描述市场状态、相对强弱和风险证据；仓位、买卖和组合执行仍属于策略层。
- 信号分为持续方向（强上涨、上涨、震荡、下跌、强下跌）与盘中事件（急跌、反转、普涨、轮动、相对强弱），两者独立保存和展示。

## V2 执行模型

### 统一日频研究特征

`local_factor_snapshot` 是 claw-data 的确定性研究派生数据，不覆盖也不混入
上游的 `tushare_norm_factor_value`。它按“交易日 × 股票”保存一个位置稳定的
`FLOAT8[272]` 数组，位置、公式、族别和重叠治理记录在
`local_factor_schema/local_factor_catalog`。101 个 Alpha101 与 171 个
Growth/Liquidity/Momentum/Quality/Reversal/Risk/Size/Value 因子由 V2
`local_factor_snapshot` 派生任务在行情、复权、估值、指数和证券主数据就绪后运行。
技术指标与 272 因子在同一任务、同一读取快照内计算并原子写入；额外技术特征放在
同一行的 `technical_values`，不再单独写另一张技术因子表。

相同公式和相同价格口径只计算一次：RSI14、MACD/DIF/DEA、SMA20、5 日收益和
Alpha101-101 在内存中计算一次、正式值只存一个数组位置，旧技术字段由只读视图投影；公式相似但价格口径、
单位或分母不同的指标不会冒充等价值。每行同时保存 272 位 ready mask、不可用
位置和输入/公式摘要，任务成功不等于每个因子都可用。

当前修正口径为 `local-272-v4`。旧版本保留作审计证据，但不通过正式查询自动回退。V4 将 Tushare 对照改为按数据日期固定种子的每日 512 只股票抽样，并以数据库级 15 分钟超时限制校验成本；抽样元数据和实际耗时随校验结果保存。若 Tushare 尚未发布当日 `factor_value`，校验记为 `provider_pending` 而不是公式失败；调度器每 15 分钟最多复验 8 个已到达参考数据的日期。
`audit_status/audit_evidence` 逐特征区分未解释缺值、可证明的上市暖机期和当日无行情；
`ready_mask` 只说明是否非空，不作为数据就绪证明。技术视图与272数组分别审计。
技术指标的上市暖机期按各自实际交易日窗口判断；零振幅 K 线上的价格区间比率记为
“公式不适用”并保留证据，不再冒充采集失败或填入伪造数值。
财务累计值仅在相邻季度齐备时转单季；`roe_ttm_lag63d` 使用63个交易日前已披露报表，
`lt_rec`（长期应收款）纳入采集和输入映射。既有历史行需要补采，新增字段不等于历史已齐。
财务/分红状态修订纳入派生任务的幂等身份；相关补采队列排空后自动重算，避免每补一个季度就重复计算。
历史资产负债表补字段仍遵守交易日16:00后的补采窗口。市场实体匹配也必须满足逐证券审计通过，不能用有物理行替代就绪。
字段级修复必须在实例冻结范围中声明 `force_acquire=true` 和所需响应字段；旧分区即使完整也不能短路采集。
此类实例只有出现 `node.acquire.request_completed` 的分页穷尽证据后，才可作为“已补字段”验收，任务状态成功本身不算证明。
成交额均值明确使用未复权实际人民币成交额；收益/成交额比值使用小数收益/人民币，
不为追求供应商相关性而猜测倍率。输入摘要覆盖实际数值，公式摘要覆盖实现源码。

- 因子目录：`GET /api/v1/research/factors/catalog`；控制台按 11 类研究用途、来源、系列、可用性筛选并分页。
- 选择性查询：`GET /api/v1/research/factors/{ts_code}?factor=rsi&factor=MACD&factor=niumen_line`
- 内部验证证据：`GET /api/v1/ops/factors/validation`；相关性达标不等于公式等价或逐值认证。
- 历史批量计算：`python scripts/backfill_local_factors.py --start YYYY-MM-DD --end YYYY-MM-DD`；默认每个交易日创建一个 V2 补采实例，由正式六节点工作流完成计算、独立审计和 `dataset_state` 发布。`--direct` 只用于开发诊断，支持安全续跑和最多 4 个日期并行，但不替代 V2 控制面的正式认证。
- 抽检 `matched` 要求至少30组配对且99%以上满足 `abs(error) <= 1e-5 + 1e-3*abs(reference)`；
  仅相关性≥0.90标为 `correlated`，不当作逐值通过。缺对照与本地缺值分开说明。
- `factor_value` 的采集、表和抽检保留，但从数据查询、研究供给及 factor-lab 输入中排除，禁止缺失回退。
- `technical_factor_snapshot` 现在仅是非物化兼容视图；其旧任务已退役。`roc_5` 为 `return_5d × 100` 的展示别名。
- 容量口径：6,000 只股票 × 252 个交易日 × 10 年为 1,512 万行；当前真实数组
  平均约 2.08 KiB，原 40–50 GiB 估算仅覆盖 272 数组，不包含此次合并的技术扩展字段。
  生产容量还需计入扩展 JSONB、索引、WAL 和备份，不应沿用旧估算作总容量承诺。
  长表会产生 41.1 亿行，因此不采用。

一个执行实例只对应一个业务逻辑周期，例如一个交易日、自然月或报告期。分页、股票/基金/指数枚举、市场分区都在该实例的 `acquire` 节点内穷举，不会制造叶任务。

固定节点为：

1. `condition`：判断该周期是否应执行。
2. `scope_plan`：冻结业务范围、参数和幂等身份。
3. `acquire`：穷举分页、分区和依赖实体并落库。
4. `validate`：使用独立审计代码核验业务表及传输证据。
5. `publish`：只有严格验证通过才发布 ready 状态。

派生任务增加 `dependencies` 与 `transform` 节点，不包含 `acquire`。当前投产的
`local_factor_snapshot` 按交易日一次计算全市场牛门线、确认/突破线和20/60日
成交成本线；结果通过通用数据接口查询，逐股研究接口仍可按任意历史时点即时计算。

V2 只有五张控制表：

| 表 | 用途 |
|---|---|
| `orchestration_v2.acquisition_endpoint` | 数据源接口契约、凭据引用、限流和完整性策略 |
| `orchestration_v2.task_definition` | 可版本化的任务定义；draft/active/retired 均保留 |
| `orchestration_v2.task_execution` | 一次逻辑周期的执行状态、租约、重试和最终错误 |
| `orchestration_v2.task_execution_event` | 追加式节点与采集证据，不允许修改或删除 |
| `orchestration_v2.dataset_state` | 数据事实状态，也是数据日历的权威来源 |

严格区分两件事：

- 执行成功：节点运行完毕、上游请求有可验证的终态。
- 数据就绪：业务表的目标分区、实体覆盖率和传输完整性通过独立审计。

## 数据源

### Tushare

Tushare 是当前批量历史和例行行情的主数据源。Token 只通过环境变量 `TUSHARE_TOKEN` 注入，不写入任务定义、日志或仓库。

### 蚂蚁数据源 MCP

系统已新增 `financial_data` connector，对接财跃星辰金融数据 MCP 的 `common_query` 接口：

```env
FINANCIAL_DATA_API_KEY=
FINANCIAL_DATA_BASE_URL=https://dfdatamcpnexus-prod.antgroup-inc.cn/api/v1/common_query
FINANCIAL_DATA_API_VERSION=1.6.0
```

调用入口：

```text
POST /api/v1/data/sources/financial_data/query
GET  /api/v1/data/sources/financial_data/usage
```

`data` 模式只允许 2026-09-29 盘点并复核过的 163 条精确业务路由（包括两条
`/api/v2/info/news/*` 路由）；未知路径会在本地拒绝，统一入口不是任意上游代理。
API Key 为空时 connector 会失败关闭，不会匿名请求或回退到伪数据。密钥必须只写入本机 `.env`；`.env` 不提交 Git。

多数据源统一通过 `service/source_connectors` 注册。定时拉取、网页快照、查询穿透和流式来源使用相同契约，但由 acquisition mode 明确区分。

这里的“相同契约”只保证 connector 的控制信封一致（`source_id`、状态、
行数、证据和告警），不保证不同供应商的原始记录字段一致。`/data/sources/*`
是源诊断/按需穿透入口，返回供应商原生模型；Agent 不应在这里随机切换数据源。
对 Agent 稳定承诺的是数据集层和 `/api/v1/research/*` 的规范模型：上游字段、
代码体系、单位、复权方式和时间语义必须先经 provider adapter 映射，审计通过后
才能进入规范模型。163 条 蚂蚁数据源 路由已经完成与 Tushare 244 条契约的
逐项语义映射，但这不等于 163 条规范适配器均已实现；供应商能力、当前 Token 权限、
本地规范落地是三个独立维度。目前已通过契约测试的有限回退包括 A 股日线/交易日历、证券身份/日度估值、
累计利润表/现金流量表/资产负债表、财务指标、滚动十二月财务、业绩预告/快报、分红、回购、股东户数、
主营构成、主要股东、解禁、质押、风险警示和停复牌，
以及基金档案、基金净值、基金股票持仓、基金分红、基金经理、指数档案和指数成分权重；
其余路由仍需逐项完成字段、日期、单位与代码适配。

当前 163 条 蚂蚁数据源 业务路由的操作口径如下；完整逐条清单由
`GET /api/v1/data/source-priorities` 提供，并可在 Dashboard“数据源”页面筛选：

| 分类 | 数量 | 当前含义 |
|---|---:|---|
| 实时必须依赖 蚂蚁数据源 | 4 | 交易状态、集合竞价快照、基础快照、派生快照；本地批量库无法替代实时查询 |
| 蚂蚁数据源 优先、无本地规范等价 | 102 | 当前只能通过显式供应商网关获取，尚未进入统一规范模型 |
| 本地优先、蚂蚁数据源 受控回退已就绪 | 29 | 正常读 Tushare/本地 DB，仅目标切片缺失且允许回退时消耗额度 |
| 本地已有重叠数据、蚂蚁数据源 适配待完成 | 28 | 当前应使用本地数据；不能把供应商原生字段混入规范接口 |

所以当前**实际依赖 蚂蚁数据源 的路由是 106 条**（4 条实时 + 102 条无本地规范
等价）。这里“无本地规范等价”只描述当前系统状态，不代表已经逐条证明 Tushare
完全没有语义相近接口，其中也可能包含尚未完成映射和标准化的缺口。

供应商语义能力另按四类互斥归档，不能与上面的“当前系统落地状态”混用：

| 供应商语义分类 | 数量 | 判定标准 |
|---|---:|---|
| Tushare 直接等价 | 26 | Tushare 结构化接口能覆盖 蚂蚁数据源 的完整业务合同 |
| Tushare 确定性派生 | 34 | 可由所列 Tushare 数据确定性计算，公式、权重和 as-of 规则必须版本化 |
| Tushare 公告原文解析 | 22 | 无结构化表，但 A 股事实可从 `anns_d` PDF 解析并保留证据链 |
| 蚂蚁数据源 必需 | 81 | Tushare 没有完整等价能力；其中 52 条存在局部市场或字段重叠，但不能冒充完整覆盖 |

当前 Tushare 目录共 244 条契约：202 条具备采集实现（200 条常规接口，另有
`hk_daily`/`us_daily` 2 条严格限频接口；`us_daily` 当前研究范围停采）、2 条虽有权限但不属于安全定时采集、
38 条无权限、1 条继承底层权限、1 条已下线。每个映射项同时显示所需 Tushare 接口和 Token
权限，因此“供应商存在”不会再被误报为“当前可调用”。反向逐条查询使用
`GET /api/v1/data/source-priorities/tushare-endpoints`，可按 `mapping_status`、
`permission` 和 `query` 筛选 244 条 Tushare 契约。

## 安装与启动

```bash
cp .env.example .env
# 编辑 .env，至少填写 TUSHARE_TOKEN
./install.sh
```

常用命令：

```bash
docker compose ps
docker compose logs -f scheduler worker-v2-routine worker-v2-backfill auditor
docker compose up -d
docker compose down
```

PostgreSQL 使用命名 volume，普通容器重建不会删除业务数据。不要运行 `docker compose down -v`，除非明确要销毁数据库。

## 初始化与全量审计

安装后的初始化不是一套独立采集器，而是 V2 的完整复用：

1. 对所有可审计数据集执行严格全历史扫描。
2. 将最新审计中的 missing/partial 分区转换为 V2 repair 实例。
3. Worker 采集并由同一任务的 validate 节点复核。
4. 全部修复终态后再次严格审计。
5. 只有最新证据无缺口时初始化状态才为 ready。

API：

```text
GET  /api/v1/ops/initialization
POST /api/v1/ops/initialization/preflight
POST /api/v1/ops/initialization
GET  /api/v1/ops/initialization/{id}
GET  /api/v1/ops/initialization/{id}/steps
```

初始化、repair 与 backfill 使用 `worker-v2-backfill`，并遵守交易时段暂停策略。例行任务不会被历史任务抢占。

## REST 服务

主要入口：

| 路径 | 说明 |
|---|---|
| `/api/v1/catalog` | 全部公开服务及其本地数据集、上游来源、派生方式和受控回退血缘 |
| `/api/v1/research/*` | 面向 Agent 的基本面、技术面、行业、宏观和跨资产研究数据 |
| `/api/v1/data/*` | 原始/标准化数据查询与数据源入口 |
| `/api/v1/ops/orchestration-v2/*` | V2 定义、执行实例、事件、数据状态和日历 |
| `/api/v1/ops/data-health` | 数据集审计和缺口状态 |
| `/api/v1/ops/initialization/*` | V2 初始化与恢复进度 |
| `/api/v1/investment-calendar/*` | 宏观发布、交割日、公告等投资事件 |
| `/api/docs` | OpenAPI 文档 |
| `/api/v1/system/overview` | 系统全貌、统一数字定义与当前运行摘要 |

Dashboard 的“服务目录”直接读取 `/api/v1/catalog`，可按原始审计层、标准层和研究层
筛选并分页查看来源。研究层的确定性指标只基于本地规范数据集计算；蚂蚁数据源
仅由已经完成字段、代码、日期和单位契约测试的规范接口，在本地目标切片缺失时受控
回退。个股 `fundamentals`、`technicals` 和 `research-pack` 还会在本地确定性计算之后，
按需补充
蚂蚁数据源 的一致预期、评级、目标价、供应商技术指标/形态和实时快照。响应在
`data.provider_evidence` 中保持来源隔离，并通过 `normalized` 提供带版本的稳定研究
契约，不能覆盖本地财务事实或技术计算；单条供应商路由失败只降级该路由，不会丢弃
同批次其他有效证据。历史查询会跳过无法执行 `as_of` 的供应商路由。可用
`include_external=false` 禁用，技术面还可
用 `include_realtime=false` 单独禁用实时快照。

研究 Agent 的外部供给统一放在 `/api/v1/research/*`。通用数据查询不会伪装成研究结论。
研究 Agent 与 Skill 已独立到 claw-quant-agents，包含统一股票研究、基本面和技术面三个
Agent 包；本仓库只维护数据和研究 API。部署与方法规范见
[Agent 与 Skill 架构](https://github.com/Bryanooo/claw-quant-agents/blob/main/docs/AGENT_RESEARCH_SKILL_ARCHITECTURE.md)。

## Dashboard

控制台地址：`http://127.0.0.1:8000/dashboard`

“个股研究”支持按股票代码、名称或拼音简码检索，并在同一页面展示日 / 周 / 月 K 线、
成交量、MACD，以及按频率治理的 SMA、EMA、RSI、ROC、CCI、ATR/NATR 参数族；同时
提供 BIAS、BBI、PPO、TSI、TRIX、Bollinger `%B`/带宽、Keltner、TTM Squeeze、PVT、
VROC、Force Index 和客观价格结构量。日线额外展示20/60日
实际成交成本线、牛门线、确认线与信号 MA10。K 线可用按钮或鼠标滚轮缩放，并通过
区间滑块平移；悬浮会列出当日 OHLC、动态单位成交量及所有已勾选指标值，点击可锁定
该交易日。摘要区同时给出 ATR/波动率、ADX/DMI、Supertrend、MFI/CMF/StochRSI。
打开股票后可加入持久化自选，自选存储在 PostgreSQL 中；点击自选卡片即可快速切换 K 线，
移出自选需要二次确认。
所有图表读取 `/api/v1/research/*` 的统一复权与质量口径，不绕过研究服务直接拼接业务表。

Dashboard 只读取 V2：

- 今日运营：本业务日应执行、已成功、运行中和异常的任务。
- 执行实例：全量 V2 实例和节点事件，可分页、筛选。
- 异常中心：真正未被后续成功覆盖的 V2 attention。
- 数据日历：按**数据日期**展示 `dataset_state`，不是按任务创建日期。
- 初始化：全历史审计、补采和复核阶段。
- 数据源：connector 状态与 acquisition mode。
- 投资日历：按自然日查看重要事件。

查询免密，管理操作使用二次确认。控制台不再依赖 V1 任务记录。

## 备份与恢复

手动备份：

```bash
./scripts/backup.sh
```

恢复演练：

```bash
./scripts/restore.sh backups/claw-quant-YYYYMMDD-HHMMSS.dump \
  --database claw_quant_restore_drill --yes
```

备份包含业务表、V2 五张控制表、审计表、迁移账本和请求级证据。`tushare_raw_record` 是可重建的异常载荷缓存，备份保留表结构但不复制其数据；`tushare_raw_request`、业务表与完成检查点仍完整保留。

恢复脚本只管理 V2 服务。一次备份只有在以下条件全部满足后才可替换上一份已验证备份：

- `pg_restore --list` 可读取；
- 校验侧车匹配；
- 可恢复到临时数据库；
- 业务表、迁移账本和 V2 五张表完成抽样校验。

## 测试

```bash
docker build --target test -t claw-quant-data:test .
docker run --rm claw-quant-data:test \
  python -m pytest -q --ignore=tests/integration

docker run --rm \
  --network claw-quant-data_default \
  --env-file .env \
  -e DB_HOST=postgres \
  -e RUN_DB_INTEGRATION=1 \
  claw-quant-data:test \
  python -m pytest -q tests/integration
```

测试覆盖 V2 合同、调度、节点执行、租约恢复、完整性审计、初始化、Dashboard 契约、多数据源 connector 和真实 PostgreSQL 约束。V1 测试已删除。

## 文档

从[文档目录](docs/README.md)进入。目录按用途和受众区分长期契约、操作说明、机器生成
目录与运行报告，避免把某次验收快照误当成当前系统状态。

## 安全边界

- `.env`、Token、API Key、数据库密码和备份文件不得提交仓库。
- Endpoint 表只保存 `env:VARIABLE_NAME` 形式的凭据引用，不保存密钥值。
- V2 handler 必须来自代码白名单；数据库不会动态执行 Python 源码。
- 审计事件追加不可变；纠错通过 supersede 与新实例完成，不删除历史证据。

公开数据扩展与蚂蚁数据源配置见[数据来源](docs/DATA_SOURCES.md)。
