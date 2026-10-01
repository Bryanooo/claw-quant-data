# Data service inventory

Generated: `2026-10-01T05:58:41.794986+00:00`

63 catalogued GET data-service entrypoints plus one authenticated Financial Data POST query-through gateway. The gateway exposes 163 allowlisted upstream business routes; those routes are not counted as 163 separate local HTTP endpoints.

## Summary

| Measure | Count |
|---|---:|
| `catalogued_get_entrypoints` | 63 |
| `financial_data_query_gateways` | 1 |
| `public_data_http_entrypoints` | 64 |
| `tushare_raw_audit_entrypoints` | 5 |
| `canonical_store_entrypoints` | 6 |
| `canonical_hybrid_entrypoints` | 24 |
| `derived_research_entrypoints` | 28 |
| `financial_data_business_routes` | 163 |
| `standard_datasets` | 194 |
| `tushare_only_datasets` | 193 |
| `multi_source_datasets` | 1 |

## Public service groups

### Tushare 原始审计服务 (5)

| Method | Path | Service | Origin | Test scope |
|---|---|---|---|---|
| GET | `/api/v1/audit/raw/interfaces` | 原始审计覆盖 | tushare | route + repository contract |
| GET | `/api/v1/audit/raw/{api_name}/requests` | 上游请求账本 | tushare | route + repository contract |
| GET | `/api/v1/audit/raw/{api_name}/records` | 原始记录 | tushare | route + repository contract |
| GET | `/api/v1/audit/raw/{api_name}/coverage` | 接口审计摘要 | tushare | route + repository contract |
| GET | `/api/v1/audit/raw/{api_name}/lineage/{record_hash}` | 原始血缘 | tushare | route + repository contract |

### 规范数据集通用服务 (6)

| Method | Path | Service | Origin | Test scope |
|---|---|---|---|---|
| GET | `/api/v1/data/datasets` | 数据集目录 | canonical_db (193 Tushare-only datasets; 1 ChinaMoney/Tushare merged dataset) | route + registry + query contract |
| GET | `/api/v1/data/datasets/{dataset_name}` | 数据集契约 | canonical_db (193 Tushare-only datasets; 1 ChinaMoney/Tushare merged dataset) | route + registry + query contract |
| GET | `/api/v1/data/datasets/{dataset_name}/records` | 标准记录查询 | canonical_db (193 Tushare-only datasets; 1 ChinaMoney/Tushare merged dataset) | route + registry + query contract |
| GET | `/api/v1/data/interfaces` | 上游映射 | canonical_db (193 Tushare-only datasets; 1 ChinaMoney/Tushare merged dataset) | route + registry + query contract |
| GET | `/api/v1/data/interfaces/{api_name}/records` | 通用接口标准查询 | canonical_db (193 Tushare-only datasets; 1 ChinaMoney/Tushare merged dataset) | route + registry + query contract |
| GET | `/api/v1/data/freshness` | 时效状态 | canonical_db (193 Tushare-only datasets; 1 ChinaMoney/Tushare merged dataset) | route + registry + query contract |

### 规范语义服务 (24)

