# 数据来源

## 来源模型

所有来源统一注册为 `SourceSpec + EndpointSpec`：

- `SourceSpec`：来源身份、采集模式、授权和保留政策；
- `EndpointSpec`：业务能力、参数 JSON Schema、输出字段、分页、时间和完整性约束；
- Connector：只负责协议、限流、超时、解析和来源证据；
- 规范适配器：统一代码、日期、单位、字段和时点语义；
- 研究服务：只消费规范数据或明确标记的外部证据。

支持定时拉取、网页/文件解析、按需查询和未来流式接入。当前生产以定时拉取和按需查询
为主；尚无生产消费者的模式不能被描述为已完成能力。

## 本地优先与回退

1. 先读已经入库并审计通过的本地规范数据；
2. 仅当请求切片明确缺失、调用方允许且适配器通过契约测试时，才使用额度源回退；
3. 回退只补缺失切片，不能覆盖同日期本地记录；
4. 未完成代码、日期、单位和字段适配的供应商 JSON 只能作为诊断或研究证据；
5. 响应必须披露 `served_from`、`read_strategy`、`fallback_used` 和未解决范围。

完整优先级和等价性查询：

```text
GET /api/v1/data/source-priorities
GET /api/v1/data/source-priorities/tushare-endpoints
```

能力存在、当前 Token 可用、规范适配器就绪和数据历史完整是四个独立状态。

## 来源发现与查询

```text
GET  /api/v1/data/sources
GET  /api/v1/data/sources/{source_id}/endpoints
POST /api/v1/data/sources/{source_id}/endpoints/{endpoint_key}/query
GET  /api/v1/data/sources/ant_data/route-contracts
GET  /api/v1/data/sources/ant_data/usage
```

按需 Connector 只允许固定 HTTPS 主机、结构化参数、响应大小和请求预算，不接受任意 URL。
响应区分 `observed`、`empty`、`page`、协议错误和上游不可用；HTTP 200 不等于数据成功。
抓取时间也不能冒充交易、公告或生效时间。

## 已注册来源

| 来源 | 主要用途 | 模式与限制 |
|---|---|---|
| Tushare | 主体、行情、财务、资金、宏观等批量历史与日常数据 | 定时落库，权限和额度按 Endpoint 管理 |
| 蚂蚁数据源 | 实时/补充能力和本地缺失切片的受控回退 | 按需、消耗额度；只有规范适配器可进入统一模型 |
| 巨潮、上证 e 互动 | 公司问答等公开证据 | 网页/接口窗口有限，不声明全历史 |
| 新浪 | ETF 期权合约、报价和 Greeks | 当前快照，不保证历史时点 |
| 中债 | 国债、银行和中票收益率曲线 | 按时间窗口查询，长历史显式分段 |
| 中国货币网 | FR/FDR 回购定盘利率 | 官方滚动数据；不等同于 Shibor |
| 人民银行 | 社会融资规模等官方附件 | 解析已支持版式，保留发布与解析证据 |

每个来源当前有多少 Endpoint、字段和可用范围，以来源目录为准。公开来源返回的是证据，
未形成规范模型时 `canonical=false`，Agent 通过
`/api/v1/research/public-evidence/*` 使用，不直接访问 data/ops/audit 命名空间。

## 数据资产怎么分类

数据集有两个相互独立的分类轴。第一轴是资产：股票、ETF/基金、指数、债券、期货等；
第二轴是生产方式：供应商原文、标准化供应商数据、规范融合数据、Claw 派生数据和研究
结果。不能看到“因子”“复权”“筹码”就一律称为 Claw 派生：供应商可以直接提供其
算法结果，Claw 只是无损采集并标准化。

当前 `GET /api/v1/data/datasets` 登记 197 个标准数据集。目录表示可查询契约，不表示每个
数据集都已达到相同历史完整度；实际行数、最新日期与状态应同时查询
`GET /api/v1/data/freshness` 和 `GET /api/v1/ops/data-health`。

### 股票相关

