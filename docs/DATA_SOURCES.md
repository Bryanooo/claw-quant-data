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

对外名称统一为“蚂蚁数据源”，推荐使用 `ANT_DATA_*` 环境变量和 `/ant_data/*` 路径。
数据库、历史审计和部分持久标识继续使用 `financial_data`，避免血缘断裂；旧配置和路径
仅作为 deprecated 兼容入口。

## 原始证据与缓存

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
