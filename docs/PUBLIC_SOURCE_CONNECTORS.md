# 公开数据 connector 与蚂蚁数据源

本次新增 5 个来源（巨潮、上证 e 互动、新浪、中债、人民银行），并扩展已有中国货币网，共 8 个按需接口。现有 Tushare 批量采集、LPR 入库和蚂蚁数据源按需链路继续使用原有数据标识。

## 能力目录与查询

- `GET /api/v1/data/sources`：来源列表。
- `GET /api/v1/data/sources/{source_id}/endpoints`：参数 JSON Schema、字段、单位、历史范围声明、时点限制和完整性策略。
- `POST /api/v1/data/sources/{source_id}/endpoints/{endpoint_key}/query`：公开接口查询。
- `GET /api/v1/data/sources/ant_data/route-contracts?route=...`：蚂蚁数据源 163 条已发现路由的入参/输出字段契约。目录快照是 2026-10-16 的发现结果，不代表全部已授权、已适配或实时可用。

| source_id / endpoint_key | 业务内容 | 参数 | 主要限制 |
|---|---|---|---|
| `cninfo/investor_questions` | 深市公司提问、回复、回复方、提问时间 | `code` 必填，`page=1`、`page_size=20` | 只返回指定页；沪市/北交所代码拒绝；不虚构回答时间 |
| `sse/investor_questions` | 沪市问答、ID、提问及回复时间 | `code` 可选，`kind=answered/questions`、`page`、`page_size` | 公司近期窗口，不能视为全部历史；时间保留原文及换算依据 |
| `sina/option_contracts` | ETF 期权合约，按月份、认购/认沽区分 | `underlying=510050/510300/588000/510500`、`side=call/put` | 当前合约，不含到期历史 |
| `sina/option_quote` | T 型报价、买卖盘、持仓、行权价、成交量额等 | 8 位 `code` | 快照；不能凭抓取时间声称交易报价时间 |
| `sina/option_greeks` | Delta、Gamma、Theta、Vega、IV、理论价值等 | 8 位 `code` | IV 按源返回的小数值，不乘除 100；无历史快照保证 |
| `chinabond/yield_curve` | 国债、商业银行 AAA、中短票 AAA，3 月至 30 年期限 | `start`、`end` 必填，`curve=all/treasury/bank_aaa/mtn_aaa` | 单次最多 360 天，长历史显式分段；中短票没有 30 年值 |
| `chinamoney/repo_fixing` | FR001/007/014 或 FDR001/007/014 | `kind=FR/FDR` | 官方滚动 CSV；FR/FDR 不等于 Shibor 或交易所回购 |
| `pboc/social_financing` | 社融总量及人民币贷款、政府债券等 10 个分项，共 12 列含月份 | `year` 必填，2021 年起 | 亿元；只保留已发布月份；旧年份版式不支持；后续修订可能覆盖历史 |

示例：

```bash
curl -sS http://localhost:8000/api/v1/data/sources/chinamoney/endpoints/repo_fixing/query \
  -H 'Content-Type: application/json' \
  -d '{"parameters":{"kind":"FR"},"required_fields":["date","FR007"],"allow_stale":false}'
```

响应为 `data` 行列表和 `meta`。`meta.evidence` 包含实际请求 URL、抓取时间、解析版本、观察到的日期起止和完整性范围。`status=page` 只表示该页通过解析；`observed` 表示此次来源响应通过检查；`empty` 仅在源明确表示无数据时返回。这些状态均不代表全历史完整。

`required_fields` 检查接口在该组参数下支持的字段名，不承诺每行非空（例如中短票 30 年收益率为 null）。FR 与 FDR 字段根据 `kind` 分别检查。参数或字段要求不匹配返回 422；未注册接口返回 404；上游网络/结构错误返回 502；熔断返回 503。可选 `require_point_in_time=true` 要求时点保证；本批公开源都不具备此保证，因此会拒绝。源选择是显式的，不作未证明等价的自动替换。

研究 Agent 使用同一查询实现的研究层入口：
`GET /api/v1/research/public-evidence/capabilities` 及
`POST /api/v1/research/public-evidence/{source_id}/{endpoint_key}`。
请求体相同，响应额外明确 `evidence_only=true`、`canonical=false`、`point_in_time=false`，
遵守现有 Agent 不直接访问 data/ops/audit 命名空间的边界。

## 系统设计