| 用途 | 主要数据集 | 性质 |
|---|---|---|
| 身份与交易制度 | `stock_basic`、`stock_company`、`bse_mapping`、`namechange`、`trade_calendar` | 供应商原生事实的标准化记录 |
| 日线与交易状态 | `stock_daily`、`bak_daily`、`bak_basic`、`daily_basic`、`stock_daily_basic`、`adj_factor`、`stock_limit`、`stock_suspend`、`stock_st`、`stk_weekly_monthly`、`stk_mins`、`stk_auction`、`stk_auction_o`、`stk_auction_c` | 供应商行情、状态及供应商计算指标 |
| 财务与业绩 | `income`、`balancesheet`、`cashflow`、`financial_indicator`、`forecast`、`express`、`fina_audit`、`fina_mainbz`、`disclosure_date`、`report_rc` | 报表、披露和分析师事件；时点研究必须使用公告可见时间 |
| 公司行为与股东 | `dividend`、`repurchase`、`share_float`、`new_share`、`pledge_detail`、`pledge_stat`、`top10_holders`、`top10_floatholders`、`stk_holdernumber`、`stk_holdertrade`、`stk_managers`、`stk_rewards` | 供应商事件数据，空行不自动代表事件不存在 |
| 资金与交易行为 | `moneyflow`、`margin`、`margin_detail`、`margin_secs`、`hk_hold`、`stock_hsgt`、`hsgt_top10`、`ggt_top10`、`block_trade`、`top_list`、`top_inst` | 供应商原生或供应商汇总指标 |
| 热度、板块与涨停生态 | `limit_list_d`、`limit_list_ths`、`limit_step`、`limit_cpt_list`、`ths_hot`、`dc_hot`、`hm_list`、`kpl_list`、`dc_concept`、`dc_concept_cons`、`kpl_concept_cons` | 供应商榜单、事件和分类结果 |
| 筹码与技术描述 | `cyq_chips`、`cyq_perf`、`stk_factor`、`stk_factor_pro`、`factor_value` | 供应商计算后提供的指标，不是 Claw 从逐笔成交还原的原始事实 |
| Claw 持久化派生 | `fama_french_daily`、`technical_factor_snapshot` | Claw 使用已入库数据确定性计算，保存公式版本和输入血缘 |

`daily_basic` 是契约通用标准表，`stock_daily_basic` 是平台核心股票每日基本面模型；二者
都包含估值、换手、股本和市值类字段，使用方应按数据契约选择，不应在同一计算中无说明
地混用。指数行情、指数权重和成分历史也经常作为股票因子基准或股票池依据，列在后面的
跨资产公共数据中。

### ETF 与公募基金相关

| 用途 | 主要数据集 | 性质 |
|---|---|---|
| ETF 身份与跟踪关系 | `etf_basic`、`etf_index` | 供应商原生主数据 |
| ETF 交易行情 | `fund_daily`、`fund_adj` | 供应商行情及供应商复权因子；复权因子不等于已验收总回报 |
| 份额、规模与申赎篮子 | `etf_share_size`、`etf_sh_cons`、`etf_sz_cons` | 供应商披露数据 |
| 基金通用资料 | `fund_basic`、`fund_company`、`fund_manager`、`fund_nav`、`fund_share`、`fund_portfolio`、`fund_div`、`fund_factor_pro`、`mkt_idx_bmk` | ETF 与场外公募基金共享；不能默认所有记录都是 ETF |
| 指数和交易支持 | `index_daily`、`index_weight`、`idx_anns`、`trade_calendar`、`stock_limit`、`stock_suspend` | ETF 基准、日历和交易状态的辅助来源；部分接口名称保留供应商命名 |
| Claw ETF 日级事实 | `/api/v1/data/etf-rotation/daily-facts` | Claw 派生接口：核验分红与份额事件，计算总回报、规则涨跌停和日级交易状态 |

ETF 日级事实目前只对经过审查的 12 只 ETF 和已声明日期范围负责。它不是供应商原表，
也不应被描述为盘口或逐笔成交数据。

### 跨资产公共数据与其他资产

