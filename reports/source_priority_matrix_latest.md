# 数据源优先级矩阵

> 生成时间：`2026-10-01T14:50:23.052294+00:00`。机器可读版本见 [`source_priority_matrix_latest.json`](source_priority_matrix_latest.json)。

## 统一规则

- 外部消费者使用规范数据集或研究接口，不直接依赖供应商字段。
- `local_db_first`：先读已经由 Tushare 定时采集并写入 DB 的规范数据；只有请求切片缺失或超过新鲜度 SLA，且 Financial Data 规范适配器通过契约测试后，才允许消耗额度回退。
- `financial_data_first`：当前没有等价本地规范数据集，或能力本身是显式实时查询；当前只能显式调用供应商网关；若要进入规范/研究接口，必须先完成字段、代码、日期和单位适配。
- 当前隐式回退数为 **0**。仅规范接口可触发已通过测试的有限回退；`adapter_required` 不是已启用，避免供应商原生模型混入统一接口。

## 汇总

| Financial Data 路由 | 当前依赖 Financial Data | 实时必须依赖 | 无本地规范等价 | 本地优先且可回退 | 本地重叠但适配待完成 |
|---:|---:|---:|---:|---:|---:|
| 163 | 106 | 4 | 102 | 29 | 28 |

> “无本地规范等价”描述的是当前系统状态，不等同于已经证明 Tushare 完全没有语义相近接口；其中也可能有尚未完成映射和标准化的缺口。

## 完整路由清单

