# claw-quant-data

`claw-quant-data` 是面向个人与研究 Agent 的金融数据底座。系统负责多数据源接入、业务表落库、严格完整性审计、缺口恢复和研究层 REST/CLI 服务；因子组合、策略回测与投研工作流应建立在它之上，而不是混入采集控制面。

自 **2026-09-29** 起，Tushare 的日常采集、初始化、历史补采、数据校验和 Dashboard 全部由 V2 编排执行。V1 控制表、运行服务、路由和测试已经退出。

## 当前组成

- PostgreSQL：业务数据、审计证据和 V2 控制面，使用 Docker volume 持久化。
- API/Dashboard：`http://127.0.0.1:8000/dashboard`，所有 REST 路由位于 `/api/*`。
- Scheduler：只负责按日、周、月、季度创建 V2 执行实例，不直接访问上游。
- V2 routine workers：执行实时/例行任务。
- V2 backfill workers：执行初始化、补采和修复；A 股交易时段自动暂停历史负载。
- Auditor：对业务数据独立审计，任务成功不等于数据就绪。
- Backup：定时产生 PostgreSQL custom-format 备份及校验侧车文件。

系统当前拥有 201 个 Tushare 接口契约。它们映射为 191 个原生采集任务和 194 个可审计数据集；数字不相等是因为一个任务可以组合多个上游接口，也可以产出多个数据集。另有 14 个派生任务定义，其中已具备业务实现的版本才允许发布为 active。

## V2 执行模型

一个执行实例只对应一个业务逻辑周期，例如一个交易日、自然月或报告期。分页、股票/基金/指数枚举、市场分区都在该实例的 `acquire` 节点内穷举，不会制造叶任务。

固定节点为：

1. `condition`：判断该周期是否应执行。
2. `scope_plan`：冻结业务范围、参数和幂等身份。
3. `acquire`：穷举分页、分区和依赖实体并落库。
4. `validate`：使用独立审计代码核验业务表及传输证据。
5. `publish`：只有严格验证通过才发布 ready 状态。

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

### Financial Data MCP

系统已新增 `financial_data` connector，对接财跃星辰金融数据 MCP 的 `common_query` 接口：

```env
FINANCIAL_DATA_API_KEY=
FINANCIAL_DATA_BASE_URL=https://dfdatamcpnexus-prod.antgroup-inc.cn/api/v1/common_query
FINANCIAL_DATA_API_VERSION=1.6.0
```

调用入口：

```text
POST /api/v1/data/sources/financial_data/query
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
才能进入规范模型。当前 Financial Data 已完成连接与协议校验，但尚未完成 163
条路由到全部规范数据集的逐项映射，因此它现在不能被宣称为 Tushare 的无差别
替代源。目前已通过契约测试的有限回退包括 A 股日线/交易日历、证券身份/日度估值、
累计利润表/现金流量表/资产负债表、财务指标、滚动十二月财务、业绩预告/快报、分红、回购、股东户数、
主营构成、主要股东、解禁、质押、风险警示和停复牌，
以及基金档案、基金净值、基金股票持仓、基金分红、基金经理、指数档案和指数成分权重；
其余路由仍需逐项完成字段、日期、单位与代码适配。

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
| `/api/v1/research/*` | 面向 Agent 的基本面、技术面、行业、宏观和跨资产研究数据 |
| `/api/v1/data/*` | 原始/标准化数据查询与数据源入口 |
| `/api/v1/ops/orchestration-v2/*` | V2 定义、执行实例、事件、数据状态和日历 |
| `/api/v1/ops/data-health` | 数据集审计和缺口状态 |
| `/api/v1/ops/initialization/*` | V2 初始化与恢复进度 |
| `/api/v1/investment-calendar/*` | 宏观发布、交割日、公告等投资事件 |
| `/api/docs` | OpenAPI 文档 |

研究 Agent 的外部供给统一放在 `/api/v1/research/*`。通用数据查询不会伪装成研究结论。

## Dashboard

控制台地址：`http://127.0.0.1:8000/dashboard`

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

- [V2 切换与运维](docs/V2_CUTOVER_2026-09-29.md)
- [V2 工作流模型](docs/COLLECTION_EXECUTION_MODEL.md)
- [数据审计](docs/DATA_ASSURANCE.md)
- [最新全量数据审计报告](reports/dataset_audit_latest.md)
- [多数据源架构](docs/MULTI_SOURCE_ARCHITECTURE.md)
- [研究 API](docs/RESEARCH_API.md)
- [CLI](docs/CLI.md)
- [文档导航](docs/README.md)

## 安全边界

- `.env`、Token、API Key、数据库密码和备份文件不得提交仓库。
- Endpoint 表只保存 `env:VARIABLE_NAME` 形式的凭据引用，不保存密钥值。
- V2 handler 必须来自代码白名单；数据库不会动态执行 Python 源码。
- 审计事件追加不可变；纠错通过 supersede 与新实例完成，不删除历史证据。