| 类别 | 代表数据集 | 当前目录规模 |
|---|---|---:|
| 指数与行业 | `index_basic`、`index_daily`、`index_weekly`、`index_monthly`、`index_weight`、`index_classify`、`index_member_all`、`ci_daily`、`sw_daily`、`industry_daily` | 13 |
| 债券与可转债 | `cb_basic`、`cb_daily`、`cb_factor_pro`、`cb_call`、`cb_issue`、`cb_rating`、`repo_daily`、`bond_blk` | 15 |
| 期货 | `fut_basic`、`fut_daily`、`fut_settle`、`fut_holding`、`fut_mapping`、`fut_wsr`、`ft_limit` | 11 |
| 期权 | `opt_basic`、`opt_daily` | 2 |
| 港股 | `hk_basic`、`hk_daily`、`hk_tradecal`、`rt_hk_k` | 4 |
| 美股 | `us_basic`、`us_tradecal`；`us_daily` 仅保留存量查询，当前停采 | 3 |
| 黄金与商品 | `sge_basic`、`sge_daily` | 2 |
| 外汇 | `forex_daily`、`fx_obasic` | 2 |
| 宏观与利率 | `cn_cpi`、`cn_gdp`、`cn_m`、`cn_pmi`、`cn_ppi`、`cn_lpr`、`shibor`、`hibor`、`libor`、国债利率和社融月度数据 | 19 |
| 新闻与自选组合 | `major_news`、`p_get`、`p_list` | 3 |

这些数量按目录的主要分类统计，公募基金与 ETF、指数与股票研究之间存在共享关系，不能
把分类数量相加后当作互斥资产总数。

### 原生、标准化和派生的准确含义

| 层级 | 含义 | 例子 |
|---|---|---|
| 原始证据 | 供应商响应及请求身份，保留原文字段和传输证据 | `tushare_raw_request`、异常/审计需要时的 `tushare_raw_record` |
| 标准化供应商数据 | 字段、代码、日期和类型已经统一，但业务值主要来自供应商 | `stock_daily`、`fund_daily`、`income`、`cyq_perf` |
| 供应商派生指标 | 算法由供应商或其社区执行，Claw 接收结果 | `cyq_perf`、`cyq_chips`、`adj_factor`、`fund_adj`、`stk_factor_pro` |
| 规范融合数据 | 本地规范库优先，对明确缺失切片做受控回退，并披露来源 | `/api/v1/data/canonical/*` |
| Claw 持久化派生 | Claw 读取已发布输入并按版本化公式生成新表 | `fama_french_daily`、`technical_factor_snapshot` |
| Claw 即时派生 | 请求时计算并返回，不冒充供应商原始记录 | ETF `daily-facts`、TTM 财务、研究 API 的技术面、事件研究、市场宽度等 |

### `cyq_perf` 是什么

`cyq_perf` 是 Tushare 社区提供的 A 股“每日筹码成本摘要”，从 2018 年开始，通常在交易日
18—19 点更新。每行对应一只股票和一个交易日，字段包括历史最低/最高价、5%、15%、
50%、85%、95% 成本分位、加权平均成本和 `winner_rate`。`cyq_chips` 则保留同日各价格
档位及其占比，粒度更细。

筹码分布使用价格、成交量、换手和历史筹码衰减模型估算。它不是登记结算系统披露的真实
持仓成本，也不是逐个投资者账户数据。因此 `cyq_perf` 在生产归属上是“供应商原生输入”，
在经济含义上却是“供应商派生指标”。它适合构造获利盘比例、成本中枢、筹码集中度和价格
偏离成本等因子，但必须先做覆盖率、稳定性和未来收益检验，不能直接当成买卖信号。

factor-lab 的 `flow_sentiment@v1` 把它作为可选因子包中的必需成员：不用该因子包时不会
阻塞核心行情数据集；选择该因子包时，缺失记录必须明确处理。采集按“每只股票一次请求、
请求内覆盖一段日期”执行，并受每日额度保护，不能拆成股票×交易日调用。

## 蚂蚁数据源命名