| Method | Path | Service | Origin | Test scope |
|---|---|---|---|---|
| GET | `/api/v1/data/canonical/market-bars` | 规范 A 股日线 | Tushare canonical DB first; Financial Data only after a verified local miss | route + canonical model + source-selection contract |
| GET | `/api/v1/data/canonical/trading-sessions` | 规范 A 股交易日历 | Tushare canonical DB first; Financial Data only after a verified local miss | route + canonical model + source-selection contract |
| GET | `/api/v1/data/canonical/equity-profiles` | 规范 A 股身份 | Tushare canonical DB first; Financial Data only after a verified local miss | route + canonical model + source-selection contract |
| GET | `/api/v1/data/canonical/equity-valuations` | 规范 A 股估值 | Tushare canonical DB first; Financial Data only after a verified local miss | route + canonical model + source-selection contract |
| GET | `/api/v1/data/canonical/equity-financial-periods` | 规范 A 股财务期间 | Tushare canonical DB first; Financial Data only after a verified local miss | route + canonical model + source-selection contract |
| GET | `/api/v1/data/canonical/equity-performance-updates` | 规范 A 股业绩预告与快报 | Tushare canonical DB first; Financial Data only after a verified local miss | route + canonical model + source-selection contract |
| GET | `/api/v1/data/canonical/equity-financial-metrics` | 规范 A 股财务指标 | Tushare canonical DB first; Financial Data only after a verified local miss | route + canonical model + source-selection contract |
| GET | `/api/v1/data/canonical/equity-ttm-financials` | 规范 A 股滚动财务 | Tushare canonical DB first; Financial Data only after a verified local miss | route + canonical model + source-selection contract |
| GET | `/api/v1/data/canonical/equity-dividends` | 规范 A 股分红 | Tushare canonical DB first; Financial Data only after a verified local miss | route + canonical model + source-selection contract |
| GET | `/api/v1/data/canonical/equity-repurchases` | 规范 A 股回购 | Tushare canonical DB first; Financial Data only after a verified local miss | route + canonical model + source-selection contract |
| GET | `/api/v1/data/canonical/equity-holder-counts` | 规范 A 股股东户数 | Tushare canonical DB first; Financial Data only after a verified local miss | route + canonical model + source-selection contract |
| GET | `/api/v1/data/canonical/equity-business-segments` | 规范 A 股主营构成 | Tushare canonical DB first; Financial Data only after a verified local miss | route + canonical model + source-selection contract |
| GET | `/api/v1/data/canonical/equity-shareholders` | 规范 A 股主要股东 | Tushare canonical DB first; Financial Data only after a verified local miss | route + canonical model + source-selection contract |
| GET | `/api/v1/data/canonical/equity-restricted-releases` | 规范 A 股限售解禁 | Tushare canonical DB first; Financial Data only after a verified local miss | route + canonical model + source-selection contract |
| GET | `/api/v1/data/canonical/equity-pledges` | 规范 A 股股权质押 | Tushare canonical DB first; Financial Data only after a verified local miss | route + canonical model + source-selection contract |
| GET | `/api/v1/data/canonical/equity-risk-alerts` | 规范 A 股风险警示 | Tushare canonical DB first; Financial Data only after a verified local miss | route + canonical model + source-selection contract |
| GET | `/api/v1/data/canonical/equity-suspensions` | 规范 A 股停复牌 | Tushare canonical DB first; Financial Data only after a verified local miss | route + canonical model + source-selection contract |
| GET | `/api/v1/data/canonical/fund-profiles` | 规范基金档案 | Tushare canonical DB first; Financial Data only after a verified local miss | route + canonical model + source-selection contract |
| GET | `/api/v1/data/canonical/fund-nav` | 规范基金净值 | Tushare canonical DB first; Financial Data only after a verified local miss | route + canonical model + source-selection contract |
| GET | `/api/v1/data/canonical/fund-stock-holdings` | 规范基金股票持仓 | Tushare canonical DB first; Financial Data only after a verified local miss | route + canonical model + source-selection contract |
| GET | `/api/v1/data/canonical/fund-dividends` | 规范基金分红 | Tushare canonical DB first; Financial Data only after a verified local miss | route + canonical model + source-selection contract |
| GET | `/api/v1/data/canonical/fund-managers` | 规范基金经理 | Tushare canonical DB first; Financial Data only after a verified local miss | route + canonical model + source-selection contract |
| GET | `/api/v1/data/canonical/index-profiles` | 规范指数档案 | Tushare canonical DB first; Financial Data only after a verified local miss | route + canonical model + source-selection contract |
| GET | `/api/v1/data/canonical/index-constituents` | 规范指数成分权重 | Tushare canonical DB first; Financial Data only after a verified local miss | route + canonical model + source-selection contract |

### 系统聚合研究服务 (28)

