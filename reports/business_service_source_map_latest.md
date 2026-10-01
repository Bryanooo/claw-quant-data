# Claw Data 业务服务与数据源映射

## 口径

- 业务与研究命名空间共 52 个：24 个规范数据服务、25 个返回研究数据/分析结果的服务、3 个研究发现与质量元数据服务。
- 辅助数据入口共 12 个：6 个通用数据集入口、5 个 Tushare 审计入口、1 个 Financial Data 查询网关。
- 因此数据相关公开 HTTP 入口共 64 个。
- 研究服务只读取本地数据库，不在研究请求中直接消费 Financial Data 额度。
- 规范数据服务先读取本地已审计数据；只有明确缺失且调用方允许时，才使用列出的 Financial Data 路由补足缺口。

## 规范数据服务（24）

| 服务 | 本地数据集与原始来源 | Financial Data 回退 | Claw 处理 |
|---|---|---|---|
| `market-bars` A股日线 | `stock_daily`，Tushare `daily` | `quote/kline-batch` | 统一代码、日期、价格和成交量字段 |
| `trading-sessions` 交易日历 | `trade_calendar`，Tushare `trade_cal` | `common/trading-day` | 统一交易所开闭市状态 |
| `equity-profiles` 股票档案 | `stock_basic`，Tushare `stock_basic` | `stock_fnd/stock-basic-info` | 统一股票身份、市场和行业字段 |
| `equity-valuations` 股票估值 | `stock_daily_basic`，Tushare `daily_basic` | `stock/daily-valuation-indicators` | 统一 PE、PB、PS、股息率、市值单位 |
| `equity-financial-periods` 三张财务报表 | `income`、`balancesheet`、`cashflow`，Tushare 同名接口 | `income-cashflow-acc`、`balance-sheet` | 按报告期组装三表并保留披露日 |
| `equity-performance-updates` 业绩预告/快报 | `forecast`、`express`，Tushare | `performance-forecast`、`prelim-acc` | 合并预告与快报并统一报告期 |
| `equity-financial-metrics` 财务指标 | `financial_indicator`，Tushare `fina_indicator` | `growth-rates-acc` | 统一盈利、成长、偿债和营运指标 |
| `equity-ttm-financials` TTM财务 | `income`、`cashflow`，Tushare | `metrics-ttm` | Claw 从累计报表派生滚动十二月 |
| `equity-dividends` 股票分红 | `dividend`，Tushare | `dividend-details` | 统一每股分红和关键日期 |
| `equity-repurchases` 股票回购 | `repurchase`，Tushare | `buyback-plans` | 统一计划、执行金额、数量和价格 |
| `equity-holder-counts` 股东户数 | `stk_holdernumber`，Tushare | `holder-count` | 统一观察日、披露日和户数变化 |
| `equity-business-segments` 主营构成 | `fina_mainbz`，Tushare | `main-business-business/industry/product/region` | 统一业务、行业、产品、地区及占比 |
| `equity-shareholders` 前十大股东 | `top10_holders`、`top10_floatholders`，Tushare | `shareholder-list` | 合并总股东与流通股东口径 |
| `equity-restricted-releases` 限售解禁 | `share_float`，Tushare | `restricted-release-calendar` | 统一解禁日期、数量和比例 |
| `equity-pledges` 股权质押 | `pledge_detail`，Tushare | `freeze-pledge` | 统一质押、冻结和解除事件 |
| `equity-risk-alerts` 风险警示 | `stk_alert`、`stock_st`，Tushare | `stock/risk-alerts` | 合并 ST、退市等风险状态 |
| `equity-suspensions` 停复牌 | `stock_suspend`，Tushare `suspend_d` | `stock/suspend-resumption` | 统一停牌时段、原因和复牌信息 |
| `fund-profiles` 基金档案 | `fund_basic`，Tushare | `fund/fund-archive` | 统一基金身份、费用率和申购门槛 |
| `fund-nav` 基金净值 | `fund_nav`，Tushare | `fund/net-value` | 统一单位净值、累计净值和收益率 |
| `fund-stock-holdings` 基金股票持仓 | `fund_portfolio`，Tushare | `fund/stock-portfolio` | 按基金和季度统一持仓 |
| `fund-dividends` 基金分红 | `fund_div`，Tushare | `fund/dividend` | 统一每份现金分红和派息日期 |
| `fund-managers` 基金经理 | `fund_manager`，Tushare | `fund/fund-manager` | 统一任职区间、任期回报和履历 |
| `index-profiles` 指数档案 | `index_basic`，Tushare | `index-profile-basic-info` | 统一指数身份、基日、基点和币种 |
| `index-constituents` 指数成分权重 | `index_weight`，Tushare | `index-constituents-list-weight` | 按更新日期统一成分与权重 |

## 研究聚合服务（28）