### 调用预算与盘中储备（2026-10-31）

真实 HTTP 发送前按 `requests` 数量在 PostgreSQL 原子预占，滚动7天硬上限1000。
供应商周重置时区尚未确认，滚动窗口是保守保护，不等同供应商账单周期。
既有查询审计已导入；失败、超时占用不退回。定时采集旧审计不完整，导入量不是完整历史账单。
遇到供应商 `QUOTA_EXCEEDED` 全入口熔断7天；确认正式恢复时间后才能调整，不反复探测。

当前分类上限：盘中245、每日榜单10、每周全市场224、四周轮换100、研究150、历史重放0。
合计729，剩余271专留未来盘中监测扩容；任何类别不能自动借用储备或其他类别余量。
盘中观察当前按5分钟调度，每轮行情/分钟K/资金流，行业目录按日共享缓存；
原盘中245子请求预算仍然有效，实际轮次受请求预算与缓存命中限制，不承诺整周每轮均能发送。
自选扩容增加K线分批请求时仍受盘中245限制，需显式重新分配储备后才能增加发送量。
停复牌不再穿透蚂蚁，以本地 Tushare 为准；本地无记录不等于已证实未停牌。

控制人、控股股东、风格分类每周获取稳定哈希划分的1/4证券，四周轮换覆盖全体，
不是每周全市场完成。股本结构、自由流通股本保留每周全市场。
定时请求同周期共享缓存并合并并发请求，重试可复用已成功批次。
缓存只缓存成功协议结果；缺响应/失败子请求不能算采集完成。
请求计量 `ant_request_budget` 与短期响应缓存 `ant_query_cache` 分开，
`/api/v1/data/sources/ant_data/usage` 的 `budget` 展示分类预算和扩容储备。

对外名称统一为“蚂蚁数据源”，推荐使用 `ANT_DATA_*` 环境变量和 `/ant_data/*` 路径。
数据库、历史审计和部分持久标识继续使用 `financial_data`，避免血缘断裂；旧配置和路径
仅作为 deprecated 兼容入口。

## 原始证据与缓存

调度器每天03:20（Asia/Shanghai）有界清理已过期的 `ant_query_cache`、超过14天的
`ant_scheduled_checkpoint` 和超过7天的进程心跳。每表每次最多删除10,000条；锁等待及
语句时间均受限。请求额度账本、原始请求、任务回执、审计记录和业务数据不属于此清理范围。
仓库状态清单使用稳定的 `*_latest` 文件及生成时间；历史验收依据明确标记为 reference，
旧日期快照存于 Git 历史或主机归档，不作为当前状态入口。

### 蚂蚁在用路由的历史查询能力（2026-10-31 核对）

范围为当前7个定时路由和4个盘中使用路由，不是供应商全部接口。依据
[`route-contracts.json`](ant_data/route-contracts.json)（2026-10-16 发现契约）和
[`ant_scheduled.py`](../service/source_connectors/ant_scheduled.py)、
[`collector.py`](../service/intraday/collector.py)。本轮未发送供应商请求、未补采；
下列是契约能力核对，不代表实时可用性、历史保留年限或历史完整性已实测通过。

| 路由（省略 `/api/v1/`） | 历史能力分类 | 日期参数及限制 |
|---|---|---|
| `quote/kline-batch` | 明确支持范围历史 | `start_date/end_date`；最多10个标的；有跨度和 `count` 限制，须分窗 |
| `quote/capital-flow-range` | 明确支持范围历史 | `start_date/end_date`；单标的，默认最多200条；契约明确日/周/月，未说明保留边界 |
| `stock_fnd/free-float` | 明确支持范围历史 | 按调整日期过滤；不传日期仅最新调整日期集合，不是全部变动史 |
| `stock_fnd/style-classification` | 明确支持范围历史 | 按截止日期过滤；不传日期仅最新截止日期集合 |
| `altdata/hot-stock-rank` | 当前榜单，无历史日期入口 | 最多200名；过去排名不能通过当前榜单恢复 |
| `altdata/hot-plate-rank` | 当前榜单，无历史日期入口 | 近月涨幅/近周资金字段是回溯指标，不是过去某天榜单 |
| `quote/basic-snapshot` | 当前行情快照 | 只有标的和字段参数，无历史时点参数 |
| `stock_fnd/equity-structure` | 最新股本结构快照 | 契约明确最新，无日期参数 |
| `sector/plate-list` | 当前目录，无历史日期入口 | 按行业/地域/概念分类查询，不等于历史板块或历史成分 |
| `stock_fnd/actual-controller` | 历史返回范围未确认 | 无日期参数；响应有 `end_date`，不足以证明返回全部历任控制人 |
| `stock_fnd/controlling-shareholder` | 历史返回范围未确认 | 无日期参数；响应有 `end_date`，不足以证明返回全部历任控股股东 |