| Method | Path | Service | Origin | Test scope |
|---|---|---|---|---|
| GET | `/api/v1/research/capabilities` | 研究能力目录 | system-derived aggregation over canonical datasets | route + calculation unit tests; representative live acceptance set |
| GET | `/api/v1/research/readiness` | 研究数据就绪状态 | system-derived aggregation over canonical datasets | route + calculation unit tests; representative live acceptance set |
| GET | `/api/v1/research/validation-set` | 研究端到端验证集 | system-derived aggregation over canonical datasets | route + calculation unit tests; representative live acceptance set |
| GET | `/api/v1/research/stocks/{ts_code}/fundamentals` | 基本面分析 | system-derived aggregation over canonical datasets | route + calculation unit tests; representative live acceptance set |
| GET | `/api/v1/research/stocks/{ts_code}/valuation` | 估值分析 | system-derived aggregation over canonical datasets | route + calculation unit tests; representative live acceptance set |
| GET | `/api/v1/research/stocks/{ts_code}/technicals` | 技术面分析 | system-derived aggregation over canonical datasets | route + calculation unit tests; representative live acceptance set |
| GET | `/api/v1/research/stocks/{ts_code}/capital-flow` | 资金与筹码 | system-derived aggregation over canonical datasets | route + calculation unit tests; representative live acceptance set |
| GET | `/api/v1/research/stocks/{ts_code}/repurchase-progress` | 回购进展 | system-derived aggregation over canonical datasets | route + calculation unit tests; representative live acceptance set |
| GET | `/api/v1/research/instruments/{asset_type}/{code}/technicals` | 多资产技术面 | system-derived aggregation over canonical datasets | route + calculation unit tests; representative live acceptance set |
| GET | `/api/v1/research/stocks/{ts_code}/event-study` | 事件研究 | system-derived aggregation over canonical datasets | route + calculation unit tests; representative live acceptance set |
| GET | `/api/v1/research/market/breadth` | 市场宽度 | system-derived aggregation over canonical datasets | route + calculation unit tests; representative live acceptance set |
| GET | `/api/v1/research/macro/regime` | 宏观状态 | system-derived aggregation over canonical datasets | route + calculation unit tests; representative live acceptance set |
| GET | `/api/v1/research/macro/{theme}` | 宏观主题序列 | system-derived aggregation over canonical datasets | route + calculation unit tests; representative live acceptance set |
| GET | `/api/v1/research/etfs/flows` | ETF份额资金流 | system-derived aggregation over canonical datasets | route + calculation unit tests; representative live acceptance set |
| GET | `/api/v1/research/etfs/state-team-signals` | 国家队ETF证据信号 | system-derived aggregation over canonical datasets | route + calculation unit tests; representative live acceptance set |
| GET | `/api/v1/research/sectors/{provider}/rotation` | 板块轮动 | system-derived aggregation over canonical datasets | route + calculation unit tests; representative live acceptance set |
| GET | `/api/v1/research/sectors/{provider}/{sector_code}/fundamentals` | 行业基本面 | system-derived aggregation over canonical datasets | route + calculation unit tests; representative live acceptance set |
| GET | `/api/v1/research/sectors/{provider}/{sector_code}/breadth` | 行业内部宽度 | system-derived aggregation over canonical datasets | route + calculation unit tests; representative live acceptance set |
| GET | `/api/v1/research/stocks/{ts_code}/snapshot` | 个股快照 | system-derived aggregation over canonical datasets | route + calculation unit tests; representative live acceptance set |
| GET | `/api/v1/research/stocks/{ts_code}/research-pack` | 个股研究包 | system-derived aggregation over canonical datasets | route + calculation unit tests; representative live acceptance set |
| GET | `/api/v1/research/stocks/{ts_code}/sectors` | 股票所属板块 | system-derived aggregation over canonical datasets | route + calculation unit tests; representative live acceptance set |
| GET | `/api/v1/research/stocks/{ts_code}/peers` | 同行发现 | system-derived aggregation over canonical datasets | route + calculation unit tests; representative live acceptance set |
| GET | `/api/v1/research/sectors` | 板块搜索 | system-derived aggregation over canonical datasets | route + calculation unit tests; representative live acceptance set |
| GET | `/api/v1/research/sectors/{provider}/{sector_code}/snapshot` | 板块快照 | system-derived aggregation over canonical datasets | route + calculation unit tests; representative live acceptance set |
| GET | `/api/v1/research/sectors/{provider}/{sector_code}/members` | 板块成分 | system-derived aggregation over canonical datasets | route + calculation unit tests; representative live acceptance set |
| GET | `/api/v1/research/sectors/{provider}/{sector_code}/research-pack` | 板块研究包 | system-derived aggregation over canonical datasets | route + calculation unit tests; representative live acceptance set |
| GET | `/api/v1/research/investment-calendar` | 投资日历范围 | system-derived aggregation over canonical datasets | route + calculation unit tests; representative live acceptance set |
| GET | `/api/v1/research/investment-calendar/{event_date}` | 单日投资事件 | system-derived aggregation over canonical datasets | route + calculation unit tests; representative live acceptance set |

## Financial Data query-through

The local gateway is `POST /api/v1/data/sources/financial_data/query`. It exposes the following reviewed upstream routes without persisting the credential:

