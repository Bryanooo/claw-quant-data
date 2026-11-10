# 全量数据集严格审计报告

生成时间：`2026-11-10T21:50:50.128993+08:00`

## 结论摘要

- 数据集：209；具备审计能力：209；缺少审计能力：0。
- 审计模式：`{'exhaustive_snapshot': 30, 'expected_partition': 75, 'observed_scope_transport': 104}`。
- 业务数据综合状态：`{'complete': 40, 'empty': 2, 'gaps': 56, 'unverified': 79}`；最新有界审计状态：`{'complete': 56, 'empty': 2, 'gaps': 61, 'unverified': 90}`。
- 已确认缺失分区：19；存在数据但不完整/缺少传输证明：10617。
- 数据集历史可用起点尚未证明、不得直接当成缺失的候选分区：103。
- 旧规则遗留、必须重审后才能判定的分区：13034。
- 补采状态：`{'attention_after_retry': 9, 'deferred_by_research_scope': 31, 'evidence_sidecar_not_applicable': 1, 'history_boundary_review': 1, 'manual_scope_required': 24, 'not_backfilled': 43, 'not_needed': 42, 'observed_scope_not_globally_provable': 57, 'reaudit_required': 1}`。
- V2：控制面 `installed`；业务数据集基线映射 177/177；现有 V2 补采/修复实例 44167；按任务×逻辑周期仍需 10482 个实例。

> `success` 只表示任务执行完成；“最新有界审计通过”也不自动等于全部历史完整。综合状态还会合并全历史分区账本、旧规则版本和活动补采。`unverified` 不得解释为完整。

## 逐数据集明细