结论：4个明确支持历史范围、5个当前快照/目录、2个历史返回范围待确认；
**没有一个已确认能够一次无截断返回全部历史**。无分页参数也不能证明结果不受行数限制。
K线单次自然日跨度：1分钟2天、5分钟7天、15分钟20天、30分钟40天、60分钟90天、
日线365天、周线1460天、月线3650天；还须校验 `count`，窗口上限不等于历史保留期限。

当前定时采集仅给证券类路由传 `symbols`，因此自由流通股本和风格分类尚未按历史范围查询。
任务及数据目录已改为“最新调整日快照”，风格分类明确“最新快照，每周1/4轮换”，不再暗示完整历史。
盘中代码向资金流接口传 `P_Min1`，但发现契约只列日/周/月，分钟级支持及跨度须保留为
契约差异待核实，不能直接套用K线限制。港股专用 `hk_stock/equity-structure`、
`hk_stock/free-float` 及美股专用 `us_stock/equity-structure` 虽支持日期范围，
也不能把这些不同路由的能力套到当前 `stock_fnd/equity-structure`。

后续如授权能力探测，先核实控制人/控股股东历史范围、资金流分钟契约及事件接口截断规则；
历史预算目前仍为0，不自动探测或补采。历史事件日期与公告可见时间须分别审计，
禁止把本次获取的历史记录直接当作当时已知的信息。

#### Tushare 替代与候选补采评估（2026-10-31，不执行）

| 需求 | Tushare 覆盖判断 | 蚂蚁历史处理建议 |
|---|---|---|
| A股每日自由流通股本数值 | `daily_basic.free_share`，万股；支持起止日期。可满足这一研究需求，但跨供应商数值口径尚未验证等价 | 优先本地Tushare，不重复拉取蚂蚁全市场历史 |
| 自由流通股本变动原因、非自由流通股股东类别拆分、归档值 | 上述每日指标不提供这些字段；不能靠数值差分还原原因，也不能以解禁计划代替实际变动 | 仅对明确需要事件解释的研究证券评估 |
| 蚂蚁规模/成长价值标签、得分及分类阈值历史 | 已核对的Tushare契约未发现同口径直接替代。市值、估值、财务指标可支持自定义风格，但不是蚂蚁标签 | 若确需供应商原标签历史，单独评估，不默认全市场十年 |

