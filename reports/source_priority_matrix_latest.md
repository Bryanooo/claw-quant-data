# 数据源优先级矩阵

> 生成时间：`2026-10-01T04:43:43.640156+00:00`。机器可读版本见 [`source_priority_matrix_latest.json`](source_priority_matrix_latest.json)。

## 统一规则

- 外部消费者使用规范数据集或研究接口，不直接依赖供应商字段。
- `local_db_first`：先读已经由 Tushare 定时采集并写入 DB 的规范数据；只有请求切片缺失或超过新鲜度 SLA，且 Financial Data 规范适配器通过契约测试后，才允许消耗额度回退。
- `financial_data_first`：当前没有等价本地规范数据集，或能力本身是显式实时查询；返回外部前仍必须经过规范字段、代码、日期和单位适配。
- 当前隐式回退数为 **0**。仅规范接口可触发已通过测试的有限回退；`adapter_required` 不是已启用，避免供应商原生模型混入统一接口。

## 汇总

| Financial Data 路由 | 本地 DB 优先 | Financial Data 优先 | 已启用规范适配 |
|---:|---:|---:|---:|
| 163 | 57 | 106 | 29 |

## 完整路由清单

| 路由 | 读取优先级 | 本地规范数据集 | Financial Data 角色 | 规范化状态 | 本地适用范围 |
|---|---|---|---|---|---|
| `/api/v1/altdata/hot-plate-rank` | `financial_data_first` | — | `primary_until_local_dataset_exists` | `canonical_dataset_required` | none |
| `/api/v1/altdata/hot-stock-rank` | `financial_data_first` | — | `primary_until_local_dataset_exists` | `canonical_dataset_required` | none |
| `/api/v1/common/entity_relationship` | `financial_data_first` | — | `primary_until_local_dataset_exists` | `canonical_dataset_required` | none |
| `/api/v1/common/industry-chain-tree` | `financial_data_first` | — | `primary_until_local_dataset_exists` | `canonical_dataset_required` | none |
| `/api/v1/common/stock-belong-industry-chain` | `financial_data_first` | — | `primary_until_local_dataset_exists` | `canonical_dataset_required` | none |
| `/api/v1/common/symbol-by-cond` | `local_db_first` | `stock_basic`, `fund_basic`, `index_basic`, `hk_basic`, `us_basic`, `sge_basic` | `quota_fallback_after_local_miss` | `adapter_required` | only requests whose market, asset, period and fields are covered by the listed canonical datasets |
| `/api/v1/common/trading-day` | `local_db_first` | `trade_calendar`, `hk_tradecal`, `us_tradecal`, `fut_trade_cal` | `quota_fallback_after_local_miss` | `partial_ready_a_share` | only requests whose market, asset, period and fields are covered by the listed canonical datasets |
| `/api/v1/common/trading-state` | `financial_data_first` | — | `explicit_realtime_query` | `canonical_dataset_required` | none |
| `/api/v1/fund/asset-allocation` | `financial_data_first` | — | `primary_until_local_dataset_exists` | `canonical_dataset_required` | none |
| `/api/v1/fund/bond-portfolio` | `financial_data_first` | — | `primary_until_local_dataset_exists` | `canonical_dataset_required` | none |
| `/api/v1/fund/dividend` | `local_db_first` | `fund_div` | `quota_fallback_after_local_miss` | `partial_ready_fund_cash_dividends` | only requests whose market, asset, period and fields are covered by the listed canonical datasets |
| `/api/v1/fund/fund-archive` | `local_db_first` | `fund_basic` | `quota_fallback_after_local_miss` | `partial_ready_common_profile_fields` | only requests whose market, asset, period and fields are covered by the listed canonical datasets |
| `/api/v1/fund/fund-charge-rate` | `financial_data_first` | — | `primary_until_local_dataset_exists` | `canonical_dataset_required` | none |
| `/api/v1/fund/fund-company-info` | `local_db_first` | `fund_company` | `quota_fallback_after_local_miss` | `adapter_required` | only requests whose market, asset, period and fields are covered by the listed canonical datasets |
| `/api/v1/fund/fund-manager` | `local_db_first` | `fund_manager` | `quota_fallback_after_local_miss` | `partial_ready_fund_manager_tenures` | only requests whose market, asset, period and fields are covered by the listed canonical datasets |
| `/api/v1/fund/fund-portfolio` | `financial_data_first` | — | `primary_until_local_dataset_exists` | `canonical_dataset_required` | none |
| `/api/v1/fund/invest-industry` | `financial_data_first` | — | `primary_until_local_dataset_exists` | `canonical_dataset_required` | none |
| `/api/v1/fund/net-value` | `local_db_first` | `fund_nav`, `fund_daily` | `quota_fallback_after_local_miss` | `partial_ready_bounded_nav_range` | only requests whose market, asset, period and fields are covered by the listed canonical datasets |
| `/api/v1/fund/plate-fund-relevancy` | `financial_data_first` | — | `primary_until_local_dataset_exists` | `canonical_dataset_required` | none |
| `/api/v1/fund/share-split` | `local_db_first` | `fund_adj` | `quota_fallback_after_local_miss` | `adapter_required` | only requests whose market, asset, period and fields are covered by the listed canonical datasets |
| `/api/v1/fund/stock-portfolio` | `local_db_first` | `fund_portfolio` | `quota_fallback_after_local_miss` | `partial_ready_quarterly_stock_holdings` | only requests whose market, asset, period and fields are covered by the listed canonical datasets |
| `/api/v1/fund/trade-limit` | `financial_data_first` | — | `primary_until_local_dataset_exists` | `canonical_dataset_required` | none |
| `/api/v1/fund/yield-rank` | `financial_data_first` | — | `primary_until_local_dataset_exists` | `canonical_dataset_required` | none |
| `/api/v1/fund_derived/benchmark-excess` | `local_db_first` | `fund_daily`, `fund_nav`, `index_daily` | `quota_fallback_after_local_miss` | `adapter_required` | only requests whose market, asset, period and fields are covered by the listed canonical datasets |
| `/api/v1/fund_derived/risk-return` | `local_db_first` | `fund_daily`, `fund_nav` | `quota_fallback_after_local_miss` | `adapter_required` | only requests whose market, asset, period and fields are covered by the listed canonical datasets |
| `/api/v1/hk_stock/adr-conversion-ratio` | `financial_data_first` | — | `primary_until_local_dataset_exists` | `canonical_dataset_required` | none |
| `/api/v1/hk_stock/equity-structure` | `financial_data_first` | — | `primary_until_local_dataset_exists` | `canonical_dataset_required` | none |
| `/api/v1/hk_stock/free-float` | `financial_data_first` | — | `primary_until_local_dataset_exists` | `canonical_dataset_required` | none |
| `/api/v1/hk_stock/high-shareholding-concentration` | `financial_data_first` | — | `primary_until_local_dataset_exists` | `canonical_dataset_required` | none |
| `/api/v1/hk_stock/ipo-key-indicators` | `financial_data_first` | — | `primary_until_local_dataset_exists` | `canonical_dataset_required` | none |
| `/api/v1/hk_stock/ratings` | `financial_data_first` | — | `primary_until_local_dataset_exists` | `canonical_dataset_required` | none |
| `/api/v1/hk_stock/restricted-share-unlock-schedule` | `financial_data_first` | — | `primary_until_local_dataset_exists` | `canonical_dataset_required` | none |
| `/api/v1/hk_stock/risk-list` | `financial_data_first` | — | `primary_until_local_dataset_exists` | `canonical_dataset_required` | none |
| `/api/v1/hk_stock/shareholding-changes` | `financial_data_first` | — | `primary_until_local_dataset_exists` | `canonical_dataset_required` | none |
| `/api/v1/hk_stock/short-position-statistics` | `financial_data_first` | — | `primary_until_local_dataset_exists` | `canonical_dataset_required` | none |
| `/api/v1/hk_stock/short-selling` | `financial_data_first` | — | `primary_until_local_dataset_exists` | `canonical_dataset_required` | none |
| `/api/v1/hk_stock/special-notices` | `financial_data_first` | — | `primary_until_local_dataset_exists` | `canonical_dataset_required` | none |
| `/api/v1/hk_stock/special-securities` | `financial_data_first` | — | `primary_until_local_dataset_exists` | `canonical_dataset_required` | none |
| `/api/v1/hk_stock/suspend-resumption` | `financial_data_first` | — | `primary_until_local_dataset_exists` | `canonical_dataset_required` | none |
| `/api/v1/hk_stock/target-price` | `financial_data_first` | — | `primary_until_local_dataset_exists` | `canonical_dataset_required` | none |
| `/api/v1/hk_stock/temporary-parallel-trading` | `financial_data_first` | — | `primary_until_local_dataset_exists` | `canonical_dataset_required` | none |
| `/api/v1/index_fnd/index-constituents-list-weight` | `local_db_first` | `index_weight`, `index_member_all` | `quota_fallback_after_local_miss` | `partial_ready_sh_sz_weighted_constituents` | only requests whose market, asset, period and fields are covered by the listed canonical datasets |
| `/api/v1/index_fnd/index-fnd-estimates-summary` | `financial_data_first` | — | `primary_until_local_dataset_exists` | `canonical_dataset_required` | none |
| `/api/v1/index_fnd/index-fnd-financial-ratios` | `financial_data_first` | — | `primary_until_local_dataset_exists` | `canonical_dataset_required` | none |
| `/api/v1/index_fnd/index-fnd-financial-ratios-single` | `financial_data_first` | — | `primary_until_local_dataset_exists` | `canonical_dataset_required` | none |
| `/api/v1/index_fnd/index-fnd-financial-statement` | `financial_data_first` | — | `primary_until_local_dataset_exists` | `canonical_dataset_required` | none |
| `/api/v1/index_fnd/index-profile-basic-info` | `local_db_first` | `index_basic` | `quota_fallback_after_local_miss` | `partial_ready_sh_sz_index_profile` | only requests whose market, asset, period and fields are covered by the listed canonical datasets |
| `/api/v1/info/announcements` | `financial_data_first` | — | `primary_until_local_dataset_exists` | `canonical_dataset_required` | none |
| `/api/v1/info/news-global-search` | `financial_data_first` | — | `primary_until_local_dataset_exists` | `canonical_dataset_required` | none |
| `/api/v1/info/research-reports` | `local_db_first` | `report_rc` | `quota_fallback_after_local_miss` | `adapter_required` | only requests whose market, asset, period and fields are covered by the listed canonical datasets |
| `/api/v1/info/tag/category` | `financial_data_first` | — | `primary_until_local_dataset_exists` | `canonical_dataset_required` | none |
| `/api/v1/info/tag/query` | `financial_data_first` | — | `primary_until_local_dataset_exists` | `canonical_dataset_required` | none |
| `/api/v1/macro/data-query` | `local_db_first` | `cn_cpi`, `cn_gdp`, `cn_m`, `cn_pmi`, `cn_ppi`, `sf_month`, `shibor`, `shibor_lpr`, `libor`, `hibor`, `us_tbr`, `us_tltr`, `us_trltr`, `us_trycr`, `us_tycr` | `quota_fallback_after_local_miss` | `adapter_required` | only requests whose market, asset, period and fields are covered by the listed canonical datasets |
| `/api/v1/macro/meta-search` | `financial_data_first` | — | `primary_until_local_dataset_exists` | `canonical_dataset_required` | none |
| `/api/v1/onecode/query` | `local_db_first` | `stock_daily`, `stock_daily_basic`, `index_daily`, `fund_daily`, `fund_nav`, `financial_indicator` | `quota_fallback_after_local_miss` | `adapter_required` | only requests whose market, asset, period and fields are covered by the listed canonical datasets |
| `/api/v1/onecode/recall` | `financial_data_first` | — | `primary_until_local_dataset_exists` | `canonical_dataset_required` | none |
| `/api/v1/quote/auction-snapshot` | `financial_data_first` | — | `explicit_realtime_query` | `canonical_dataset_required` | none |
| `/api/v1/quote/basic-snapshot` | `financial_data_first` | — | `explicit_realtime_query` | `canonical_dataset_required` | none |
| `/api/v1/quote/capital-flow-range` | `local_db_first` | `moneyflow`, `moneyflow_dc`, `moneyflow_ths`, `moneyflow_ind_dc`, `moneyflow_ind_ths`, `moneyflow_mkt_dc` | `quota_fallback_after_local_miss` | `adapter_required` | only requests whose market, asset, period and fields are covered by the listed canonical datasets |
| `/api/v1/quote/derived-snapshot` | `financial_data_first` | — | `explicit_realtime_query` | `canonical_dataset_required` | none |
| `/api/v1/quote/kline-batch` | `local_db_first` | `stock_daily`, `index_daily`, `index_weekly`, `index_monthly`, `fund_daily`, `hk_daily`, `sge_daily`, `fut_daily`, `opt_daily`, `cb_daily`, `forex_daily` | `quota_fallback_after_local_miss` | `partial_ready_a_share_daily_unadjusted` | only requests whose market, asset, period and fields are covered by the listed canonical datasets |
| `/api/v1/sector/plate-component` | `local_db_first` | `ths_member`, `dc_member`, `tdx_member`, `index_member_all` | `quota_fallback_after_local_miss` | `adapter_required` | only requests whose market, asset, period and fields are covered by the listed canonical datasets |
| `/api/v1/sector/plate-fund-relevancy` | `financial_data_first` | — | `primary_until_local_dataset_exists` | `canonical_dataset_required` | none |
| `/api/v1/sector/plate-list` | `local_db_first` | `ths_index`, `dc_index`, `tdx_index`, `index_classify` | `quota_fallback_after_local_miss` | `adapter_required` | only requests whose market, asset, period and fields are covered by the listed canonical datasets |
| `/api/v1/sector/sector-capital-flow` | `local_db_first` | `moneyflow_ind_dc`, `moneyflow_ind_ths`, `margin`, `margin_detail` | `quota_fallback_after_local_miss` | `adapter_required` | only requests whose market, asset, period and fields are covered by the listed canonical datasets |
| `/api/v1/sector/sector-financial-cumulative` | `financial_data_first` | — | `primary_until_local_dataset_exists` | `canonical_dataset_required` | none |
| `/api/v1/sector/sector-financial-point` | `financial_data_first` | — | `primary_until_local_dataset_exists` | `canonical_dataset_required` | none |
| `/api/v1/sector/sector-financial-quarterly` | `financial_data_first` | — | `primary_until_local_dataset_exists` | `canonical_dataset_required` | none |
| `/api/v1/sector/sector-valuation` | `local_db_first` | `index_dailybasic` | `quota_fallback_after_local_miss` | `adapter_required` | only requests whose market, asset, period and fields are covered by the listed canonical datasets |
| `/api/v1/stock/after-daily-quote` | `financial_data_first` | — | `primary_until_local_dataset_exists` | `canonical_dataset_required` | none |
| `/api/v1/stock/ashare-cdr-conversion-ratio` | `financial_data_first` | — | `primary_until_local_dataset_exists` | `canonical_dataset_required` | none |
| `/api/v1/stock/block-trading-details` | `local_db_first` | `block_trade` | `quota_fallback_after_local_miss` | `adapter_required` | only requests whose market, asset, period and fields are covered by the listed canonical datasets |
| `/api/v1/stock/change-plan` | `financial_data_first` | — | `primary_until_local_dataset_exists` | `canonical_dataset_required` | none |
| `/api/v1/stock/component-list-belonged` | `local_db_first` | `index_member_all`, `ths_member`, `dc_member`, `tdx_member` | `quota_fallback_after_local_miss` | `adapter_required` | only requests whose market, asset, period and fields are covered by the listed canonical datasets |
| `/api/v1/stock/daily-valuation-indicators` | `local_db_first` | `stock_daily_basic` | `quota_fallback_after_local_miss` | `partial_ready_a_share_daily_core_fields` | only requests whose market, asset, period and fields are covered by the listed canonical datasets |
| `/api/v1/stock/market-detail` | `financial_data_first` | — | `primary_until_local_dataset_exists` | `canonical_dataset_required` | none |
| `/api/v1/stock/risk-alerts` | `local_db_first` | `stk_alert`, `stock_st` | `quota_fallback_after_local_miss` | `partial_ready_a_share_risk_alerts` | only requests whose market, asset, period and fields are covered by the listed canonical datasets |
| `/api/v1/stock/sc-activitie` | `financial_data_first` | — | `primary_until_local_dataset_exists` | `canonical_dataset_required` | none |
| `/api/v1/stock/sc-trade` | `financial_data_first` | — | `primary_until_local_dataset_exists` | `canonical_dataset_required` | none |
| `/api/v1/stock/sh-hold-stat` | `local_db_first` | `hk_hold`, `stock_hsgt` | `quota_fallback_after_local_miss` | `adapter_required` | only requests whose market, asset, period and fields are covered by the listed canonical datasets |
| `/api/v1/stock/stock-index-constituents-list` | `local_db_first` | `index_member_all`, `index_weight` | `quota_fallback_after_local_miss` | `adapter_required` | only requests whose market, asset, period and fields are covered by the listed canonical datasets |
| `/api/v1/stock/suspend-resumption` | `local_db_first` | `stock_suspend` | `quota_fallback_after_local_miss` | `partial_ready_a_share_suspensions` | only requests whose market, asset, period and fields are covered by the listed canonical datasets |
| `/api/v1/stock/tech-indicators` | `local_db_first` | `stock_daily`, `adj_factor`, `stk_factor`, `stk_factor_pro` | `quota_fallback_after_local_miss` | `adapter_required` | only requests whose market, asset, period and fields are covered by the listed canonical datasets |
| `/api/v1/stock/tech-patterns` | `local_db_first` | `stock_daily`, `adj_factor` | `quota_fallback_after_local_miss` | `adapter_required` | only requests whose market, asset, period and fields are covered by the listed canonical datasets |
| `/api/v1/stock/tra-variant` | `financial_data_first` | — | `primary_until_local_dataset_exists` | `canonical_dataset_required` | none |
| `/api/v1/stock_fnd/actual-controller` | `financial_data_first` | — | `primary_until_local_dataset_exists` | `canonical_dataset_required` | none |
| `/api/v1/stock_fnd/asset-restructuring` | `financial_data_first` | — | `primary_until_local_dataset_exists` | `canonical_dataset_required` | none |
| `/api/v1/stock_fnd/balance-sheet` | `local_db_first` | `balancesheet` | `quota_fallback_after_local_miss` | `partial_ready_a_share_balance_core_fields` | only requests whose market, asset, period and fields are covered by the listed canonical datasets |
| `/api/v1/stock_fnd/broker-golden-stocks` | `local_db_first` | `broker_recommend` | `quota_fallback_after_local_miss` | `adapter_required` | only requests whose market, asset, period and fields are covered by the listed canonical datasets |
| `/api/v1/stock_fnd/buyback-plans` | `local_db_first` | `repurchase` | `quota_fallback_after_local_miss` | `partial_ready_a_share_repurchase_plan_fields` | only requests whose market, asset, period and fields are covered by the listed canonical datasets |
| `/api/v1/stock_fnd/concert-parties` | `financial_data_first` | — | `primary_until_local_dataset_exists` | `canonical_dataset_required` | none |
| `/api/v1/stock_fnd/consensus-details` | `financial_data_first` | — | `primary_until_local_dataset_exists` | `canonical_dataset_required` | none |
| `/api/v1/stock_fnd/consensus-stats` | `financial_data_first` | — | `primary_until_local_dataset_exists` | `canonical_dataset_required` | none |
| `/api/v1/stock_fnd/controlling-shareholder` | `financial_data_first` | — | `primary_until_local_dataset_exists` | `canonical_dataset_required` | none |
| `/api/v1/stock_fnd/delisting-info` | `financial_data_first` | — | `primary_until_local_dataset_exists` | `canonical_dataset_required` | none |
| `/api/v1/stock_fnd/depository-receipt` | `financial_data_first` | — | `primary_until_local_dataset_exists` | `canonical_dataset_required` | none |
| `/api/v1/stock_fnd/dividend-details` | `local_db_first` | `dividend` | `quota_fallback_after_local_miss` | `partial_ready_a_share_core_dividend_fields` | only requests whose market, asset, period and fields are covered by the listed canonical datasets |
| `/api/v1/stock_fnd/dividend-record` | `local_db_first` | `dividend` | `quota_fallback_after_local_miss` | `adapter_required` | only requests whose market, asset, period and fields are covered by the listed canonical datasets |
| `/api/v1/stock_fnd/employee-ownership-plan` | `financial_data_first` | — | `primary_until_local_dataset_exists` | `canonical_dataset_required` | none |
| `/api/v1/stock_fnd/equity-structure` | `financial_data_first` | — | `primary_until_local_dataset_exists` | `canonical_dataset_required` | none |
| `/api/v1/stock_fnd/executive-compensation` | `local_db_first` | `stk_rewards` | `quota_fallback_after_local_miss` | `adapter_required` | only requests whose market, asset, period and fields are covered by the listed canonical datasets |
| `/api/v1/stock_fnd/free-float` | `financial_data_first` | — | `primary_until_local_dataset_exists` | `canonical_dataset_required` | none |
| `/api/v1/stock_fnd/fund-raising-usage` | `financial_data_first` | — | `primary_until_local_dataset_exists` | `canonical_dataset_required` | none |
| `/api/v1/stock_fnd/growth-rates-acc` | `local_db_first` | `financial_indicator` | `quota_fallback_after_local_miss` | `partial_ready_a_share_core_financial_metrics` | only requests whose market, asset, period and fields are covered by the listed canonical datasets |
| `/api/v1/stock_fnd/growth-rates-quarter` | `local_db_first` | `income`, `cashflow`, `financial_indicator` | `quota_fallback_after_local_miss` | `adapter_required` | only requests whose market, asset, period and fields are covered by the listed canonical datasets |
| `/api/v1/stock_fnd/guarantee-events` | `financial_data_first` | — | `primary_until_local_dataset_exists` | `canonical_dataset_required` | none |
| `/api/v1/stock_fnd/guarantee-stats` | `financial_data_first` | — | `primary_until_local_dataset_exists` | `canonical_dataset_required` | none |
| `/api/v1/stock_fnd/hk-intermediary-holdings` | `financial_data_first` | — | `primary_until_local_dataset_exists` | `canonical_dataset_required` | none |
| `/api/v1/stock_fnd/holder-count` | `local_db_first` | `stk_holdernumber` | `quota_fallback_after_local_miss` | `partial_ready_a_share_holder_count_fields` | only requests whose market, asset, period and fields are covered by the listed canonical datasets |
| `/api/v1/stock_fnd/holding-stats` | `financial_data_first` | — | `primary_until_local_dataset_exists` | `canonical_dataset_required` | none |
| `/api/v1/stock_fnd/holding-subsidiaries` | `financial_data_first` | — | `primary_until_local_dataset_exists` | `canonical_dataset_required` | none |
| `/api/v1/stock_fnd/income-cashflow-acc` | `local_db_first` | `income`, `cashflow` | `quota_fallback_after_local_miss` | `partial_ready_a_share_cumulative_core_fields` | only requests whose market, asset, period and fields are covered by the listed canonical datasets |
| `/api/v1/stock_fnd/income-cashflow-single` | `local_db_first` | `income`, `cashflow` | `quota_fallback_after_local_miss` | `adapter_required` | only requests whose market, asset, period and fields are covered by the listed canonical datasets |
| `/api/v1/stock_fnd/industry-classification` | `local_db_first` | `stock_basic`, `index_classify` | `quota_fallback_after_local_miss` | `adapter_required` | only requests whose market, asset, period and fields are covered by the listed canonical datasets |
| `/api/v1/stock_fnd/investor-relations` | `financial_data_first` | — | `primary_until_local_dataset_exists` | `canonical_dataset_required` | none |
| `/api/v1/stock_fnd/ipo-primary` | `financial_data_first` | — | `primary_until_local_dataset_exists` | `canonical_dataset_required` | none |
| `/api/v1/stock_fnd/ipo-quote-details` | `financial_data_first` | — | `primary_until_local_dataset_exists` | `canonical_dataset_required` | none |
| `/api/v1/stock_fnd/ipo-winning-numbers` | `financial_data_first` | — | `primary_until_local_dataset_exists` | `canonical_dataset_required` | none |
| `/api/v1/stock_fnd/listing-rules` | `financial_data_first` | — | `primary_until_local_dataset_exists` | `canonical_dataset_required` | none |
| `/api/v1/stock_fnd/litigation-arbitration` | `financial_data_first` | — | `primary_until_local_dataset_exists` | `canonical_dataset_required` | none |
| `/api/v1/stock_fnd/main-business-business` | `local_db_first` | `fina_mainbz` | `quota_fallback_after_local_miss` | `partial_ready_a_share_business_segments` | only requests whose market, asset, period and fields are covered by the listed canonical datasets |
| `/api/v1/stock_fnd/main-business-industry` | `local_db_first` | `fina_mainbz` | `quota_fallback_after_local_miss` | `partial_ready_a_share_business_segments` | only requests whose market, asset, period and fields are covered by the listed canonical datasets |
| `/api/v1/stock_fnd/main-business-product` | `local_db_first` | `fina_mainbz` | `quota_fallback_after_local_miss` | `partial_ready_a_share_business_segments` | only requests whose market, asset, period and fields are covered by the listed canonical datasets |
| `/api/v1/stock_fnd/main-business-region` | `local_db_first` | `fina_mainbz` | `quota_fallback_after_local_miss` | `partial_ready_a_share_business_segments` | only requests whose market, asset, period and fields are covered by the listed canonical datasets |
| `/api/v1/stock_fnd/metrics-ttm` | `local_db_first` | `financial_indicator` | `quota_fallback_after_local_miss` | `partial_ready_a_share_core_ttm_financials` | only requests whose market, asset, period and fields are covered by the listed canonical datasets |
| `/api/v1/stock_fnd/performance-forecast` | `local_db_first` | `forecast` | `quota_fallback_after_local_miss` | `partial_ready_a_share_core_forecast_fields` | only requests whose market, asset, period and fields are covered by the listed canonical datasets |
| `/api/v1/stock_fnd/prelim-acc` | `local_db_first` | `express` | `quota_fallback_after_local_miss` | `partial_ready_a_share_cumulative_preliminary_fields` | only requests whose market, asset, period and fields are covered by the listed canonical datasets |
| `/api/v1/stock_fnd/prelim-balance` | `local_db_first` | `express` | `quota_fallback_after_local_miss` | `adapter_required` | only requests whose market, asset, period and fields are covered by the listed canonical datasets |
| `/api/v1/stock_fnd/prelim-quarter` | `local_db_first` | `express` | `quota_fallback_after_local_miss` | `adapter_required` | only requests whose market, asset, period and fields are covered by the listed canonical datasets |
| `/api/v1/stock_fnd/rating-summary` | `financial_data_first` | — | `primary_until_local_dataset_exists` | `canonical_dataset_required` | none |
| `/api/v1/stock_fnd/regulatory-penalties` | `financial_data_first` | — | `primary_until_local_dataset_exists` | `canonical_dataset_required` | none |
| `/api/v1/stock_fnd/related-party-transactions` | `financial_data_first` | — | `primary_until_local_dataset_exists` | `canonical_dataset_required` | none |
| `/api/v1/stock_fnd/restricted-release-calendar` | `local_db_first` | `share_float` | `quota_fallback_after_local_miss` | `partial_ready_a_share_restricted_releases` | only requests whose market, asset, period and fields are covered by the listed canonical datasets |
| `/api/v1/stock_fnd/review-process` | `financial_data_first` | — | `primary_until_local_dataset_exists` | `canonical_dataset_required` | none |
| `/api/v1/stock_fnd/risk-factor-csi300` | `financial_data_first` | — | `primary_until_local_dataset_exists` | `canonical_dataset_required` | none |
| `/api/v1/stock_fnd/risk-factor-csi500` | `financial_data_first` | — | `primary_until_local_dataset_exists` | `canonical_dataset_required` | none |
| `/api/v1/stock_fnd/risk-factor-sh000001` | `financial_data_first` | — | `primary_until_local_dataset_exists` | `canonical_dataset_required` | none |
| `/api/v1/stock_fnd/risk-factor-sw` | `financial_data_first` | — | `primary_until_local_dataset_exists` | `canonical_dataset_required` | none |
| `/api/v1/stock_fnd/seo-placement-details` | `financial_data_first` | — | `primary_until_local_dataset_exists` | `canonical_dataset_required` | none |
| `/api/v1/stock_fnd/shareholder-commitment` | `financial_data_first` | — | `primary_until_local_dataset_exists` | `canonical_dataset_required` | none |
| `/api/v1/stock_fnd/shareholder-list` | `local_db_first` | `top10_holders`, `top10_floatholders` | `quota_fallback_after_local_miss` | `partial_ready_a_share_major_shareholders` | only requests whose market, asset, period and fields are covered by the listed canonical datasets |
| `/api/v1/stock_fnd/shareholder-meeting` | `financial_data_first` | — | `primary_until_local_dataset_exists` | `canonical_dataset_required` | none |
| `/api/v1/stock_fnd/specialty-metrics-period` | `financial_data_first` | — | `primary_until_local_dataset_exists` | `canonical_dataset_required` | none |
| `/api/v1/stock_fnd/specialty-metrics-point` | `financial_data_first` | — | `primary_until_local_dataset_exists` | `canonical_dataset_required` | none |
| `/api/v1/stock_fnd/stock-basic-info` | `local_db_first` | `stock_basic`, `stock_company` | `quota_fallback_after_local_miss` | `partial_ready_a_share_identity_fields` | only requests whose market, asset, period and fields are covered by the listed canonical datasets |
| `/api/v1/stock_fnd/stock-rel-fund-holdings-top` | `local_db_first` | `fund_portfolio` | `quota_fallback_after_local_miss` | `adapter_required` | only requests whose market, asset, period and fields are covered by the listed canonical datasets |
| `/api/v1/stock_fnd/style-classification` | `financial_data_first` | — | `primary_until_local_dataset_exists` | `canonical_dataset_required` | none |
| `/api/v1/stock_fnd/takeover-offers` | `financial_data_first` | — | `primary_until_local_dataset_exists` | `canonical_dataset_required` | none |
| `/api/v1/stock_fnd/target-price` | `financial_data_first` | — | `primary_until_local_dataset_exists` | `canonical_dataset_required` | none |
| `/api/v1/stock_fnd/tender-offers` | `financial_data_first` | — | `primary_until_local_dataset_exists` | `canonical_dataset_required` | none |
| `/api/v1/stock_fnd/yield-factor` | `financial_data_first` | — | `primary_until_local_dataset_exists` | `canonical_dataset_required` | none |
| `/api/v1/stock_sh_equity/freeze-pledge` | `local_db_first` | `pledge_detail`, `pledge_stat` | `quota_fallback_after_local_miss` | `partial_ready_a_share_pledge_events` | only requests whose market, asset, period and fields are covered by the listed canonical datasets |
| `/api/v1/us_stock/adr-ratio-changes` | `financial_data_first` | — | `primary_until_local_dataset_exists` | `canonical_dataset_required` | none |
| `/api/v1/us_stock/capital-events` | `financial_data_first` | — | `primary_until_local_dataset_exists` | `canonical_dataset_required` | none |
| `/api/v1/us_stock/company-ownership` | `financial_data_first` | — | `primary_until_local_dataset_exists` | `canonical_dataset_required` | none |
| `/api/v1/us_stock/concept-components` | `financial_data_first` | — | `primary_until_local_dataset_exists` | `canonical_dataset_required` | none |
| `/api/v1/us_stock/dividends` | `financial_data_first` | — | `primary_until_local_dataset_exists` | `canonical_dataset_required` | none |
| `/api/v1/us_stock/equity-structure` | `financial_data_first` | — | `primary_until_local_dataset_exists` | `canonical_dataset_required` | none |
| `/api/v1/us_stock/ratings` | `financial_data_first` | — | `primary_until_local_dataset_exists` | `canonical_dataset_required` | none |
| `/api/v1/us_stock/security-markings` | `financial_data_first` | — | `primary_until_local_dataset_exists` | `canonical_dataset_required` | none |
| `/api/v1/us_stock/target-price` | `financial_data_first` | — | `primary_until_local_dataset_exists` | `canonical_dataset_required` | none |
| `/api/v2/info/news/article` | `financial_data_first` | — | `primary_until_local_dataset_exists` | `canonical_dataset_required` | none |
| `/api/v2/info/news/search_evidence` | `financial_data_first` | — | `primary_until_local_dataset_exists` | `canonical_dataset_required` | none |