| 数据集 | 审计模式 | 状态 | 缺失 | 部分/未证明 | 补采队列/运行 | 处理状态 | V2 任务/定义 | 缺失日期样例 |
|---|---|---:|---:|---:|---:|---|---|---|
| adj_factor | expected_partition | gaps | 0 | 25 | 0/0 | not_backfilled | adj_factor/active | 2026-07-13, 2026-07-14, 2026-07-15, 2026-07-16, 2026-07-17 |
| ant_actual_controller | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | ant_actual_controller/active | — |
| ant_controlling_shareholder | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | ant_controlling_shareholder/active | — |
| ant_equity_structure | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | ant_equity_structure/active | — |
| ant_free_float | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | ant_free_float/active | — |
| ant_hot_plate_rank | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | ant_hot_plate_rank/active | — |
| ant_hot_stock_rank | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | ant_hot_stock_rank/active | — |
| ant_style_classification | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | ant_style_classification/active | — |
| bak_basic | observed_scope_transport | unverified | 0 | 0 | 0/0 | observed_scope_not_globally_provable | bak_basic/active | — |
| bak_daily | expected_partition | gaps | 0 | 25 | 0/0 | not_backfilled | bak_daily/active | 2026-07-13, 2026-07-14, 2026-07-15, 2026-07-16, 2026-07-17 |
| balancesheet | expected_partition | unverified | 0 | 0 | 0/0 | manual_scope_required | balancesheet/active | — |
| bc_bestotcqt | observed_scope_transport | complete | 0 | 0 | 0/0 | deferred_by_research_scope | bc_bestotcqt/active | — |
| bc_otcqt | observed_scope_transport | complete | 0 | 0 | 0/0 | deferred_by_research_scope | bc_otcqt/active | — |
| block_trade | observed_scope_transport | unverified | 0 | 0 | 0/0 | observed_scope_not_globally_provable | block_trade/active | — |
| bond_blk | observed_scope_transport | complete | 0 | 0 | 0/0 | deferred_by_research_scope | bond_blk/active | — |
| bond_blk_detail | observed_scope_transport | complete | 0 | 0 | 0/0 | deferred_by_research_scope | bond_blk_detail/active | — |
| broker_recommend | exhaustive_snapshot | complete | 0 | 0 | 0/0 | not_needed | broker_recommend/active | — |
| bse_mapping | exhaustive_snapshot | complete | 0 | 0 | 0/0 | not_needed | bse_mapping/active | — |
| cashflow | expected_partition | unverified | 0 | 0 | 0/0 | manual_scope_required | cashflow/active | — |
| cb_basic | exhaustive_snapshot | complete | 0 | 0 | 0/0 | not_needed | cb_basic/active | — |
| cb_call | observed_scope_transport | unverified | 0 | 0 | 0/0 | observed_scope_not_globally_provable | cb_call/active | — |
| cb_daily | expected_partition | gaps | 0 | 25 | 0/0 | not_backfilled | cb_daily/active | 2026-07-13, 2026-07-14, 2026-07-15, 2026-07-16, 2026-07-17 |
| cb_factor_pro | expected_partition | complete | 0 | 0 | 0/0 | not_needed | cb_factor_pro/active | — |
| cb_issue | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | cb_issue/active | — |
| cb_rate | exhaustive_snapshot | unverified | 0 | 0 | 0/0 | manual_scope_required | cb_rate/active | — |
| cb_rating | observed_scope_transport | unverified | 0 | 0 | 0/0 | manual_scope_required | cb_rating/active | — |
| cb_share | observed_scope_transport | unverified | 0 | 0 | 0/0 | manual_scope_required | cb_share/active | — |
| ccass_hold | observed_scope_transport | complete | 0 | 0 | 0/0 | deferred_by_research_scope | ccass_hold/active | — |
| ccass_hold_detail | observed_scope_transport | complete | 0 | 0 | 0/0 | deferred_by_research_scope | ccass_hold_detail/active | — |
| chinabond_yield_curve | expected_partition | gaps | 0 | 2454 | 0/0 | attention_after_retry | chinabond_yield_curve/active | 2016-11-14, 2016-11-15, 2016-11-16, 2016-11-17, 2016-11-18 |
| ci_daily | expected_partition | gaps | 0 | 25 | 0/0 | not_backfilled | ci_daily/active | 2026-07-13, 2026-07-14, 2026-07-15, 2026-07-16, 2026-07-17 |
| ci_index_member | exhaustive_snapshot | complete | 0 | 0 | 0/0 | not_needed | ci_index_member/active | — |
| cn_cpi | expected_partition | gaps | 0 | 107 | 0/0 | not_backfilled | cn_cpi/active | 2016-11-30, 2016-12-31, 2017-01-31, 2017-02-28, 2017-03-31 |
| cn_gdp | expected_partition | gaps | 0 | 28 | 0/0 | not_backfilled | cn_gdp/active | 2016-12-31, 2017-03-31, 2017-06-30, 2017-09-30, 2017-12-31 |
| cn_lpr | expected_partition | gaps | 0 | 107 | 0/0 | not_backfilled | cn_lpr/active | 2016-11-30, 2016-12-31, 2017-01-31, 2017-02-28, 2017-03-31 |
| cn_m | expected_partition | gaps | 0 | 107 | 0/0 | not_backfilled | cn_m/active | 2016-11-30, 2016-12-31, 2017-01-31, 2017-02-28, 2017-03-31 |
| cn_pmi | expected_partition | gaps | 0 | 107 | 0/0 | not_backfilled | cn_pmi/active | 2016-11-30, 2016-12-31, 2017-01-31, 2017-02-28, 2017-03-31 |
| cn_ppi | expected_partition | gaps | 0 | 107 | 0/0 | not_backfilled | cn_ppi/active | 2016-11-30, 2016-12-31, 2017-01-31, 2017-02-28, 2017-03-31 |
| cn_schedule | observed_scope_transport | unverified | 0 | 0 | 0/0 | observed_scope_not_globally_provable | cn_schedule/active | — |
| cyq_chips | expected_partition | unverified | 0 | 0 | 0/0 | reaudit_required | cyq_chips/active | — |
| cyq_perf | expected_partition | gaps | 0 | 49 | 0/0 | manual_scope_required | cyq_perf/active | 2026-08-03, 2026-08-04, 2026-08-05, 2026-08-06, 2026-08-07 |
| daily_basic | expected_partition | gaps | 0 | 20 | 0/0 | not_backfilled | daily_basic/active | 2026-08-03, 2026-08-04, 2026-08-05, 2026-08-06, 2026-08-07 |
| daily_info | expected_partition | gaps | 0 | 25 | 0/0 | not_backfilled | daily_info/active | 2026-07-13, 2026-07-14, 2026-07-15, 2026-07-16, 2026-07-17 |
| dc_concept | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | dc_concept/active | — |
| dc_concept_cons | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | dc_concept_cons/active | — |
| dc_daily | expected_partition | gaps | 0 | 25 | 0/0 | not_backfilled | dc_daily/active | 2026-07-13, 2026-07-14, 2026-07-15, 2026-07-16, 2026-07-17 |
| dc_hot | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | dc_hot/active | — |
| dc_index | expected_partition | gaps | 0 | 29 | 0/0 | attention_after_retry | dc_index/active | 2026-08-28, 2026-08-31, 2026-09-01, 2026-09-02, 2026-09-03 |
| dc_member | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | dc_member/active | — |
| disclosure_date | observed_scope_transport | unverified | 0 | 0 | 0/0 | observed_scope_not_globally_provable | disclosure_date/active | — |
| dividend | observed_scope_transport | unverified | 0 | 0 | 0/0 | observed_scope_not_globally_provable | dividend/active | — |
| eco_cal | observed_scope_transport | unverified | 0 | 0 | 0/0 | observed_scope_not_globally_provable | eco_cal/active | — |
| etf_basic | exhaustive_snapshot | complete | 0 | 0 | 0/0 | not_needed | etf_basic/active | — |
| etf_index | exhaustive_snapshot | complete | 0 | 0 | 0/0 | not_needed | etf_index/active | — |
| etf_sh_cons | expected_partition | gaps | 0 | 31 | 0/0 | manual_scope_required | etf_sh_cons/active | 2026-08-27, 2026-08-28, 2026-08-31, 2026-09-01, 2026-09-02 |
| etf_share_size | expected_partition | gaps | 0 | 25 | 0/0 | not_backfilled | etf_share_size/active | 2026-07-13, 2026-07-14, 2026-07-15, 2026-07-16, 2026-07-17 |
| etf_sz_cons | expected_partition | gaps | 0 | 26 | 0/0 | manual_scope_required | etf_sz_cons/active | 2026-08-27, 2026-08-28, 2026-08-31, 2026-09-01, 2026-09-02 |
| express | observed_scope_transport | unverified | 0 | 0 | 0/0 | manual_scope_required | express/active | — |
| factor_value | expected_partition | gaps | 0 | 25 | 0/0 | deferred_by_research_scope | factor_value/active | 2026-08-28, 2026-08-31, 2026-09-01, 2026-09-02, 2026-09-03 |
| fama_french_daily | expected_partition | gaps | 0 | 41 | 0/0 | not_backfilled | fama_french_daily/active | 2026-08-03, 2026-08-04, 2026-08-05, 2026-08-06, 2026-08-07 |
| fina_audit | observed_scope_transport | unverified | 0 | 0 | 0/0 | manual_scope_required | fina_audit/active | — |
| fina_mainbz | expected_partition | unverified | 0 | 0 | 0/0 | manual_scope_required | fina_mainbz/active | — |
| financial_indicator | expected_partition | unverified | 0 | 0 | 0/0 | manual_scope_required | financial_indicator/active | — |
| forecast | observed_scope_transport | unverified | 0 | 0 | 0/0 | observed_scope_not_globally_provable | forecast/active | — |
| forex_daily | observed_scope_transport | unverified | 0 | 0 | 0/0 | observed_scope_not_globally_provable | fx_daily/active | — |
| ft_limit | observed_scope_transport | complete | 0 | 0 | 0/0 | deferred_by_research_scope | ft_limit/active | — |
| fund_adj | expected_partition | gaps | 0 | 25 | 0/0 | not_backfilled | fund_adj/active | 2026-07-13, 2026-07-14, 2026-07-15, 2026-07-16, 2026-07-17 |
| fund_basic | exhaustive_snapshot | complete | 0 | 0 | 0/0 | not_needed | fund_basic/active | — |
| fund_company | exhaustive_snapshot | unverified | 0 | 0 | 0/0 | observed_scope_not_globally_provable | fund_company/active | — |
| fund_daily | expected_partition | gaps | 0 | 25 | 0/0 | not_backfilled | fund_daily/active | 2026-07-13, 2026-07-14, 2026-07-15, 2026-07-16, 2026-07-17 |
| fund_div | observed_scope_transport | unverified | 0 | 0 | 0/0 | observed_scope_not_globally_provable | fund_div/active | — |
| fund_factor_pro | expected_partition | complete | 0 | 0 | 0/0 | not_needed | fund_factor_pro/active | — |
| fund_manager | observed_scope_transport | unverified | 0 | 0 | 0/0 | observed_scope_not_globally_provable | fund_manager/active | — |
| fund_nav | observed_scope_transport | unverified | 0 | 0 | 0/0 | observed_scope_not_globally_provable | fund_nav/active | — |
| fund_portfolio | observed_scope_transport | unverified | 0 | 0 | 0/0 | observed_scope_not_globally_provable | fund_portfolio/active | — |
| fund_share | observed_scope_transport | unverified | 0 | 0 | 0/0 | observed_scope_not_globally_provable | fund_share/active | — |
| fut_basic | exhaustive_snapshot | complete | 0 | 0 | 0/0 | deferred_by_research_scope | fut_basic/active | — |
| fut_daily | observed_scope_transport | complete | 0 | 0 | 0/0 | deferred_by_research_scope | fut_daily/active | — |
| fut_holding | observed_scope_transport | unverified | 0 | 0 | 0/0 | deferred_by_research_scope | fut_holding/active | — |
| fut_index_daily | expected_partition | gaps | 0 | 17 | 0/0 | deferred_by_research_scope | fut_index_daily/active | 2026-09-04, 2026-09-07, 2026-09-08, 2026-09-09, 2026-09-10 |
| fut_mapping | observed_scope_transport | complete | 0 | 0 | 0/0 | deferred_by_research_scope | fut_mapping/active | — |
| fut_settle | observed_scope_transport | complete | 0 | 0 | 0/0 | deferred_by_research_scope | fut_settle/active | — |
| fut_trade_cal | observed_scope_transport | unverified | 0 | 0 | 0/0 | deferred_by_research_scope | fut_trade_cal/active | — |
| fut_weekly_detail | observed_scope_transport | unverified | 0 | 0 | 0/0 | deferred_by_research_scope | fut_weekly_detail/active | — |
| fut_weekly_monthly | observed_scope_transport | unverified | 0 | 0 | 0/0 | deferred_by_research_scope | fut_weekly_monthly/active | — |
| fut_wsr | observed_scope_transport | complete | 0 | 0 | 0/0 | deferred_by_research_scope | fut_wsr/active | — |
| fx_obasic | exhaustive_snapshot | complete | 0 | 0 | 0/0 | deferred_by_research_scope | fx_obasic/active | — |
| ggt_daily | observed_scope_transport | unverified | 0 | 0 | 0/0 | observed_scope_not_globally_provable | ggt_daily/active | — |
| ggt_monthly | expected_partition | gaps | 0 | 143 | 0/0 | not_backfilled | ggt_monthly/active | 2014-11-30, 2014-12-31, 2015-01-31, 2015-02-28, 2015-03-31 |
| ggt_top10 | observed_scope_transport | unverified | 0 | 0 | 0/0 | manual_scope_required | ggt_top10/active | — |
| gz_index | observed_scope_transport | unverified | 0 | 0 | 0/0 | deferred_by_research_scope | gz_index/active | — |
| hibor | observed_scope_transport | unverified | 0 | 0 | 0/0 | observed_scope_not_globally_provable | hibor/active | — |
| hk_basic | exhaustive_snapshot | complete | 0 | 0 | 0/0 | deferred_by_research_scope | hk_basic/active | — |
| hk_daily | expected_partition | gaps | 1 | 15 | 0/0 | deferred_by_research_scope | hk_daily/active | 2026-11-09 |
| hk_hold | observed_scope_transport | gaps | 0 | 61 | 0/0 | attention_after_retry | hk_hold/active | 2026-07-13, 2026-07-14, 2026-07-15, 2026-07-16, 2026-07-17 |
| hk_tradecal | observed_scope_transport | unverified | 0 | 0 | 0/0 | deferred_by_research_scope | hk_tradecal/active | — |
| hm_list | exhaustive_snapshot | complete | 0 | 0 | 0/0 | not_needed | hm_list/active | — |
| hsgt_top10 | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | hsgt_top10/active | — |
| idx_anns | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | idx_anns/active | — |
| idx_factor_pro | expected_partition | gaps | 0 | 35 | 0/0 | not_backfilled | idx_factor_pro/active | 2026-07-13, 2026-07-14, 2026-07-15, 2026-07-16, 2026-07-17 |
| income | expected_partition | unverified | 0 | 0 | 0/0 | manual_scope_required | income/active | — |
| index_basic | exhaustive_snapshot | complete | 0 | 0 | 0/0 | not_needed | index_basic/active | — |
| index_classify | exhaustive_snapshot | complete | 0 | 0 | 0/0 | not_needed | index_classify/active | — |
| index_daily | expected_partition | gaps | 0 | 35 | 0/0 | attention_after_retry | index_daily/active | 2026-07-13, 2026-07-14, 2026-07-15, 2026-07-16, 2026-07-17 |
| index_dailybasic | expected_partition | gaps | 0 | 35 | 0/0 | not_backfilled | index_dailybasic/active | 2026-07-13, 2026-07-14, 2026-07-15, 2026-07-16, 2026-07-17 |
| index_global | observed_scope_transport | unverified | 0 | 0 | 0/0 | observed_scope_not_globally_provable | index_global/active | — |
| index_member_all | exhaustive_snapshot | complete | 0 | 0 | 0/0 | not_needed | index_member_all/active | — |
| index_monthly | expected_partition | gaps | 0 | 42 | 0/0 | not_backfilled | index_monthly/active | 2024-11-27, 2024-11-28, 2024-11-29, 2024-12-27, 2024-12-30 |
| index_weekly | expected_partition | gaps | 0 | 6 | 0/0 | not_backfilled | index_weekly/active | 2026-07-16, 2026-07-17, 2026-07-23, 2026-07-24, 2026-07-30 |
| index_weight | observed_scope_transport | unverified | 0 | 0 | 0/0 | manual_scope_required | index_weight/active | — |
| industry_daily | expected_partition | gaps | 0 | 36 | 0/0 | not_backfilled | ths_daily/active | 2026-07-13, 2026-07-14, 2026-07-15, 2026-07-16, 2026-07-17 |
| kpl_concept_cons | expected_partition | gaps | 0 | 35 | 0/0 | not_backfilled | kpl_concept_cons/active | 2026-07-13, 2026-07-14, 2026-07-15, 2026-07-16, 2026-07-17 |
| kpl_list | observed_scope_transport | unverified | 0 | 0 | 0/0 | observed_scope_not_globally_provable | kpl_list/active | — |
| libor | observed_scope_transport | unverified | 0 | 0 | 0/0 | deferred_by_research_scope | libor/active | — |
| limit_cpt_list | observed_scope_transport | unverified | 0 | 0 | 0/0 | observed_scope_not_globally_provable | limit_cpt_list/active | — |
| limit_list_d | observed_scope_transport | unverified | 0 | 0 | 0/0 | observed_scope_not_globally_provable | limit_list_d/active | — |
| limit_list_ths | observed_scope_transport | unverified | 0 | 0 | 0/0 | observed_scope_not_globally_provable | limit_list_ths/active | — |
| limit_step | observed_scope_transport | unverified | 0 | 0 | 0/0 | observed_scope_not_globally_provable | limit_step/active | — |
| local_factor_snapshot | expected_partition | gaps | 0 | 26 | 0/0 | attention_after_retry | local_factor_snapshot/active | 2026-09-24, 2026-09-28, 2026-09-29, 2026-09-30, 2026-10-08 |
| major_news | exhaustive_snapshot | complete | 0 | 0 | 0/0 | not_needed | major_news/active | — |
| margin | expected_partition | gaps | 0 | 34 | 0/0 | not_backfilled | margin/active | 2026-07-13, 2026-07-14, 2026-07-15, 2026-07-16, 2026-07-17 |
| margin_detail | expected_partition | gaps | 0 | 4003 | 0/0 | attention_after_retry | margin_detail/active | 2010-03-31, 2010-04-01, 2010-04-02, 2010-04-06, 2010-04-07 |
| margin_secs | observed_scope_transport | unverified | 0 | 0 | 0/0 | observed_scope_not_globally_provable | margin_secs/active | — |
| mkt_idx_bmk | exhaustive_snapshot | complete | 0 | 0 | 0/0 | not_needed | mkt_idx_bmk/active | — |
| moneyflow | expected_partition | gaps | 0 | 35 | 0/0 | not_backfilled | moneyflow/active | 2026-07-13, 2026-07-14, 2026-07-15, 2026-07-16, 2026-07-17 |
| moneyflow_cnt_ths | expected_partition | gaps | 0 | 35 | 0/0 | not_backfilled | moneyflow_cnt_ths/active | 2026-07-13, 2026-07-14, 2026-07-15, 2026-07-16, 2026-07-17 |
| moneyflow_dc | expected_partition | gaps | 0 | 23 | 0/0 | manual_scope_required | moneyflow_dc/active | 2026-09-01, 2026-09-02, 2026-09-03, 2026-09-04, 2026-09-07 |
| moneyflow_hsgt | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | moneyflow_hsgt/active | — |
| moneyflow_ind_dc | expected_partition | gaps | 0 | 35 | 0/0 | not_backfilled | moneyflow_ind_dc/active | 2026-07-13, 2026-07-14, 2026-07-15, 2026-07-16, 2026-07-17 |
| moneyflow_ind_ths | expected_partition | gaps | 0 | 35 | 0/0 | not_backfilled | moneyflow_ind_ths/active | 2026-07-13, 2026-07-14, 2026-07-15, 2026-07-16, 2026-07-17 |
| moneyflow_mkt_dc | expected_partition | gaps | 0 | 35 | 0/0 | not_backfilled | moneyflow_mkt_dc/active | 2026-07-13, 2026-07-14, 2026-07-15, 2026-07-16, 2026-07-17 |
| moneyflow_ths | expected_partition | gaps | 0 | 35 | 0/0 | not_backfilled | moneyflow_ths/active | 2026-07-13, 2026-07-14, 2026-07-15, 2026-07-16, 2026-07-17 |
| namechange | observed_scope_transport | unverified | 0 | 0 | 0/0 | observed_scope_not_globally_provable | namechange/active | — |
| new_share | observed_scope_transport | empty | 0 | 0 | 0/0 | not_needed | new_share/active | — |
| opt_basic | exhaustive_snapshot | complete | 0 | 0 | 0/0 | deferred_by_research_scope | opt_basic/active | — |
| opt_daily | expected_partition | gaps | 0 | 12 | 0/0 | deferred_by_research_scope | opt_daily/active | 2026-09-24, 2026-09-28, 2026-09-29, 2026-09-30, 2026-10-08 |
| p_get | exhaustive_snapshot | unverified | 0 | 0 | 0/0 | manual_scope_required | p_get/active | — |
| p_list | exhaustive_snapshot | empty | 0 | 0 | 0/0 | not_needed | p_list/active | — |
| pledge_detail | observed_scope_transport | unverified | 0 | 0 | 0/0 | observed_scope_not_globally_provable | pledge_detail/active | — |
| pledge_stat | observed_scope_transport | unverified | 0 | 0 | 0/0 | manual_scope_required | pledge_stat/active | — |
| repo_daily | observed_scope_transport | unverified | 0 | 0 | 0/0 | observed_scope_not_globally_provable | repo_daily/active | — |
| report_rc | expected_partition | unverified | 0 | 0 | 0/0 | observed_scope_not_globally_provable | report_rc/active | — |
| repurchase | expected_partition | complete | 0 | 0 | 0/0 | not_needed | repurchase/active | — |
| rt_hk_k | exhaustive_snapshot | unverified | 0 | 0 | 0/0 | deferred_by_research_scope | rt_hk_k/active | — |
| sf_month | expected_partition | gaps | 0 | 107 | 0/0 | not_backfilled | sf_month/active | 2016-11-30, 2016-12-31, 2017-01-31, 2017-02-28, 2017-03-31 |
| sge_basic | exhaustive_snapshot | complete | 0 | 0 | 0/0 | not_needed | sge_basic/active | — |
| sge_daily | expected_partition | gaps | 0 | 1166 | 0/0 | not_backfilled | sge_daily/active | 2021-11-11, 2021-11-12, 2021-11-15, 2021-11-16, 2021-11-17 |
| share_float | observed_scope_transport | unverified | 0 | 0 | 0/0 | observed_scope_not_globally_provable | share_float/active | — |
| shibor | expected_partition | gaps | 0 | 697 | 0/0 | not_backfilled | shibor/active | 2023-11-13, 2023-11-14, 2023-11-15, 2023-11-16, 2023-11-17 |
| shibor_quote | observed_scope_transport | unverified | 0 | 0 | 0/0 | observed_scope_not_globally_provable | shibor_quote/active | — |
| slb_len | observed_scope_transport | unverified | 0 | 0 | 0/0 | observed_scope_not_globally_provable | slb_len/active | — |
| slb_len_mm | observed_scope_transport | unverified | 0 | 0 | 0/0 | observed_scope_not_globally_provable | slb_len_mm/active | — |
| slb_sec | observed_scope_transport | unverified | 0 | 0 | 0/0 | observed_scope_not_globally_provable | slb_sec/active | — |
| slb_sec_detail | observed_scope_transport | unverified | 0 | 0 | 0/0 | observed_scope_not_globally_provable | slb_sec_detail/active | — |
| stk_account | observed_scope_transport | unverified | 0 | 0 | 0/0 | observed_scope_not_globally_provable | stk_account/active | — |
| stk_ah_comparison | observed_scope_transport | unverified | 0 | 0 | 0/0 | observed_scope_not_globally_provable | stk_ah_comparison/active | — |
| stk_alert | observed_scope_transport | unverified | 0 | 0 | 0/0 | observed_scope_not_globally_provable | stk_alert/active | — |
| stk_auction | expected_partition | gaps | 0 | 35 | 0/0 | not_backfilled | stk_auction/active | 2026-07-13, 2026-07-14, 2026-07-15, 2026-07-16, 2026-07-17 |
| stk_auction_c | observed_scope_transport | unverified | 0 | 0 | 0/0 | observed_scope_not_globally_provable | stk_auction_c/active | — |
| stk_auction_o | observed_scope_transport | unverified | 0 | 0 | 0/0 | observed_scope_not_globally_provable | stk_auction_o/active | — |
| stk_factor | expected_partition | gaps | 0 | 25 | 0/0 | attention_after_retry | stk_factor/active | 2026-07-13, 2026-07-14, 2026-07-15, 2026-07-16, 2026-07-17 |
| stk_factor_pro | expected_partition | gaps | 0 | 24 | 0/0 | attention_after_retry | stk_factor_pro/active | 2026-07-13, 2026-07-14, 2026-07-15, 2026-07-16, 2026-07-17 |
| stk_high_shock | observed_scope_transport | unverified | 0 | 0 | 0/0 | observed_scope_not_globally_provable | stk_high_shock/active | — |
| stk_holdernumber | observed_scope_transport | unverified | 0 | 0 | 0/0 | observed_scope_not_globally_provable | stk_holdernumber/active | — |
| stk_holdertrade | observed_scope_transport | unverified | 0 | 0 | 0/0 | observed_scope_not_globally_provable | stk_holdertrade/active | — |
| stk_managers | observed_scope_transport | unverified | 0 | 0 | 0/0 | observed_scope_not_globally_provable | stk_managers/active | — |
| stk_mins | exhaustive_snapshot | unverified | 0 | 0 | 0/0 | manual_scope_required | stk_mins/active | — |
| stk_nineturn | observed_scope_transport | unverified | 0 | 0 | 0/0 | observed_scope_not_globally_provable | stk_nineturn/active | — |
| stk_rewards | observed_scope_transport | unverified | 0 | 0 | 0/0 | manual_scope_required | stk_rewards/active | — |
| stk_seasoned | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | stk_seasoned/active | — |
| stk_shock | observed_scope_transport | unverified | 0 | 0 | 0/0 | observed_scope_not_globally_provable | stk_shock/active | — |
| stk_surv | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | stk_surv/active | — |
| stk_week_month_adj | observed_scope_transport | unverified | 0 | 0 | 0/0 | manual_scope_required | stk_week_month_adj/active | — |
| stk_weekly_monthly | observed_scope_transport | unverified | 0 | 0 | 0/0 | observed_scope_not_globally_provable | stk_weekly_monthly/active | — |
| stock_announcements | expected_partition | unverified | 0 | 0 | 0/0 | history_boundary_review | cninfo_announcements/active | — |
| stock_basic | exhaustive_snapshot | complete | 0 | 0 | 0/0 | not_needed | stock_basic/active | — |
| stock_company | exhaustive_snapshot | complete | 0 | 0 | 0/0 | not_needed | stock_company/active | — |
| stock_daily | expected_partition | gaps | 0 | 35 | 0/0 | not_backfilled | daily/active | 2026-07-13, 2026-07-14, 2026-07-15, 2026-07-16, 2026-07-17 |
| stock_daily_basic | expected_partition | gaps | 0 | 35 | 0/0 | not_backfilled | daily_basic/active | 2026-07-13, 2026-07-14, 2026-07-15, 2026-07-16, 2026-07-17 |
| stock_hsgt | observed_scope_transport | unverified | 0 | 0 | 0/0 | manual_scope_required | stock_hsgt/active | — |
| stock_limit | expected_partition | gaps | 0 | 35 | 0/0 | not_backfilled | stk_limit/active | 2026-07-13, 2026-07-14, 2026-07-15, 2026-07-16, 2026-07-17 |
| stock_st | expected_partition | gaps | 0 | 35 | 0/0 | not_backfilled | stock_st/active | 2026-07-13, 2026-07-14, 2026-07-15, 2026-07-16, 2026-07-17 |
| stock_suspend | observed_scope_transport | unverified | 0 | 0 | 0/0 | observed_scope_not_globally_provable | suspend_d/active | — |
| sw_daily | expected_partition | gaps | 0 | 35 | 0/0 | not_backfilled | sw_daily/active | 2026-07-13, 2026-07-14, 2026-07-15, 2026-07-16, 2026-07-17 |
| sz_daily_info | expected_partition | gaps | 0 | 35 | 0/0 | not_backfilled | sz_daily_info/active | 2026-07-13, 2026-07-14, 2026-07-15, 2026-07-16, 2026-07-17 |
| tdx_daily | expected_partition | gaps | 0 | 35 | 0/0 | not_backfilled | tdx_daily/active | 2026-07-13, 2026-07-14, 2026-07-15, 2026-07-16, 2026-07-17 |
| tdx_index | expected_partition | gaps | 0 | 35 | 0/0 | not_backfilled | tdx_index/active | 2026-07-13, 2026-07-14, 2026-07-15, 2026-07-16, 2026-07-17 |
| tdx_member | observed_scope_transport | unverified | 0 | 0 | 0/0 | manual_scope_required | tdx_member/active | — |
| technical_factor_snapshot | expected_partition | complete | 0 | 0 | 0/0 | not_needed | local_factor_snapshot/active | — |
| ths_hot | expected_partition | gaps | 0 | 35 | 0/0 | attention_after_retry | ths_hot/active | 2026-07-13, 2026-07-14, 2026-07-15, 2026-07-16, 2026-07-17 |
| ths_index | exhaustive_snapshot | complete | 0 | 0 | 0/0 | not_needed | ths_index/active | — |
| ths_member | exhaustive_snapshot | complete | 0 | 0 | 0/0 | not_needed | ths_member/active | — |
| top10_cb_holders | observed_scope_transport | unverified | 0 | 0 | 0/0 | manual_scope_required | top10_cb_holders/active | — |
| top10_floatholders | expected_partition | unverified | 0 | 0 | 0/0 | observed_scope_not_globally_provable | top10_floatholders/active | — |
| top10_holders | expected_partition | unverified | 0 | 0 | 0/0 | observed_scope_not_globally_provable | top10_holders/active | — |
| top_inst | observed_scope_transport | unverified | 0 | 0 | 0/0 | observed_scope_not_globally_provable | top_inst/active | — |
| top_list | observed_scope_transport | unverified | 0 | 0 | 0/0 | observed_scope_not_globally_provable | top_list/active | — |
| trade_calendar | observed_scope_transport | unverified | 0 | 0 | 0/0 | observed_scope_not_globally_provable | trade_cal/active | — |
| tushare_raw | exhaustive_snapshot | unverified | 0 | 0 | 0/0 | evidence_sidecar_not_applicable | —/not_applicable | — |
| us_basic | exhaustive_snapshot | complete | 0 | 0 | 0/0 | deferred_by_research_scope | us_basic/active | — |
| us_daily | expected_partition | gaps | 18 | 17 | 0/0 | deferred_by_research_scope | us_daily/active | 2026-09-01, 2026-09-02, 2026-09-04, 2026-09-08, 2026-09-09 |
| us_tbr | observed_scope_transport | unverified | 0 | 0 | 0/0 | observed_scope_not_globally_provable | us_tbr/active | — |
| us_tltr | observed_scope_transport | unverified | 0 | 0 | 0/0 | observed_scope_not_globally_provable | us_tltr/active | — |
| us_tradecal | observed_scope_transport | unverified | 0 | 0 | 0/0 | deferred_by_research_scope | us_tradecal/active | — |
| us_trltr | observed_scope_transport | unverified | 0 | 0 | 0/0 | observed_scope_not_globally_provable | us_trltr/active | — |
| us_trycr | observed_scope_transport | unverified | 0 | 0 | 0/0 | observed_scope_not_globally_provable | us_trycr/active | — |
| us_tycr | observed_scope_transport | unverified | 0 | 0 | 0/0 | observed_scope_not_globally_provable | us_tycr/active | — |
| valuation_percentile_snapshot | expected_partition | complete | 0 | 0 | 0/0 | not_needed | valuation_percentile_snapshot/active | — |
| wz_index | observed_scope_transport | unverified | 0 | 0 | 0/0 | deferred_by_research_scope | wz_index/active | — |