- `/api/v1/altdata/hot-plate-rank`
- `/api/v1/altdata/hot-stock-rank`
- `/api/v1/common/entity_relationship`
- `/api/v1/common/industry-chain-tree`
- `/api/v1/common/stock-belong-industry-chain`
- `/api/v1/common/symbol-by-cond`
- `/api/v1/common/trading-day`
- `/api/v1/common/trading-state`
- `/api/v1/fund/asset-allocation`
- `/api/v1/fund/bond-portfolio`
- `/api/v1/fund/dividend`
- `/api/v1/fund/fund-archive`
- `/api/v1/fund/fund-charge-rate`
- `/api/v1/fund/fund-company-info`
- `/api/v1/fund/fund-manager`
- `/api/v1/fund/fund-portfolio`
- `/api/v1/fund/invest-industry`
- `/api/v1/fund/net-value`
- `/api/v1/fund/plate-fund-relevancy`
- `/api/v1/fund/share-split`
- `/api/v1/fund/stock-portfolio`
- `/api/v1/fund/trade-limit`
- `/api/v1/fund/yield-rank`
- `/api/v1/fund_derived/benchmark-excess`
- `/api/v1/fund_derived/risk-return`
- `/api/v1/hk_stock/adr-conversion-ratio`
- `/api/v1/hk_stock/equity-structure`
- `/api/v1/hk_stock/free-float`
- `/api/v1/hk_stock/high-shareholding-concentration`
- `/api/v1/hk_stock/ipo-key-indicators`
- `/api/v1/hk_stock/ratings`
- `/api/v1/hk_stock/restricted-share-unlock-schedule`
- `/api/v1/hk_stock/risk-list`
- `/api/v1/hk_stock/shareholding-changes`
- `/api/v1/hk_stock/short-position-statistics`
- `/api/v1/hk_stock/short-selling`
- `/api/v1/hk_stock/special-notices`
- `/api/v1/hk_stock/special-securities`
- `/api/v1/hk_stock/suspend-resumption`
- `/api/v1/hk_stock/target-price`
- `/api/v1/hk_stock/temporary-parallel-trading`
- `/api/v1/index_fnd/index-constituents-list-weight`
- `/api/v1/index_fnd/index-fnd-estimates-summary`
- `/api/v1/index_fnd/index-fnd-financial-ratios`
- `/api/v1/index_fnd/index-fnd-financial-ratios-single`
- `/api/v1/index_fnd/index-fnd-financial-statement`
- `/api/v1/index_fnd/index-profile-basic-info`
- `/api/v1/info/announcements`
- `/api/v1/info/news-global-search`
- `/api/v1/info/research-reports`
- `/api/v1/info/tag/category`
- `/api/v1/info/tag/query`
- `/api/v1/macro/data-query`
- `/api/v1/macro/meta-search`
- `/api/v1/onecode/query`
- `/api/v1/onecode/recall`
- `/api/v1/quote/auction-snapshot`
- `/api/v1/quote/basic-snapshot`
- `/api/v1/quote/capital-flow-range`
- `/api/v1/quote/derived-snapshot`
- `/api/v1/quote/kline-batch`
- `/api/v1/sector/plate-component`
- `/api/v1/sector/plate-fund-relevancy`
- `/api/v1/sector/plate-list`
- `/api/v1/sector/sector-capital-flow`
- `/api/v1/sector/sector-financial-cumulative`
- `/api/v1/sector/sector-financial-point`
- `/api/v1/sector/sector-financial-quarterly`
- `/api/v1/sector/sector-valuation`
- `/api/v1/stock/after-daily-quote`
- `/api/v1/stock/ashare-cdr-conversion-ratio`
- `/api/v1/stock/block-trading-details`
- `/api/v1/stock/change-plan`
- `/api/v1/stock/component-list-belonged`
- `/api/v1/stock/daily-valuation-indicators`
- `/api/v1/stock/market-detail`
- `/api/v1/stock/risk-alerts`
- `/api/v1/stock/sc-activitie`
- `/api/v1/stock/sc-trade`
- `/api/v1/stock/sh-hold-stat`
- `/api/v1/stock/stock-index-constituents-list`
- `/api/v1/stock/suspend-resumption`
- `/api/v1/stock/tech-indicators`
- `/api/v1/stock/tech-patterns`
- `/api/v1/stock/tra-variant`
- `/api/v1/stock_fnd/actual-controller`
- `/api/v1/stock_fnd/asset-restructuring`
- `/api/v1/stock_fnd/balance-sheet`
- `/api/v1/stock_fnd/broker-golden-stocks`
- `/api/v1/stock_fnd/buyback-plans`
- `/api/v1/stock_fnd/concert-parties`
- `/api/v1/stock_fnd/consensus-details`
- `/api/v1/stock_fnd/consensus-stats`
- `/api/v1/stock_fnd/controlling-shareholder`
- `/api/v1/stock_fnd/delisting-info`
- `/api/v1/stock_fnd/depository-receipt`
- `/api/v1/stock_fnd/dividend-details`
- `/api/v1/stock_fnd/dividend-record`
- `/api/v1/stock_fnd/employee-ownership-plan`
- `/api/v1/stock_fnd/equity-structure`
- `/api/v1/stock_fnd/executive-compensation`
- `/api/v1/stock_fnd/free-float`
- `/api/v1/stock_fnd/fund-raising-usage`
- `/api/v1/stock_fnd/growth-rates-acc`
- `/api/v1/stock_fnd/growth-rates-quarter`
- `/api/v1/stock_fnd/guarantee-events`
- `/api/v1/stock_fnd/guarantee-stats`
- `/api/v1/stock_fnd/hk-intermediary-holdings`
- `/api/v1/stock_fnd/holder-count`
- `/api/v1/stock_fnd/holding-stats`
- `/api/v1/stock_fnd/holding-subsidiaries`
- `/api/v1/stock_fnd/income-cashflow-acc`
- `/api/v1/stock_fnd/income-cashflow-single`
- `/api/v1/stock_fnd/industry-classification`
- `/api/v1/stock_fnd/investor-relations`
- `/api/v1/stock_fnd/ipo-primary`
- `/api/v1/stock_fnd/ipo-quote-details`
- `/api/v1/stock_fnd/ipo-winning-numbers`
- `/api/v1/stock_fnd/listing-rules`
- `/api/v1/stock_fnd/litigation-arbitration`
- `/api/v1/stock_fnd/main-business-business`
- `/api/v1/stock_fnd/main-business-industry`
- `/api/v1/stock_fnd/main-business-product`
- `/api/v1/stock_fnd/main-business-region`
- `/api/v1/stock_fnd/metrics-ttm`
- `/api/v1/stock_fnd/performance-forecast`
- `/api/v1/stock_fnd/prelim-acc`
- `/api/v1/stock_fnd/prelim-balance`
- `/api/v1/stock_fnd/prelim-quarter`
- `/api/v1/stock_fnd/rating-summary`
- `/api/v1/stock_fnd/regulatory-penalties`
- `/api/v1/stock_fnd/related-party-transactions`
- `/api/v1/stock_fnd/restricted-release-calendar`
- `/api/v1/stock_fnd/review-process`
- `/api/v1/stock_fnd/risk-factor-csi300`
- `/api/v1/stock_fnd/risk-factor-csi500`
- `/api/v1/stock_fnd/risk-factor-sh000001`
- `/api/v1/stock_fnd/risk-factor-sw`
- `/api/v1/stock_fnd/seo-placement-details`
- `/api/v1/stock_fnd/shareholder-commitment`
- `/api/v1/stock_fnd/shareholder-list`
- `/api/v1/stock_fnd/shareholder-meeting`
- `/api/v1/stock_fnd/specialty-metrics-period`
- `/api/v1/stock_fnd/specialty-metrics-point`
- `/api/v1/stock_fnd/stock-basic-info`
- `/api/v1/stock_fnd/stock-rel-fund-holdings-top`
- `/api/v1/stock_fnd/style-classification`
- `/api/v1/stock_fnd/takeover-offers`
- `/api/v1/stock_fnd/target-price`
- `/api/v1/stock_fnd/tender-offers`
- `/api/v1/stock_fnd/yield-factor`
- `/api/v1/stock_sh_equity/freeze-pledge`
- `/api/v1/us_stock/adr-ratio-changes`
- `/api/v1/us_stock/capital-events`
- `/api/v1/us_stock/company-ownership`
- `/api/v1/us_stock/concept-components`
- `/api/v1/us_stock/dividends`
- `/api/v1/us_stock/equity-structure`
- `/api/v1/us_stock/ratings`
- `/api/v1/us_stock/security-markings`
- `/api/v1/us_stock/target-price`
- `/api/v2/info/news/article`
- `/api/v2/info/news/search_evidence`

## Test posture

- `route_contract`: 64/64 public data entrypoints covered by OpenAPI registration tests
- `tushare_mapping_contract`: 201/201 collectable interfaces map to public datasets
- `dataset_registry_contract`: 194/194 registered datasets map to collector or normalization storage
- `financial_data_catalog_contract`: 163/163 business routes are allowlisted and input-validated
- `canonical_contract`: 24/24 canonical routes registered; domain services have unit/contract tests
- `research_contract`: 28/28 research routes registered; calculation services have unit tests
- `research_live_acceptance`: 13 representative end-to-end cases
- `financial_data_live_acceptance`: protocol and query gateway covered; a full 163-route live sweep is intentionally not run in CI because it consumes provider quota and depends on mutable upstream sample data