| 路由 | 依赖分类 | 当前必须依赖 FD | 对外访问 | 本地规范数据集 | 规范化状态 |
|---|---|---|---|---|---|
| `/api/v1/altdata/hot-plate-rank` | `financial_data_primary_no_local_canonical` | 是 | `explicit_provider_gateway_only` | — | `canonical_dataset_required` |
| `/api/v1/altdata/hot-stock-rank` | `financial_data_primary_no_local_canonical` | 是 | `explicit_provider_gateway_only` | — | `canonical_dataset_required` |
| `/api/v1/common/entity_relationship` | `financial_data_primary_no_local_canonical` | 是 | `explicit_provider_gateway_only` | — | `canonical_dataset_required` |
| `/api/v1/common/industry-chain-tree` | `financial_data_primary_no_local_canonical` | 是 | `explicit_provider_gateway_only` | — | `canonical_dataset_required` |
| `/api/v1/common/stock-belong-industry-chain` | `financial_data_primary_no_local_canonical` | 是 | `explicit_provider_gateway_only` | — | `canonical_dataset_required` |
| `/api/v1/common/symbol-by-cond` | `local_overlap_adapter_pending` | 否 | `local_dataset_or_explicit_provider_gateway` | `stock_basic`, `fund_basic`, `index_basic`, `hk_basic`, `us_basic`, `sge_basic` | `adapter_required` |
| `/api/v1/common/trading-day` | `local_first_canonical_fallback_ready` | 否 | `canonical_api_with_bounded_fallback` | `trade_calendar`, `hk_tradecal`, `us_tradecal`, `fut_trade_cal` | `partial_ready_a_share` |
| `/api/v1/common/trading-state` | `financial_data_realtime_required` | 是 | `explicit_provider_gateway_only` | — | `canonical_dataset_required` |
| `/api/v1/fund/asset-allocation` | `financial_data_primary_no_local_canonical` | 是 | `explicit_provider_gateway_only` | — | `canonical_dataset_required` |
| `/api/v1/fund/bond-portfolio` | `financial_data_primary_no_local_canonical` | 是 | `explicit_provider_gateway_only` | — | `canonical_dataset_required` |
| `/api/v1/fund/dividend` | `local_first_canonical_fallback_ready` | 否 | `canonical_api_with_bounded_fallback` | `fund_div` | `partial_ready_fund_cash_dividends` |
| `/api/v1/fund/fund-archive` | `local_first_canonical_fallback_ready` | 否 | `canonical_api_with_bounded_fallback` | `fund_basic` | `partial_ready_common_profile_fields` |
| `/api/v1/fund/fund-charge-rate` | `financial_data_primary_no_local_canonical` | 是 | `explicit_provider_gateway_only` | — | `canonical_dataset_required` |
| `/api/v1/fund/fund-company-info` | `local_overlap_adapter_pending` | 否 | `local_dataset_or_explicit_provider_gateway` | `fund_company` | `adapter_required` |
| `/api/v1/fund/fund-manager` | `local_first_canonical_fallback_ready` | 否 | `canonical_api_with_bounded_fallback` | `fund_manager` | `partial_ready_fund_manager_tenures` |
| `/api/v1/fund/fund-portfolio` | `financial_data_primary_no_local_canonical` | 是 | `explicit_provider_gateway_only` | — | `canonical_dataset_required` |
| `/api/v1/fund/invest-industry` | `financial_data_primary_no_local_canonical` | 是 | `explicit_provider_gateway_only` | — | `canonical_dataset_required` |
| `/api/v1/fund/net-value` | `local_first_canonical_fallback_ready` | 否 | `canonical_api_with_bounded_fallback` | `fund_nav`, `fund_daily` | `partial_ready_bounded_nav_range` |
| `/api/v1/fund/plate-fund-relevancy` | `financial_data_primary_no_local_canonical` | 是 | `explicit_provider_gateway_only` | — | `canonical_dataset_required` |
| `/api/v1/fund/share-split` | `local_overlap_adapter_pending` | 否 | `local_dataset_or_explicit_provider_gateway` | `fund_adj` | `adapter_required` |
| `/api/v1/fund/stock-portfolio` | `local_first_canonical_fallback_ready` | 否 | `canonical_api_with_bounded_fallback` | `fund_portfolio` | `partial_ready_quarterly_stock_holdings` |
| `/api/v1/fund/trade-limit` | `financial_data_primary_no_local_canonical` | 是 | `explicit_provider_gateway_only` | — | `canonical_dataset_required` |
| `/api/v1/fund/yield-rank` | `financial_data_primary_no_local_canonical` | 是 | `explicit_provider_gateway_only` | — | `canonical_dataset_required` |
| `/api/v1/fund_derived/benchmark-excess` | `local_overlap_adapter_pending` | 否 | `local_dataset_or_explicit_provider_gateway` | `fund_daily`, `fund_nav`, `index_daily` | `adapter_required` |
| `/api/v1/fund_derived/risk-return` | `local_overlap_adapter_pending` | 否 | `local_dataset_or_explicit_provider_gateway` | `fund_daily`, `fund_nav` | `adapter_required` |
| `/api/v1/hk_stock/adr-conversion-ratio` | `financial_data_primary_no_local_canonical` | 是 | `explicit_provider_gateway_only` | — | `canonical_dataset_required` |
| `/api/v1/hk_stock/equity-structure` | `financial_data_primary_no_local_canonical` | 是 | `explicit_provider_gateway_only` | — | `canonical_dataset_required` |
| `/api/v1/hk_stock/free-float` | `financial_data_primary_no_local_canonical` | 是 | `explicit_provider_gateway_only` | — | `canonical_dataset_required` |
| `/api/v1/hk_stock/high-shareholding-concentration` | `financial_data_primary_no_local_canonical` | 是 | `explicit_provider_gateway_only` | — | `canonical_dataset_required` |
| `/api/v1/hk_stock/ipo-key-indicators` | `financial_data_primary_no_local_canonical` | 是 | `explicit_provider_gateway_only` | — | `canonical_dataset_required` |
| `/api/v1/hk_stock/ratings` | `financial_data_primary_no_local_canonical` | 是 | `explicit_provider_gateway_only` | — | `canonical_dataset_required` |
| `/api/v1/hk_stock/restricted-share-unlock-schedule` | `financial_data_primary_no_local_canonical` | 是 | `explicit_provider_gateway_only` | — | `canonical_dataset_required` |
| `/api/v1/hk_stock/risk-list` | `financial_data_primary_no_local_canonical` | 是 | `explicit_provider_gateway_only` | — | `canonical_dataset_required` |
| `/api/v1/hk_stock/shareholding-changes` | `financial_data_primary_no_local_canonical` | 是 | `explicit_provider_gateway_only` | — | `canonical_dataset_required` |
| `/api/v1/hk_stock/short-position-statistics` | `financial_data_primary_no_local_canonical` | 是 | `explicit_provider_gateway_only` | — | `canonical_dataset_required` |
| `/api/v1/hk_stock/short-selling` | `financial_data_primary_no_local_canonical` | 是 | `explicit_provider_gateway_only` | — | `canonical_dataset_required` |
| `/api/v1/hk_stock/special-notices` | `financial_data_primary_no_local_canonical` | 是 | `explicit_provider_gateway_only` | — | `canonical_dataset_required` |
| `/api/v1/hk_stock/special-securities` | `financial_data_primary_no_local_canonical` | 是 | `explicit_provider_gateway_only` | — | `canonical_dataset_required` |
| `/api/v1/hk_stock/suspend-resumption` | `financial_data_primary_no_local_canonical` | 是 | `explicit_provider_gateway_only` | — | `canonical_dataset_required` |
| `/api/v1/hk_stock/target-price` | `financial_data_primary_no_local_canonical` | 是 | `explicit_provider_gateway_only` | — | `canonical_dataset_required` |
| `/api/v1/hk_stock/temporary-parallel-trading` | `financial_data_primary_no_local_canonical` | 是 | `explicit_provider_gateway_only` | — | `canonical_dataset_required` |
| `/api/v1/index_fnd/index-constituents-list-weight` | `local_first_canonical_fallback_ready` | 否 | `canonical_api_with_bounded_fallback` | `index_weight`, `index_member_all` | `partial_ready_sh_sz_weighted_constituents` |
| `/api/v1/index_fnd/index-fnd-estimates-summary` | `financial_data_primary_no_local_canonical` | 是 | `explicit_provider_gateway_only` | — | `canonical_dataset_required` |
| `/api/v1/index_fnd/index-fnd-financial-ratios` | `financial_data_primary_no_local_canonical` | 是 | `explicit_provider_gateway_only` | — | `canonical_dataset_required` |
| `/api/v1/index_fnd/index-fnd-financial-ratios-single` | `financial_data_primary_no_local_canonical` | 是 | `explicit_provider_gateway_only` | — | `canonical_dataset_required` |
| `/api/v1/index_fnd/index-fnd-financial-statement` | `financial_data_primary_no_local_canonical` | 是 | `explicit_provider_gateway_only` | — | `canonical_dataset_required` |
| `/api/v1/index_fnd/index-profile-basic-info` | `local_first_canonical_fallback_ready` | 否 | `canonical_api_with_bounded_fallback` | `index_basic` | `partial_ready_sh_sz_index_profile` |
| `/api/v1/info/announcements` | `financial_data_primary_no_local_canonical` | 是 | `explicit_provider_gateway_only` | — | `canonical_dataset_required` |
| `/api/v1/info/news-global-search` | `financial_data_primary_no_local_canonical` | 是 | `explicit_provider_gateway_only` | — | `canonical_dataset_required` |
| `/api/v1/info/research-reports` | `local_overlap_adapter_pending` | 否 | `local_dataset_or_explicit_provider_gateway` | `report_rc` | `adapter_required` |
| `/api/v1/info/tag/category` | `financial_data_primary_no_local_canonical` | 是 | `explicit_provider_gateway_only` | — | `canonical_dataset_required` |
| `/api/v1/info/tag/query` | `financial_data_primary_no_local_canonical` | 是 | `explicit_provider_gateway_only` | — | `canonical_dataset_required` |
| `/api/v1/macro/data-query` | `local_overlap_adapter_pending` | 否 | `local_dataset_or_explicit_provider_gateway` | `cn_cpi`, `cn_gdp`, `cn_m`, `cn_pmi`, `cn_ppi`, `sf_month`, `shibor`, `shibor_lpr`, `libor`, `hibor`, `us_tbr`, `us_tltr`, `us_trltr`, `us_trycr`, `us_tycr` | `adapter_required` |
| `/api/v1/macro/meta-search` | `financial_data_primary_no_local_canonical` | 是 | `explicit_provider_gateway_only` | — | `canonical_dataset_required` |
| `/api/v1/onecode/query` | `local_overlap_adapter_pending` | 否 | `local_dataset_or_explicit_provider_gateway` | `stock_daily`, `stock_daily_basic`, `index_daily`, `fund_daily`, `fund_nav`, `financial_indicator` | `adapter_required` |
| `/api/v1/onecode/recall` | `financial_data_primary_no_local_canonical` | 是 | `explicit_provider_gateway_only` | — | `canonical_dataset_required` |
| `/api/v1/quote/auction-snapshot` | `financial_data_realtime_required` | 是 | `explicit_provider_gateway_only` | — | `canonical_dataset_required` |
| `/api/v1/quote/basic-snapshot` | `financial_data_realtime_required` | 是 | `explicit_provider_gateway_only` | — | `canonical_dataset_required` |
| `/api/v1/quote/capital-flow-range` | `local_overlap_adapter_pending` | 否 | `local_dataset_or_explicit_provider_gateway` | `moneyflow`, `moneyflow_dc`, `moneyflow_ths`, `moneyflow_ind_dc`, `moneyflow_ind_ths`, `moneyflow_mkt_dc` | `adapter_required` |
| `/api/v1/quote/derived-snapshot` | `financial_data_realtime_required` | 是 | `explicit_provider_gateway_only` | — | `canonical_dataset_required` |
| `/api/v1/quote/kline-batch` | `local_first_canonical_fallback_ready` | 否 | `canonical_api_with_bounded_fallback` | `stock_daily`, `index_daily`, `index_weekly`, `index_monthly`, `fund_daily`, `hk_daily`, `sge_daily`, `fut_daily`, `opt_daily`, `cb_daily`, `forex_daily` | `partial_ready_a_share_daily_unadjusted` |
| `/api/v1/sector/plate-component` | `local_overlap_adapter_pending` | 否 | `local_dataset_or_explicit_provider_gateway` | `ths_member`, `dc_member`, `tdx_member`, `index_member_all` | `adapter_required` |
| `/api/v1/sector/plate-fund-relevancy` | `financial_data_primary_no_local_canonical` | 是 | `explicit_provider_gateway_only` | — | `canonical_dataset_required` |
| `/api/v1/sector/plate-list` | `local_overlap_adapter_pending` | 否 | `local_dataset_or_explicit_provider_gateway` | `ths_index`, `dc_index`, `tdx_index`, `index_classify` | `adapter_required` |
| `/api/v1/sector/sector-capital-flow` | `local_overlap_adapter_pending` | 否 | `local_dataset_or_explicit_provider_gateway` | `moneyflow_ind_dc`, `moneyflow_ind_ths`, `margin`, `margin_detail` | `adapter_required` |
| `/api/v1/sector/sector-financial-cumulative` | `financial_data_primary_no_local_canonical` | 是 | `explicit_provider_gateway_only` | — | `canonical_dataset_required` |
| `/api/v1/sector/sector-financial-point` | `financial_data_primary_no_local_canonical` | 是 | `explicit_provider_gateway_only` | — | `canonical_dataset_required` |
| `/api/v1/sector/sector-financial-quarterly` | `financial_data_primary_no_local_canonical` | 是 | `explicit_provider_gateway_only` | — | `canonical_dataset_required` |
| `/api/v1/sector/sector-valuation` | `local_overlap_adapter_pending` | 否 | `local_dataset_or_explicit_provider_gateway` | `index_dailybasic` | `adapter_required` |
| `/api/v1/stock/after-daily-quote` | `financial_data_primary_no_local_canonical` | 是 | `explicit_provider_gateway_only` | — | `canonical_dataset_required` |
| `/api/v1/stock/ashare-cdr-conversion-ratio` | `financial_data_primary_no_local_canonical` | 是 | `explicit_provider_gateway_only` | — | `canonical_dataset_required` |
| `/api/v1/stock/block-trading-details` | `local_overlap_adapter_pending` | 否 | `local_dataset_or_explicit_provider_gateway` | `block_trade` | `adapter_required` |
| `/api/v1/stock/change-plan` | `financial_data_primary_no_local_canonical` | 是 | `explicit_provider_gateway_only` | — | `canonical_dataset_required` |
| `/api/v1/stock/component-list-belonged` | `local_overlap_adapter_pending` | 否 | `local_dataset_or_explicit_provider_gateway` | `index_member_all`, `ths_member`, `dc_member`, `tdx_member` | `adapter_required` |
| `/api/v1/stock/daily-valuation-indicators` | `local_first_canonical_fallback_ready` | 否 | `canonical_api_with_bounded_fallback` | `stock_daily_basic` | `partial_ready_a_share_daily_core_fields` |
| `/api/v1/stock/market-detail` | `financial_data_primary_no_local_canonical` | 是 | `explicit_provider_gateway_only` | — | `canonical_dataset_required` |
| `/api/v1/stock/risk-alerts` | `local_first_canonical_fallback_ready` | 否 | `canonical_api_with_bounded_fallback` | `stk_alert`, `stock_st` | `partial_ready_a_share_risk_alerts` |
| `/api/v1/stock/sc-activitie` | `financial_data_primary_no_local_canonical` | 是 | `explicit_provider_gateway_only` | — | `canonical_dataset_required` |
| `/api/v1/stock/sc-trade` | `financial_data_primary_no_local_canonical` | 是 | `explicit_provider_gateway_only` | — | `canonical_dataset_required` |
| `/api/v1/stock/sh-hold-stat` | `local_overlap_adapter_pending` | 否 | `local_dataset_or_explicit_provider_gateway` | `hk_hold`, `stock_hsgt` | `adapter_required` |
| `/api/v1/stock/stock-index-constituents-list` | `local_overlap_adapter_pending` | 否 | `local_dataset_or_explicit_provider_gateway` | `index_member_all`, `index_weight` | `adapter_required` |
| `/api/v1/stock/suspend-resumption` | `local_first_canonical_fallback_ready` | 否 | `canonical_api_with_bounded_fallback` | `stock_suspend` | `partial_ready_a_share_suspensions` |
| `/api/v1/stock/tech-indicators` | `local_overlap_adapter_pending` | 否 | `local_dataset_or_explicit_provider_gateway` | `stock_daily`, `adj_factor`, `stk_factor`, `stk_factor_pro` | `adapter_required` |
| `/api/v1/stock/tech-patterns` | `local_overlap_adapter_pending` | 否 | `local_dataset_or_explicit_provider_gateway` | `stock_daily`, `adj_factor` | `adapter_required` |
| `/api/v1/stock/tra-variant` | `financial_data_primary_no_local_canonical` | 是 | `explicit_provider_gateway_only` | — | `canonical_dataset_required` |
| `/api/v1/stock_fnd/actual-controller` | `financial_data_primary_no_local_canonical` | 是 | `explicit_provider_gateway_only` | — | `canonical_dataset_required` |
| `/api/v1/stock_fnd/asset-restructuring` | `financial_data_primary_no_local_canonical` | 是 | `explicit_provider_gateway_only` | — | `canonical_dataset_required` |
| `/api/v1/stock_fnd/balance-sheet` | `local_first_canonical_fallback_ready` | 否 | `canonical_api_with_bounded_fallback` | `balancesheet` | `partial_ready_a_share_balance_core_fields` |
| `/api/v1/stock_fnd/broker-golden-stocks` | `local_overlap_adapter_pending` | 否 | `local_dataset_or_explicit_provider_gateway` | `broker_recommend` | `adapter_required` |
| `/api/v1/stock_fnd/buyback-plans` | `local_first_canonical_fallback_ready` | 否 | `canonical_api_with_bounded_fallback` | `repurchase` | `partial_ready_a_share_repurchase_plan_fields` |
| `/api/v1/stock_fnd/concert-parties` | `financial_data_primary_no_local_canonical` | 是 | `explicit_provider_gateway_only` | — | `canonical_dataset_required` |
| `/api/v1/stock_fnd/consensus-details` | `financial_data_primary_no_local_canonical` | 是 | `explicit_provider_gateway_only` | — | `canonical_dataset_required` |
| `/api/v1/stock_fnd/consensus-stats` | `financial_data_primary_no_local_canonical` | 是 | `explicit_provider_gateway_only` | — | `canonical_dataset_required` |
| `/api/v1/stock_fnd/controlling-shareholder` | `financial_data_primary_no_local_canonical` | 是 | `explicit_provider_gateway_only` | — | `canonical_dataset_required` |
| `/api/v1/stock_fnd/delisting-info` | `financial_data_primary_no_local_canonical` | 是 | `explicit_provider_gateway_only` | — | `canonical_dataset_required` |
| `/api/v1/stock_fnd/depository-receipt` | `financial_data_primary_no_local_canonical` | 是 | `explicit_provider_gateway_only` | — | `canonical_dataset_required` |
| `/api/v1/stock_fnd/dividend-details` | `local_first_canonical_fallback_ready` | 否 | `canonical_api_with_bounded_fallback` | `dividend` | `partial_ready_a_share_core_dividend_fields` |
| `/api/v1/stock_fnd/dividend-record` | `local_overlap_adapter_pending` | 否 | `local_dataset_or_explicit_provider_gateway` | `dividend` | `adapter_required` |
| `/api/v1/stock_fnd/employee-ownership-plan` | `financial_data_primary_no_local_canonical` | 是 | `explicit_provider_gateway_only` | — | `canonical_dataset_required` |
| `/api/v1/stock_fnd/equity-structure` | `financial_data_primary_no_local_canonical` | 是 | `explicit_provider_gateway_only` | — | `canonical_dataset_required` |
| `/api/v1/stock_fnd/executive-compensation` | `local_overlap_adapter_pending` | 否 | `local_dataset_or_explicit_provider_gateway` | `stk_rewards` | `adapter_required` |
| `/api/v1/stock_fnd/free-float` | `financial_data_primary_no_local_canonical` | 是 | `explicit_provider_gateway_only` | — | `canonical_dataset_required` |
| `/api/v1/stock_fnd/fund-raising-usage` | `financial_data_primary_no_local_canonical` | 是 | `explicit_provider_gateway_only` | — | `canonical_dataset_required` |
| `/api/v1/stock_fnd/growth-rates-acc` | `local_first_canonical_fallback_ready` | 否 | `canonical_api_with_bounded_fallback` | `financial_indicator` | `partial_ready_a_share_core_financial_metrics` |
| `/api/v1/stock_fnd/growth-rates-quarter` | `local_overlap_adapter_pending` | 否 | `local_dataset_or_explicit_provider_gateway` | `income`, `cashflow`, `financial_indicator` | `adapter_required` |
| `/api/v1/stock_fnd/guarantee-events` | `financial_data_primary_no_local_canonical` | 是 | `explicit_provider_gateway_only` | — | `canonical_dataset_required` |
| `/api/v1/stock_fnd/guarantee-stats` | `financial_data_primary_no_local_canonical` | 是 | `explicit_provider_gateway_only` | — | `canonical_dataset_required` |
| `/api/v1/stock_fnd/hk-intermediary-holdings` | `financial_data_primary_no_local_canonical` | 是 | `explicit_provider_gateway_only` | — | `canonical_dataset_required` |
| `/api/v1/stock_fnd/holder-count` | `local_first_canonical_fallback_ready` | 否 | `canonical_api_with_bounded_fallback` | `stk_holdernumber` | `partial_ready_a_share_holder_count_fields` |
| `/api/v1/stock_fnd/holding-stats` | `financial_data_primary_no_local_canonical` | 是 | `explicit_provider_gateway_only` | — | `canonical_dataset_required` |
| `/api/v1/stock_fnd/holding-subsidiaries` | `financial_data_primary_no_local_canonical` | 是 | `explicit_provider_gateway_only` | — | `canonical_dataset_required` |
| `/api/v1/stock_fnd/income-cashflow-acc` | `local_first_canonical_fallback_ready` | 否 | `canonical_api_with_bounded_fallback` | `income`, `cashflow` | `partial_ready_a_share_cumulative_core_fields` |
| `/api/v1/stock_fnd/income-cashflow-single` | `local_overlap_adapter_pending` | 否 | `local_dataset_or_explicit_provider_gateway` | `income`, `cashflow` | `adapter_required` |
| `/api/v1/stock_fnd/industry-classification` | `local_overlap_adapter_pending` | 否 | `local_dataset_or_explicit_provider_gateway` | `stock_basic`, `index_classify` | `adapter_required` |
| `/api/v1/stock_fnd/investor-relations` | `financial_data_primary_no_local_canonical` | 是 | `explicit_provider_gateway_only` | — | `canonical_dataset_required` |
| `/api/v1/stock_fnd/ipo-primary` | `financial_data_primary_no_local_canonical` | 是 | `explicit_provider_gateway_only` | — | `canonical_dataset_required` |
| `/api/v1/stock_fnd/ipo-quote-details` | `financial_data_primary_no_local_canonical` | 是 | `explicit_provider_gateway_only` | — | `canonical_dataset_required` |
| `/api/v1/stock_fnd/ipo-winning-numbers` | `financial_data_primary_no_local_canonical` | 是 | `explicit_provider_gateway_only` | — | `canonical_dataset_required` |
| `/api/v1/stock_fnd/listing-rules` | `financial_data_primary_no_local_canonical` | 是 | `explicit_provider_gateway_only` | — | `canonical_dataset_required` |
| `/api/v1/stock_fnd/litigation-arbitration` | `financial_data_primary_no_local_canonical` | 是 | `explicit_provider_gateway_only` | — | `canonical_dataset_required` |
| `/api/v1/stock_fnd/main-business-business` | `local_first_canonical_fallback_ready` | 否 | `canonical_api_with_bounded_fallback` | `fina_mainbz` | `partial_ready_a_share_business_segments` |
| `/api/v1/stock_fnd/main-business-industry` | `local_first_canonical_fallback_ready` | 否 | `canonical_api_with_bounded_fallback` | `fina_mainbz` | `partial_ready_a_share_business_segments` |
| `/api/v1/stock_fnd/main-business-product` | `local_first_canonical_fallback_ready` | 否 | `canonical_api_with_bounded_fallback` | `fina_mainbz` | `partial_ready_a_share_business_segments` |
| `/api/v1/stock_fnd/main-business-region` | `local_first_canonical_fallback_ready` | 否 | `canonical_api_with_bounded_fallback` | `fina_mainbz` | `partial_ready_a_share_business_segments` |
| `/api/v1/stock_fnd/metrics-ttm` | `local_first_canonical_fallback_ready` | 否 | `canonical_api_with_bounded_fallback` | `financial_indicator` | `partial_ready_a_share_core_ttm_financials` |
| `/api/v1/stock_fnd/performance-forecast` | `local_first_canonical_fallback_ready` | 否 | `canonical_api_with_bounded_fallback` | `forecast` | `partial_ready_a_share_core_forecast_fields` |
| `/api/v1/stock_fnd/prelim-acc` | `local_first_canonical_fallback_ready` | 否 | `canonical_api_with_bounded_fallback` | `express` | `partial_ready_a_share_cumulative_preliminary_fields` |
| `/api/v1/stock_fnd/prelim-balance` | `local_overlap_adapter_pending` | 否 | `local_dataset_or_explicit_provider_gateway` | `express` | `adapter_required` |
| `/api/v1/stock_fnd/prelim-quarter` | `local_overlap_adapter_pending` | 否 | `local_dataset_or_explicit_provider_gateway` | `express` | `adapter_required` |
| `/api/v1/stock_fnd/rating-summary` | `financial_data_primary_no_local_canonical` | 是 | `explicit_provider_gateway_only` | — | `canonical_dataset_required` |
| `/api/v1/stock_fnd/regulatory-penalties` | `financial_data_primary_no_local_canonical` | 是 | `explicit_provider_gateway_only` | — | `canonical_dataset_required` |
| `/api/v1/stock_fnd/related-party-transactions` | `financial_data_primary_no_local_canonical` | 是 | `explicit_provider_gateway_only` | — | `canonical_dataset_required` |
| `/api/v1/stock_fnd/restricted-release-calendar` | `local_first_canonical_fallback_ready` | 否 | `canonical_api_with_bounded_fallback` | `share_float` | `partial_ready_a_share_restricted_releases` |
| `/api/v1/stock_fnd/review-process` | `financial_data_primary_no_local_canonical` | 是 | `explicit_provider_gateway_only` | — | `canonical_dataset_required` |
| `/api/v1/stock_fnd/risk-factor-csi300` | `financial_data_primary_no_local_canonical` | 是 | `explicit_provider_gateway_only` | — | `canonical_dataset_required` |
| `/api/v1/stock_fnd/risk-factor-csi500` | `financial_data_primary_no_local_canonical` | 是 | `explicit_provider_gateway_only` | — | `canonical_dataset_required` |
| `/api/v1/stock_fnd/risk-factor-sh000001` | `financial_data_primary_no_local_canonical` | 是 | `explicit_provider_gateway_only` | — | `canonical_dataset_required` |
| `/api/v1/stock_fnd/risk-factor-sw` | `financial_data_primary_no_local_canonical` | 是 | `explicit_provider_gateway_only` | — | `canonical_dataset_required` |
| `/api/v1/stock_fnd/seo-placement-details` | `financial_data_primary_no_local_canonical` | 是 | `explicit_provider_gateway_only` | — | `canonical_dataset_required` |
| `/api/v1/stock_fnd/shareholder-commitment` | `financial_data_primary_no_local_canonical` | 是 | `explicit_provider_gateway_only` | — | `canonical_dataset_required` |
| `/api/v1/stock_fnd/shareholder-list` | `local_first_canonical_fallback_ready` | 否 | `canonical_api_with_bounded_fallback` | `top10_holders`, `top10_floatholders` | `partial_ready_a_share_major_shareholders` |
| `/api/v1/stock_fnd/shareholder-meeting` | `financial_data_primary_no_local_canonical` | 是 | `explicit_provider_gateway_only` | — | `canonical_dataset_required` |
| `/api/v1/stock_fnd/specialty-metrics-period` | `financial_data_primary_no_local_canonical` | 是 | `explicit_provider_gateway_only` | — | `canonical_dataset_required` |
| `/api/v1/stock_fnd/specialty-metrics-point` | `financial_data_primary_no_local_canonical` | 是 | `explicit_provider_gateway_only` | — | `canonical_dataset_required` |
| `/api/v1/stock_fnd/stock-basic-info` | `local_first_canonical_fallback_ready` | 否 | `canonical_api_with_bounded_fallback` | `stock_basic`, `stock_company` | `partial_ready_a_share_identity_fields` |
| `/api/v1/stock_fnd/stock-rel-fund-holdings-top` | `local_overlap_adapter_pending` | 否 | `local_dataset_or_explicit_provider_gateway` | `fund_portfolio` | `adapter_required` |
| `/api/v1/stock_fnd/style-classification` | `financial_data_primary_no_local_canonical` | 是 | `explicit_provider_gateway_only` | — | `canonical_dataset_required` |
| `/api/v1/stock_fnd/takeover-offers` | `financial_data_primary_no_local_canonical` | 是 | `explicit_provider_gateway_only` | — | `canonical_dataset_required` |
| `/api/v1/stock_fnd/target-price` | `financial_data_primary_no_local_canonical` | 是 | `explicit_provider_gateway_only` | — | `canonical_dataset_required` |
| `/api/v1/stock_fnd/tender-offers` | `financial_data_primary_no_local_canonical` | 是 | `explicit_provider_gateway_only` | — | `canonical_dataset_required` |
| `/api/v1/stock_fnd/yield-factor` | `financial_data_primary_no_local_canonical` | 是 | `explicit_provider_gateway_only` | — | `canonical_dataset_required` |
| `/api/v1/stock_sh_equity/freeze-pledge` | `local_first_canonical_fallback_ready` | 否 | `canonical_api_with_bounded_fallback` | `pledge_detail`, `pledge_stat` | `partial_ready_a_share_pledge_events` |
| `/api/v1/us_stock/adr-ratio-changes` | `financial_data_primary_no_local_canonical` | 是 | `explicit_provider_gateway_only` | — | `canonical_dataset_required` |
| `/api/v1/us_stock/capital-events` | `financial_data_primary_no_local_canonical` | 是 | `explicit_provider_gateway_only` | — | `canonical_dataset_required` |
| `/api/v1/us_stock/company-ownership` | `financial_data_primary_no_local_canonical` | 是 | `explicit_provider_gateway_only` | — | `canonical_dataset_required` |
| `/api/v1/us_stock/concept-components` | `financial_data_primary_no_local_canonical` | 是 | `explicit_provider_gateway_only` | — | `canonical_dataset_required` |
| `/api/v1/us_stock/dividends` | `financial_data_primary_no_local_canonical` | 是 | `explicit_provider_gateway_only` | — | `canonical_dataset_required` |
| `/api/v1/us_stock/equity-structure` | `financial_data_primary_no_local_canonical` | 是 | `explicit_provider_gateway_only` | — | `canonical_dataset_required` |
| `/api/v1/us_stock/ratings` | `financial_data_primary_no_local_canonical` | 是 | `explicit_provider_gateway_only` | — | `canonical_dataset_required` |
| `/api/v1/us_stock/security-markings` | `financial_data_primary_no_local_canonical` | 是 | `explicit_provider_gateway_only` | — | `canonical_dataset_required` |
| `/api/v1/us_stock/target-price` | `financial_data_primary_no_local_canonical` | 是 | `explicit_provider_gateway_only` | — | `canonical_dataset_required` |
| `/api/v2/info/news/article` | `financial_data_primary_no_local_canonical` | 是 | `explicit_provider_gateway_only` | — | `canonical_dataset_required` |
| `/api/v2/info/news/search_evidence` | `financial_data_primary_no_local_canonical` | 是 | `explicit_provider_gateway_only` | — | `canonical_dataset_required` |