## V2 缺口实例规划（只读）

| 任务 | 逻辑周期实例数 | 输出数据集 | 周期样例 |
|---|---:|---|---|
| margin_detail | 4003 | margin_detail | 2010-03-31, 2010-04-01, 2010-04-02, 2010-04-06, 2010-04-07 |
| chinabond_yield_curve | 2454 | chinabond_yield_curve | 2016-11-14, 2016-11-15, 2016-11-16, 2016-11-17, 2016-11-18 |
| sge_daily | 1166 | sge_daily | 2021-11-11, 2021-11-12, 2021-11-15, 2021-11-16, 2021-11-17 |
| shibor | 697 | shibor | 2023-11-13, 2023-11-14, 2023-11-15, 2023-11-16, 2023-11-17 |
| ggt_monthly | 143 | ggt_monthly | 2014-11, 2014-12, 2015-01, 2015-02, 2015-03 |
| cn_cpi | 107 | cn_cpi | 2016-11, 2016-12, 2017-01, 2017-02, 2017-03 |
| cn_lpr | 107 | cn_lpr | 2016-11, 2016-12, 2017-01, 2017-02, 2017-03 |
| cn_m | 107 | cn_m | 2016-11, 2016-12, 2017-01, 2017-02, 2017-03 |
| cn_pmi | 107 | cn_pmi | 2016-11, 2016-12, 2017-01, 2017-02, 2017-03 |
| cn_ppi | 107 | cn_ppi | 2016-11, 2016-12, 2017-01, 2017-02, 2017-03 |
| sf_month | 107 | sf_month | 2016-11, 2016-12, 2017-01, 2017-02, 2017-03 |
| hk_hold | 61 | hk_hold | 2026-07-13, 2026-07-14, 2026-07-15, 2026-07-16, 2026-07-17 |
| cyq_perf | 49 | cyq_perf | 2026-08-03, 2026-08-04, 2026-08-05, 2026-08-06, 2026-08-07 |
| fama_french_daily | 41 | fama_french_daily | 2026-08-03, 2026-08-04, 2026-08-05, 2026-08-06, 2026-08-07 |
| ths_daily | 36 | industry_daily | 2026-07-13, 2026-07-14, 2026-07-15, 2026-07-16, 2026-07-17 |
| daily | 35 | stock_daily | 2026-07-13, 2026-07-14, 2026-07-15, 2026-07-16, 2026-07-17 |
| daily_basic | 35 | daily_basic, stock_daily_basic | 2026-07-13, 2026-07-14, 2026-07-15, 2026-07-16, 2026-07-17 |
| idx_factor_pro | 35 | idx_factor_pro | 2026-07-13, 2026-07-14, 2026-07-15, 2026-07-16, 2026-07-17 |
| index_daily | 35 | index_daily | 2026-07-13, 2026-07-14, 2026-07-15, 2026-07-16, 2026-07-17 |
| index_dailybasic | 35 | index_dailybasic | 2026-07-13, 2026-07-14, 2026-07-15, 2026-07-16, 2026-07-17 |
| kpl_concept_cons | 35 | kpl_concept_cons | 2026-07-13, 2026-07-14, 2026-07-15, 2026-07-16, 2026-07-17 |
| moneyflow | 35 | moneyflow | 2026-07-13, 2026-07-14, 2026-07-15, 2026-07-16, 2026-07-17 |
| moneyflow_cnt_ths | 35 | moneyflow_cnt_ths | 2026-07-13, 2026-07-14, 2026-07-15, 2026-07-16, 2026-07-17 |
| moneyflow_ind_dc | 35 | moneyflow_ind_dc | 2026-07-13, 2026-07-14, 2026-07-15, 2026-07-16, 2026-07-17 |
| moneyflow_ind_ths | 35 | moneyflow_ind_ths | 2026-07-13, 2026-07-14, 2026-07-15, 2026-07-16, 2026-07-17 |
| moneyflow_mkt_dc | 35 | moneyflow_mkt_dc | 2026-07-13, 2026-07-14, 2026-07-15, 2026-07-16, 2026-07-17 |
| moneyflow_ths | 35 | moneyflow_ths | 2026-07-13, 2026-07-14, 2026-07-15, 2026-07-16, 2026-07-17 |
| stk_auction | 35 | stk_auction | 2026-07-13, 2026-07-14, 2026-07-15, 2026-07-16, 2026-07-17 |
| stk_limit | 35 | stock_limit | 2026-07-13, 2026-07-14, 2026-07-15, 2026-07-16, 2026-07-17 |
| stock_st | 35 | stock_st | 2026-07-13, 2026-07-14, 2026-07-15, 2026-07-16, 2026-07-17 |
| sw_daily | 35 | sw_daily | 2026-07-13, 2026-07-14, 2026-07-15, 2026-07-16, 2026-07-17 |
| sz_daily_info | 35 | sz_daily_info | 2026-07-13, 2026-07-14, 2026-07-15, 2026-07-16, 2026-07-17 |
| tdx_daily | 35 | tdx_daily | 2026-07-13, 2026-07-14, 2026-07-15, 2026-07-16, 2026-07-17 |
| tdx_index | 35 | tdx_index | 2026-07-13, 2026-07-14, 2026-07-15, 2026-07-16, 2026-07-17 |
| ths_hot | 35 | ths_hot | 2026-07-13, 2026-07-14, 2026-07-15, 2026-07-16, 2026-07-17 |
| margin | 34 | margin | 2026-07-13, 2026-07-14, 2026-07-15, 2026-07-16, 2026-07-17 |
| etf_sh_cons | 31 | etf_sh_cons | 2026-08-27, 2026-08-28, 2026-08-31, 2026-09-01, 2026-09-02 |
| dc_index | 29 | dc_index | 2026-08-28, 2026-08-31, 2026-09-01, 2026-09-02, 2026-09-03 |
| cn_gdp | 28 | cn_gdp | 2016-Q4, 2017-Q1, 2017-Q2, 2017-Q3, 2017-Q4 |
| etf_sz_cons | 26 | etf_sz_cons | 2026-08-27, 2026-08-28, 2026-08-31, 2026-09-01, 2026-09-02 |
| local_factor_snapshot | 26 | local_factor_snapshot, technical_factor_snapshot | 2026-09-24, 2026-09-28, 2026-09-29, 2026-09-30, 2026-10-08 |
| adj_factor | 25 | adj_factor | 2026-07-13, 2026-07-14, 2026-07-15, 2026-07-16, 2026-07-17 |
| bak_daily | 25 | bak_daily | 2026-07-13, 2026-07-14, 2026-07-15, 2026-07-16, 2026-07-17 |
| cb_daily | 25 | cb_daily | 2026-07-13, 2026-07-14, 2026-07-15, 2026-07-16, 2026-07-17 |
| ci_daily | 25 | ci_daily | 2026-07-13, 2026-07-14, 2026-07-15, 2026-07-16, 2026-07-17 |
| daily_info | 25 | daily_info | 2026-07-13, 2026-07-14, 2026-07-15, 2026-07-16, 2026-07-17 |
| dc_daily | 25 | dc_daily | 2026-07-13, 2026-07-14, 2026-07-15, 2026-07-16, 2026-07-17 |
| etf_share_size | 25 | etf_share_size | 2026-07-13, 2026-07-14, 2026-07-15, 2026-07-16, 2026-07-17 |
| fund_adj | 25 | fund_adj | 2026-07-13, 2026-07-14, 2026-07-15, 2026-07-16, 2026-07-17 |
| fund_daily | 25 | fund_daily | 2026-07-13, 2026-07-14, 2026-07-15, 2026-07-16, 2026-07-17 |
| stk_factor | 25 | stk_factor | 2026-07-13, 2026-07-14, 2026-07-15, 2026-07-16, 2026-07-17 |
| stk_factor_pro | 24 | stk_factor_pro | 2026-07-13, 2026-07-14, 2026-07-15, 2026-07-16, 2026-07-17 |
| moneyflow_dc | 23 | moneyflow_dc | 2026-09-01, 2026-09-02, 2026-09-03, 2026-09-04, 2026-09-07 |
| index_monthly | 16 | index_monthly | 2024-11, 2024-12, 2025-01, 2025-02, 2025-03 |
| index_weekly | 3 | index_weekly | 2026-W29, 2026-W30, 2026-W31 |

## 口径

- `expected_partition`：有明确交易日/月/季度预期，可发现从未采集的日期。
- `observed_scope_transport`：稀疏事件不虚构每日必须有数据；按声明的采集范围、分页耗尽和终态证明审计。
- `exhaustive_snapshot`：无日期数据必须有全量快照成功证明、有效空结果证明或完整分页证明。
- `backfill_in_progress`：存在历史/初始化/修复 V2 执行实例；盘中统一延后到 16:00 后执行。
- `not_backfilled`：存在缺口或未验证状态，但当前没有对应 V2 执行实例，需要补计划或人工判定上游边界。
- `history_boundary_review`：候选日期早于本地首个已观测分区，但上游没有给出该数据集的权威可用起点。交易日历只能证明市场开市，不能证明接口当日已经存在或应发布；在补充契约起点前不得把这些日期误报为缺失。