依据：[Tushare 每日指标官方契约](https://tushare.pro/document/2?doc_id=32)及本地Tushare/蚂蚁契约。
本地 `tushare_norm_daily_basic` 抽查：2026-10-08共5557行、2026-10-30共5571行，
两日 `free_share` 均全非空；这只是字段可用性抽查，不代表全历史证券覆盖验收。
日值按万股转换为股需要乘10000；蚂蚁该字段契约未明示单位，跨源合并前须核验，不能盲目等同。

候选范围优先为明确研究证券（例如50或200只）、最近12个月，按季度窗口读取事件记录，
不按股票×交易日逐日请求。不确定事件频率、返回上限与分页能力时，不承诺一年一次请求即可完整。
按现有50只/子请求批量配置估算：`ceil(证券数/50) × 日期窗口数 × 接口数`。
两接口、4个季度窗口：50只约8次，200只约32次；当前5577只上市股票约896次。
这不是实测报价或完整性保证，尚不含探测、截断拆分及失败费用；50只历史批量能力也需验证。
十年40窗口同范围约8960次，且仅当前上市股票会遗漏历史退市证券，不能称为全市场十年覆盖。
如果只补风格一个接口，上述基础估算减半；优先不为自由股本日值花蚂蚁额度。
历史预算保持0，不调整当前日常预算、不占用未来盘中预留271次，不创建补采实例。
确认实际需求、批量/截断规则和可分配预算后，才能给出正式补采计划与完成时间。

- Tushare 保存请求级证据；异常时保存逐行原文。
- 查询穿透来源保存脱敏请求元数据、状态、行数和响应哈希，不默认持久化供应商业务行。
- 缓存键包含来源、Endpoint、规范化参数和能力要求；TTL 从请求完成时计算。
- 默认不回退过期缓存；显式允许时响应标记 `cache=stale`。
- 审计不可用会返回 warning，不能把无审计的单元测试当作端到端验证。

## 未知历史边界

本地首条数据之前存在候选日期，不自动等于缺失。对经评审的稠密序列，可以由近及远
建立受控探测实例：只有请求成功、分页耗尽且审计确认零行，才能记录
`verified_empty`；连续空窗只能形成 provisional boundary。财报、成分变更和事件型
数据不适用空窗推断，必须依赖契约、实体范围或官方证据。

## 新增来源流程

1. 定义 Source/Endpoint 契约、授权、时区和保留政策；
2. 实现有界 Connector，不接受任意 URL；
3. 保存请求/工件证据，再实现规范映射；
4. 测试分页、空数据、漂移、缓存、熔断、幂等和失败分类；
5. 增加覆盖规则与更新周期后才允许自动调度；
6. 最后让研究层消费规范数据，客户端不依赖供应商字段。

机器目录见 [Tushare 接口索引](tushare/README.md)、
[Tushare 标准表契约](tushare/tables/README.md) 和
[蚂蚁数据源路由契约](ant_data/route-contracts.json)。


## A股日频采集范围（2026-11）

自动采集以 A 股日频量化为目标。港股/美股证券及独立行情、期货、期权、柜台与普通债券大宗交易、LIBOR 和地方民间利率停止新增自动采集。既有业务表、历史版本及本地查询全部保留。`DEFERRED_RESEARCH_DATASETS` 同时约束日常调度、周参考刷新、初始化/恢复计划和 worker 领取；待运行实例按策略作废并追加审计事件。

保留 A 股及 ETF、可转债、沪深港通、基金持仓、国内宏观利率与汇率背景。外汇增量只采 `USDCNH.FXCM`、`USDOLLAR.FXCM`，单实例窗口最多 31 天；既有其他外汇/CFD 数据继续可查。空响应不代表已取得最新价格。

新增 `stk_seasoned`：Tushare 增发事件，保留官方 69 个字段及不同 payload 版本，包含预案、审批、实际发行及募集费用等。按公告日采集，不把公告日视为实际实施日。供应商未提供稳定项目 ID，按 payload 身份保留不同项目/版本，不把同一股票的多条增发事件合并。官方契约：https://tushare.pro/document/2?doc_id=494 。

新增 `stock_announcements`：巨潮公开公告目录，按沪、深、北交易所和完整自然日分页，保存代码、公告身份、标题、发布时间、PDF 地址、首次观察和最近观察时间。逐页核对总数、日期、交易所及唯一身份；合并列表及时间排序实测存在分页重叠，不能用于完整性认证。这里只证明公开目录在指定范围内已耗尽，不保证监管意义上的所有披露。Tushare `anns_d` 当前令牌无权限，未宣称可用。

公告与增发每日回看最近 7 个已结束自然日，包含周末；更早历史须明确日期、有界回填。公告 PDF/文本只在调用正文接口时下载，不批量落库、不生成持久正文缓存。扫描件不自动 OCR。首次观察时间参与回测知识边界；后来补入的公告不会自动成为历史上已经知道的事件。