以下服务均由 Claw 读取本地 PostgreSQL 后组装或计算，不直接调用 Financial Data。

| 服务 | 主要本地数据集 | Claw 提供的结果 |
|---|---|---|
| `capabilities` | 静态能力目录 | 可用研究能力和待办缺口 |
| `readiness` | V2执行状态、覆盖审计、时效状态 | 研究能力是否真正可用 |
| `validation-set` | 静态验收目录 | 端到端研究验证案例 |
| 股票基本面 | `stock_basic`、`financial_indicator`、`income`、`balancesheet`、`cashflow`、`fina_mainbz` | 财务趋势、杜邦、现金质量、偿债、营运、主营构成 |
| 股票估值 | `stock_basic`、`stock_daily_basic`、`financial_indicator`、`ths_member`、`dc_member` | 估值历史分位、同行比较、DCF/DDM输入 |
| 股票技术面 | `stock_daily`、`adj_factor`、`stock_daily_basic`、`index_daily` | K线、日周月年周期、趋势、动量、量价、枢轴、波浪、缠论、风险 |
| 股票资金与筹码 | `moneyflow`、`margin_detail`、`hk_hold`、`block_trade`、`cyq_perf` | 主力资金、两融、北向、大宗、筹码状态 |
| 股票回购进展 | `repurchase`、`stock_daily`、`index_daily` | 回购执行率、均价及公告后表现 |
| 多资产技术面 | 股票/指数/ETF/板块/黄金对应行情、复权和基准数据集 | 同一套多周期技术分析模型 |
| 事件研究 | `stock_daily`、`index_daily` | 事件窗口收益与累计异常收益 |
| 市场宽度 | `stock_daily`、`limit_list_d` | 涨跌分布、均线扩散、涨跌停情绪 |
| 宏观状态 | `cn_gdp`、`cn_pmi`、`cn_cpi`、`cn_ppi`、`cn_m`、`sf_month`、`shibor`、`shibor_lpr` | 增长、通胀、流动性状态；LPR为中国货币网+Tushare |
| 宏观主题序列 | 同上 | 增长、通胀或流动性的有界历史序列 |
| ETF资金流 | `etf_share_size`、`etf_basic`、`fund_basic`、`index_daily` | 份额申赎、估算资金流和市场表现 |
| 国家队ETF信号 | 同ETF资金流 | 市场流量/疑似/确认三级证据，禁止无持有人证据的确认归因 |
| 板块轮动 | `industry_daily`、`dc_daily`、`tdx_daily` | 多窗口收益和成交活跃度排名 |
| 行业基本面 | `income`、`cashflow`、`financial_indicator`、`stock_daily_basic`及板块成员表 | 行业财务、估值、同比和贡献公司 |
| 行业内部宽度 | `stock_daily`及THS/DC/TDX成员表 | 行业成分涨跌和均线扩散 |
| 个股快照 | `stock_basic`、`stock_daily`、`stock_daily_basic`、`moneyflow`、`financial_indicator`、`stock_limit`、`stock_suspend` | 最新身份、行情、估值、资金、财务与交易状态 |
| 个股研究包 | 股票行情、复权、资金、财务、股东、质押、回购、分红、新闻及基准共20余数据集 | 时点安全的完整研究上下文，不直接给交易建议 |
| 股票所属板块 | `ths_index/member`、`dc_index/member`、`tdx_index/member` | 股票的行业、概念、主题归属 |
| 同行发现 | THS/DC/TDX板块目录与成员表 | 根据共同板块筛选同行 |
| 板块搜索 | `ths_index`、`dc_index`、`tdx_index` | 跨供应商搜索行业、概念和主题 |
| 板块快照 | 各供应商板块目录、日线、成员、资金流 | 板块资料、最新行情和成员摘要 |
| 板块成分 | `ths_member`、`dc_member`、`tdx_member` | 指定历史时点的板块成分 |
| 板块研究包 | 板块目录、日线、成员、资金流 | 板块趋势、资金和成分研究上下文 |
| 投资日历范围 | `eco_cal`、`fut_basic`，Tushare | 宏观发布、央行事件及股指期货交割日 |
| 单日投资事件 | 同上 | 指定日期的重要事件明细和发布状态 |

## 辅助数据入口（12）

| 数量 | 用途 | 来源 |
|---:|---|---|
| 6 | 数据集目录、契约、记录查询、接口映射、通用接口查询、时效查询 | 本地194个标准数据集；193个Tushare，1个中国货币网+Tushare |
| 5 | 原始请求、原始记录、覆盖和血缘审计 | Tushare原始请求与响应 |
| 1 | `POST /api/v1/data/sources/financial_data/query` | Financial Data；受控开放163条白名单业务路由 |

完整的163条 Financial Data 路由参见 `reports/data_service_inventory_latest.md`。