1. **复用服务边界**：所有新增接口注册在 SourceRegistry，经 QueryBroker 进入 TTL 缓存和熔断。缓存最多 1,024 项，TTL 从请求完成时开始计算；参数和能力要求先校验，错误参数不影响上游熔断。公开查询默认不回退到过期缓存；显式允许时标记 `cache=stale`。
2. **请求有界**：每次调用最多 20 个 HTTP 请求、60 秒网络预算、每个响应最多 12 MiB、结果最多 10,000 行；HTTP 连接/读取分别最多 5/15 秒；只允许固定 HTTPS 主机，不跟随重定向。单次阻塞读取可能延迟至读取超时才检查总预算，不声称严格的 60 秒墙钟 SLA。
3. **拒绝静默损失**：严格核对回购 CSV 列布局、问答公司代码、期权字段位置、收益率表头/日期/每个返回日的曲线集合，以及社融列名与月份。HTTP 成功不等于数据成功；验证码/错误页/坏字段不能变成空数据。
4. **区分声明与观测**：`history_declared` 描述已知来源范围；`history_verified=null/false` 表示未做全量验证。单次结果的 `observed_start/end` 只说明这次实际拿到什么，不将单次窗口当作来源总保留期。
5. **时间语义**：抓取时间不是交易、公告或生效时间。上证相对日期优先按 HTTP Date 转上海时区，缺失时按抓取时间换算，并返回依据/原文。蚂蚁研究证据的 `end_date` 过滤不再被标成已证明 `point_in_time_safe`。
6. **审计与许可**：生产注册的 connector 保存脱敏请求元数据、响应摘要/条数；本批不保存原始业务行，不自动建 canonical 数据表或定时回补任务。审计库不可用时保留查询结果并返回 warning；无审计库的直接 connector 测试不等于部署端到端审计验证。
7. **可维护性**：函数移入独立模块，不在运行时执行外部 SKILL.md。适配的解析代码保留 Apache-2.0 许可和来源说明，见 `third_party/a-stock-data/`。

Tushare 已注册接口也暴露原始字段说明、权限和实现状态；蚂蚁统一请求接口指向每条路由的字段契约。没有把“字段目录存在”“有 token”“规范适配器已完成”“历史完整”合并成一个 ready 标记。多源自动择优、长期许可评估、完整交易日审计、时点版本库和新的批量入库仍需后续单独建设。

## 更名兼容

对外名称统一为 **蚂蚁数据源**。推荐使用：

- `ANT_DATA_API_KEY`、`ANT_DATA_BASE_URL`、`ANT_DATA_API_VERSION`、`ANT_DATA_CONNECT_TIMEOUT_SECONDS`、`ANT_DATA_READ_TIMEOUT_SECONDS`。
- `POST /api/v1/data/sources/ant_data/query` 与 `GET /api/v1/data/sources/ant_data/usage`。
- Python 名称 `AntDataConnector`。

新配置优先；旧 `FINANCIAL_DATA_*` 变量继续兼容。数据库、审计记录、source priority 键和响应中的持久标识仍为 `financial_data`，避免迁移造成 lineage 断裂或历史请求重复计数。旧 `/financial_data/query`、`/financial_data/usage` 仍可调用，OpenAPI 标为 deprecated。`ant_data` 的来源和 endpoint 发现入口解析到同一来源，来源列表不会重复计数。

本次没有更换蚂蚁上游服务地址或凭证，没有运行数据库迁移或重启生产服务。新依赖 `xlrd`、`openpyxl` 用于人民银行附件解析；部署时重建镜像以安装依赖，并运行现有 migrate 服务同步来源注册表（否则新来源的审计外键无法满足）。能力元数据以 `request_contract.x-capabilities` 同步到现有控制表，不新增业务数据表或 schema 迁移。

## 验证记录（2026-10-16，上海时间）

真实只读抽样结论如下；一次性原始响应已移出项目归档：

- 深市比亚迪问答：2 条。
- 上证全市场已回复问答：2 条；贵州茅台公司页：源明确返回近期无回复（0 条，不表示所有历史无问答）。
- 50ETF 认购合约：47 条；单合约报价和 Greeks 各 1 条。
- 中债三曲线 2026-10-12 至 2026-10-15：12 条。
- FR：747 条，2023-10-16 至 2026-10-15；FDR：249 条，2025-10-15 至 2026-10-15。这是此次观测范围。
- 人民银行 2025 年社融：12 个月。

上述抽样不构成所有参数、历史年份或交易日完整性认证；各来源的运行时可用性仍由真实查询决定。

最终非集成回归：`pytest -m 'not integration' -q` 为 **580 passed / 9 skipped / 2 failed**。
两项失败均为工作区已有的技能发布一致性问题：
`test_authoritative_skills_are_packaged_by_research_agent`（两个已有新技能未加入测试/发布清单）与
`test_packaged_skill_resources_are_complete_and_local`（stock-review-cadence 的引用文档与发布副本不同步）。
本次保留这些已有修改，没有为消除测试失败覆盖它们。新增连接器、研究入口、更名兼容和现有数据源专项测试通过。
`node --check service/dashboard/dashboard.js`、`docker compose config --quiet`、`git diff --check` 通过。
PostgreSQL 真实审计写入与生产重建/迁移同步尚未执行。
