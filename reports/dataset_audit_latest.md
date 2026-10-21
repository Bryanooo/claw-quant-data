# 全量数据集严格审计报告

生成时间：`2026-10-21T09:54:29.042702+08:00`

## 结论摘要

- 数据集：197；具备审计能力：197；缺少审计能力：0。
- 审计模式：`{'exhaustive_snapshot': 31, 'expected_partition': 70, 'observed_scope_transport': 96}`。
- 业务数据综合状态：`{'complete': 174, 'gaps': 13, 'unverified': 8}`；最新有界审计状态：`{'complete': 174, 'gaps': 16, 'unverified': 7}`。
- 已确认缺失分区：9386；存在数据但不完整/缺少传输证明：2166。
- 数据集历史可用起点尚未证明、不得直接当成缺失的候选分区：0。
- 旧规则遗留、必须重审后才能判定的分区：0。
- 补采状态：`{'backfill_in_progress': 15, 'deferred_by_research_scope': 1, 'evidence_sidecar_not_applicable': 1, 'manual_scope_required': 6, 'not_needed': 174}`。
- V2：控制面 `installed`；业务数据集基线映射 195/195；现有 V2 补采/修复实例 40805；按任务×逻辑周期仍需 2282 个实例。

> `success` 只表示任务执行完成；“最新有界审计通过”也不自动等于全部历史完整。综合状态还会合并全历史分区账本、旧规则版本和活动补采。`unverified` 不得解释为完整。

## 逐数据集明细

| 数据集 | 审计模式 | 状态 | 缺失 | 部分/未证明 | 补采队列/运行 | 处理状态 | V2 任务/定义 | 缺失日期样例 |
|---|---|---:|---:|---:|---:|---|---|---|
| adj_factor | expected_partition | complete | 0 | 0 | 0/0 | not_needed | adj_factor/active | — |
| bak_basic | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | bak_basic/active | — |
| bak_daily | expected_partition | complete | 0 | 0 | 0/0 | not_needed | bak_daily/active | — |
| balancesheet | expected_partition | complete | 0 | 0 | 0/0 | not_needed | balancesheet/active | — |
| bc_bestotcqt | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | bc_bestotcqt/active | — |
| bc_otcqt | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | bc_otcqt/active | — |
| block_trade | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | block_trade/active | — |
| bond_blk | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | bond_blk/active | — |
| bond_blk_detail | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | bond_blk_detail/active | — |
| broker_recommend | exhaustive_snapshot | complete | 0 | 0 | 0/0 | not_needed | broker_recommend/active | — |
| bse_mapping | exhaustive_snapshot | complete | 0 | 0 | 0/0 | not_needed | bse_mapping/active | — |
| cashflow | expected_partition | complete | 0 | 0 | 0/0 | not_needed | cashflow/active | — |
| cb_basic | exhaustive_snapshot | complete | 0 | 0 | 0/0 | not_needed | cb_basic/active | — |
| cb_call | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | cb_call/active | — |
| cb_daily | expected_partition | complete | 0 | 0 | 0/0 | not_needed | cb_daily/active | — |
| cb_factor_pro | expected_partition | unverified | 0 | 0 | 2/0 | backfill_in_progress | cb_factor_pro/active | — |
| cb_issue | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | cb_issue/active | — |
| cb_rate | exhaustive_snapshot | unverified | 0 | 0 | 0/0 | manual_scope_required | cb_rate/active | — |
| cb_rating | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | cb_rating/active | — |
| cb_share | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | cb_share/active | — |
| ccass_hold | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | ccass_hold/active | — |
| ccass_hold_detail | observed_scope_transport | unverified | 0 | 0 | 0/0 | manual_scope_required | ccass_hold_detail/active | — |
| ci_daily | expected_partition | complete | 0 | 0 | 0/0 | not_needed | ci_daily/active | — |
| ci_index_member | exhaustive_snapshot | complete | 0 | 0 | 0/0 | not_needed | ci_index_member/active | — |
| cn_cpi | expected_partition | complete | 0 | 0 | 0/0 | not_needed | cn_cpi/active | — |
| cn_gdp | expected_partition | complete | 0 | 0 | 0/0 | not_needed | cn_gdp/active | — |
| cn_lpr | expected_partition | complete | 0 | 0 | 0/0 | not_needed | cn_lpr/active | — |
| cn_m | expected_partition | complete | 0 | 0 | 0/0 | not_needed | cn_m/active | — |
| cn_pmi | expected_partition | complete | 0 | 0 | 0/0 | not_needed | cn_pmi/active | — |
| cn_ppi | expected_partition | complete | 0 | 0 | 0/0 | not_needed | cn_ppi/active | — |
| cn_schedule | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | cn_schedule/active | — |
| cyq_chips | expected_partition | gaps | 15 | 2095 | 1/0 | backfill_in_progress | cyq_chips/active | 2026-09-22, 2026-09-23, 2026-09-24, 2026-09-28, 2026-09-29 |
| cyq_perf | expected_partition | complete | 0 | 0 | 0/0 | not_needed | cyq_perf/active | — |
| daily_basic | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | daily_basic/active | — |
| daily_info | expected_partition | complete | 0 | 0 | 0/0 | not_needed | daily_info/active | — |
| dc_concept | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | dc_concept/active | — |
| dc_concept_cons | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | dc_concept_cons/active | — |
| dc_daily | expected_partition | complete | 0 | 0 | 0/0 | not_needed | dc_daily/active | — |
| dc_hot | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | dc_hot/active | — |
| dc_index | expected_partition | gaps | 11 | 0 | 1/0 | backfill_in_progress | dc_index/active | 2026-09-28, 2026-09-29, 2026-09-30, 2026-10-08, 2026-10-09 |
| dc_member | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | dc_member/active | — |
| disclosure_date | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | disclosure_date/active | — |
| dividend | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | dividend/active | — |
| eco_cal | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | eco_cal/active | — |
| etf_basic | exhaustive_snapshot | complete | 0 | 0 | 0/0 | not_needed | etf_basic/active | — |
| etf_index | exhaustive_snapshot | complete | 0 | 0 | 0/0 | not_needed | etf_index/active | — |
| etf_sh_cons | expected_partition | gaps | 12 | 0 | 1/0 | backfill_in_progress | etf_sh_cons/active | 2026-09-28, 2026-09-29, 2026-09-30, 2026-10-08, 2026-10-09 |
| etf_share_size | expected_partition | complete | 0 | 0 | 0/0 | not_needed | etf_share_size/active | — |
| etf_sz_cons | expected_partition | gaps | 12 | 0 | 1/0 | backfill_in_progress | etf_sz_cons/active | 2026-09-28, 2026-09-29, 2026-09-30, 2026-10-08, 2026-10-09 |
| express | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | express/active | — |
| factor_value | expected_partition | gaps | 14 | 0 | 2/0 | backfill_in_progress | factor_value/active | 2026-09-10, 2026-09-22, 2026-09-28, 2026-09-29, 2026-09-30 |
| fama_french_daily | expected_partition | complete | 0 | 0 | 0/0 | not_needed | fama_french_daily/active | — |
| fina_audit | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | fina_audit/active | — |
| fina_mainbz | expected_partition | complete | 0 | 0 | 0/0 | not_needed | fina_mainbz/active | — |
| financial_indicator | expected_partition | complete | 0 | 0 | 0/0 | not_needed | financial_indicator/active | — |
| forecast | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | forecast/active | — |
| forex_daily | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | fx_daily/active | — |
| ft_limit | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | ft_limit/active | — |
| fund_adj | expected_partition | complete | 0 | 0 | 0/0 | not_needed | fund_adj/active | — |
| fund_basic | exhaustive_snapshot | complete | 0 | 0 | 0/0 | not_needed | fund_basic/active | — |
| fund_company | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | fund_company/active | — |
| fund_daily | expected_partition | complete | 0 | 0 | 0/0 | not_needed | fund_daily/active | — |
| fund_div | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | fund_div/active | — |
| fund_factor_pro | expected_partition | unverified | 0 | 0 | 2/0 | backfill_in_progress | fund_factor_pro/active | — |
| fund_manager | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | fund_manager/active | — |
| fund_nav | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | fund_nav/active | — |
| fund_portfolio | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | fund_portfolio/active | — |
| fund_share | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | fund_share/active | — |
| fut_basic | exhaustive_snapshot | unverified | 0 | 0 | 0/0 | manual_scope_required | fut_basic/active | — |
| fut_daily | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | fut_daily/active | — |
| fut_holding | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | fut_holding/active | — |
| fut_index_daily | expected_partition | gaps | 12 | 0 | 12/0 | backfill_in_progress | fut_index_daily/active | 2026-09-28, 2026-09-29, 2026-09-30, 2026-10-08, 2026-10-09 |
| fut_mapping | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | fut_mapping/active | — |
| fut_settle | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | fut_settle/active | — |
| fut_trade_cal | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | fut_trade_cal/active | — |
| fut_weekly_detail | exhaustive_snapshot | complete | 0 | 0 | 0/0 | not_needed | fut_weekly_detail/active | — |
| fut_weekly_monthly | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | fut_weekly_monthly/active | — |
| fut_wsr | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | fut_wsr/active | — |
| fx_obasic | exhaustive_snapshot | complete | 0 | 0 | 0/0 | not_needed | fx_obasic/active | — |
| ggt_daily | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | ggt_daily/active | — |
| ggt_monthly | expected_partition | complete | 0 | 0 | 0/0 | not_needed | ggt_monthly/active | — |
| ggt_top10 | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | ggt_top10/active | — |
| gz_index | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | gz_index/active | — |
| hibor | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | hibor/active | — |
| hk_basic | exhaustive_snapshot | complete | 0 | 0 | 0/0 | not_needed | hk_basic/active | — |
| hk_daily | expected_partition | gaps | 5 | 0 | 5/0 | backfill_in_progress | hk_daily/active | 2026-09-25, 2026-10-02, 2026-10-05, 2026-10-06, 2026-10-07 |
| hk_hold | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | hk_hold/active | — |
| hk_tradecal | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | hk_tradecal/active | — |
| hm_list | exhaustive_snapshot | complete | 0 | 0 | 0/0 | not_needed | hm_list/active | — |
| hsgt_top10 | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | hsgt_top10/active | — |
| idx_anns | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | idx_anns/active | — |
| idx_factor_pro | expected_partition | complete | 0 | 0 | 0/0 | not_needed | idx_factor_pro/active | — |
| income | expected_partition | complete | 0 | 0 | 0/0 | not_needed | income/active | — |
| index_basic | exhaustive_snapshot | complete | 0 | 0 | 0/0 | not_needed | index_basic/active | — |
| index_classify | exhaustive_snapshot | complete | 0 | 0 | 0/0 | not_needed | index_classify/active | — |
| index_daily | expected_partition | complete | 0 | 0 | 0/0 | not_needed | index_daily/active | — |
| index_dailybasic | expected_partition | complete | 0 | 0 | 0/0 | not_needed | index_dailybasic/active | — |
| index_global | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | index_global/active | — |
| index_member_all | exhaustive_snapshot | complete | 0 | 0 | 0/0 | not_needed | index_member_all/active | — |
| index_monthly | expected_partition | complete | 0 | 0 | 0/0 | not_needed | index_monthly/active | — |
| index_weekly | expected_partition | complete | 0 | 0 | 0/0 | not_needed | index_weekly/active | — |
| index_weight | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | index_weight/active | — |
| industry_daily | expected_partition | complete | 0 | 0 | 0/0 | not_needed | ths_daily/active | — |
| kpl_concept_cons | expected_partition | complete | 0 | 0 | 0/0 | not_needed | kpl_concept_cons/active | — |
| kpl_list | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | kpl_list/active | — |
| libor | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | libor/active | — |
| limit_cpt_list | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | limit_cpt_list/active | — |
| limit_list_d | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | limit_list_d/active | — |
| limit_list_ths | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | limit_list_ths/active | — |
| limit_step | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | limit_step/active | — |
| major_news | exhaustive_snapshot | complete | 0 | 0 | 0/0 | not_needed | major_news/active | — |
| margin | expected_partition | complete | 0 | 0 | 0/0 | not_needed | margin/active | — |
| margin_detail | expected_partition | complete | 0 | 0 | 0/0 | not_needed | margin_detail/active | — |
| margin_secs | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | margin_secs/active | — |
| mkt_idx_bmk | exhaustive_snapshot | complete | 0 | 0 | 0/0 | not_needed | mkt_idx_bmk/active | — |
| moneyflow | expected_partition | complete | 0 | 0 | 0/0 | not_needed | moneyflow/active | — |
| moneyflow_cnt_ths | expected_partition | complete | 0 | 0 | 0/0 | not_needed | moneyflow_cnt_ths/active | — |
| moneyflow_dc | expected_partition | gaps | 12 | 0 | 1/0 | backfill_in_progress | moneyflow_dc/active | 2026-09-28, 2026-09-29, 2026-09-30, 2026-10-08, 2026-10-09 |
| moneyflow_hsgt | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | moneyflow_hsgt/active | — |
| moneyflow_ind_dc | expected_partition | complete | 0 | 0 | 0/0 | not_needed | moneyflow_ind_dc/active | — |
| moneyflow_ind_ths | expected_partition | complete | 0 | 0 | 0/0 | not_needed | moneyflow_ind_ths/active | — |
| moneyflow_mkt_dc | expected_partition | complete | 0 | 0 | 0/0 | not_needed | moneyflow_mkt_dc/active | — |
| moneyflow_ths | expected_partition | complete | 0 | 0 | 0/0 | not_needed | moneyflow_ths/active | — |
| namechange | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | namechange/active | — |
| new_share | exhaustive_snapshot | complete | 0 | 0 | 0/0 | not_needed | new_share/active | — |
| opt_basic | exhaustive_snapshot | complete | 0 | 0 | 0/0 | not_needed | opt_basic/active | — |
| opt_daily | expected_partition | gaps | 11 | 0 | 1/0 | backfill_in_progress | opt_daily/active | 2026-09-28, 2026-09-29, 2026-09-30, 2026-10-08, 2026-10-09 |
| p_get | exhaustive_snapshot | unverified | 0 | 0 | 0/0 | manual_scope_required | p_get/active | — |
| p_list | exhaustive_snapshot | complete | 0 | 0 | 0/0 | not_needed | p_list/active | — |
| pledge_detail | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | pledge_detail/active | — |
| pledge_stat | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | pledge_stat/active | — |
| repo_daily | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | repo_daily/active | — |
| report_rc | expected_partition | gaps | 11 | 0 | 11/0 | backfill_in_progress | report_rc/active | 2026-10-01, 2026-10-02, 2026-10-03, 2026-10-04, 2026-10-05 |
| repurchase | expected_partition | complete | 0 | 0 | 0/0 | not_needed | repurchase/active | — |
| rt_hk_k | exhaustive_snapshot | unverified | 0 | 0 | 0/0 | manual_scope_required | rt_hk_k/active | — |
| sf_month | expected_partition | complete | 0 | 0 | 0/0 | not_needed | sf_month/active | — |
| sge_basic | exhaustive_snapshot | complete | 0 | 0 | 0/0 | not_needed | sge_basic/active | — |
| sge_daily | expected_partition | complete | 0 | 0 | 0/0 | not_needed | sge_daily/active | — |
| share_float | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | share_float/active | — |
| shibor | expected_partition | complete | 0 | 0 | 0/0 | not_needed | shibor/active | — |
| shibor_quote | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | shibor_quote/active | — |
| slb_len | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | slb_len/active | — |
| slb_len_mm | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | slb_len_mm/active | — |
| slb_sec | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | slb_sec/active | — |
| slb_sec_detail | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | slb_sec_detail/active | — |
| stk_account | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | stk_account/active | — |
| stk_ah_comparison | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | stk_ah_comparison/active | — |
| stk_alert | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | stk_alert/active | — |
| stk_auction | expected_partition | complete | 0 | 0 | 0/0 | not_needed | stk_auction/active | — |
| stk_auction_c | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | stk_auction_c/active | — |
| stk_auction_o | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | stk_auction_o/active | — |
| stk_factor | expected_partition | gaps | 1 | 16 | 17/0 | backfill_in_progress | stk_factor/active | 1993-01-03 |
| stk_factor_pro | expected_partition | gaps | 1 | 34 | 35/0 | backfill_in_progress | stk_factor_pro/active | 1993-01-03 |
| stk_high_shock | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | stk_high_shock/active | — |
| stk_holdernumber | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | stk_holdernumber/active | — |
| stk_holdertrade | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | stk_holdertrade/active | — |
| stk_managers | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | stk_managers/active | — |
| stk_mins | exhaustive_snapshot | unverified | 0 | 0 | 0/0 | manual_scope_required | stk_mins/active | — |
| stk_nineturn | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | stk_nineturn/active | — |
| stk_rewards | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | stk_rewards/active | — |
| stk_shock | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | stk_shock/active | — |
| stk_surv | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | stk_surv/active | — |
| stk_week_month_adj | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | stk_week_month_adj/active | — |
| stk_weekly_monthly | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | stk_weekly_monthly/active | — |
| stock_basic | exhaustive_snapshot | complete | 0 | 0 | 0/0 | not_needed | stock_basic/active | — |
| stock_company | exhaustive_snapshot | complete | 0 | 0 | 0/0 | not_needed | stock_company/active | — |
| stock_daily | expected_partition | complete | 0 | 0 | 0/0 | not_needed | daily/active | — |
| stock_daily_basic | expected_partition | complete | 0 | 0 | 0/0 | not_needed | daily_basic/active | — |
| stock_hsgt | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | stock_hsgt/active | — |
| stock_limit | expected_partition | complete | 0 | 0 | 0/0 | not_needed | stk_limit/active | — |
| stock_st | expected_partition | gaps | 20 | 0 | 20/0 | backfill_in_progress | stock_st/active | 2025-11-21, 2025-11-24, 2025-11-25, 2025-11-26, 2025-12-09 |
| stock_suspend | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | suspend_d/active | — |
| sw_daily | expected_partition | complete | 0 | 0 | 0/0 | not_needed | sw_daily/active | — |
| sz_daily_info | expected_partition | complete | 0 | 0 | 0/0 | not_needed | sz_daily_info/active | — |
| tdx_daily | expected_partition | complete | 0 | 0 | 0/0 | not_needed | tdx_daily/active | — |
| tdx_index | expected_partition | complete | 0 | 0 | 0/0 | not_needed | tdx_index/active | — |
| tdx_member | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | tdx_member/active | — |
| technical_factor_snapshot | expected_partition | complete | 0 | 0 | 0/0 | not_needed | technical_factor_snapshot/active | — |
| ths_hot | expected_partition | complete | 0 | 0 | 0/0 | not_needed | ths_hot/active | — |
| ths_index | exhaustive_snapshot | complete | 0 | 0 | 0/0 | not_needed | ths_index/active | — |
| ths_member | exhaustive_snapshot | complete | 0 | 0 | 0/0 | not_needed | ths_member/active | — |
| top10_cb_holders | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | top10_cb_holders/active | — |
| top10_floatholders | expected_partition | complete | 0 | 0 | 0/0 | not_needed | top10_floatholders/active | — |
| top10_holders | expected_partition | complete | 0 | 0 | 0/0 | not_needed | top10_holders/active | — |
| top_inst | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | top_inst/active | — |
| top_list | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | top_list/active | — |
| trade_calendar | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | trade_cal/active | — |
| tushare_raw | exhaustive_snapshot | unverified | 0 | 0 | 0/0 | evidence_sidecar_not_applicable | —/not_applicable | — |
| us_basic | exhaustive_snapshot | complete | 0 | 0 | 0/0 | not_needed | us_basic/active | — |
| us_daily | expected_partition | gaps | 9249 | 21 | 0/0 | deferred_by_research_scope | us_daily/active | 1990-01-02, 1990-01-03, 1990-01-04, 1990-01-05, 1990-01-08 |
| us_tbr | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | us_tbr/active | — |
| us_tltr | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | us_tltr/active | — |
| us_tradecal | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | us_tradecal/active | — |
| us_trltr | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | us_trltr/active | — |
| us_trycr | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | us_trycr/active | — |
| us_tycr | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | us_tycr/active | — |
| wz_index | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | wz_index/active | — |

## V2 缺口实例规划（只读）

| 任务 | 逻辑周期实例数 | 输出数据集 | 周期样例 |
|---|---:|---|---|
| cyq_chips | 2110 | cyq_chips | 2018-01-02, 2018-01-03, 2018-01-04, 2018-01-05, 2018-01-08 |
| stk_factor_pro | 35 | stk_factor_pro | 1991-02-01, 1991-02-20, 1991-02-21, 1991-02-22, 1991-02-25 |
| stock_st | 20 | stock_st | 2025-11-21, 2025-11-24, 2025-11-25, 2025-11-26, 2025-12-09 |
| stk_factor | 17 | stk_factor | 1991-02-01, 1991-02-20, 1991-02-21, 1991-02-22, 1991-02-25 |
| factor_value | 14 | factor_value | 2026-09-10, 2026-09-22, 2026-09-28, 2026-09-29, 2026-09-30 |
| etf_sh_cons | 12 | etf_sh_cons | 2026-09-28, 2026-09-29, 2026-09-30, 2026-10-08, 2026-10-09 |
| etf_sz_cons | 12 | etf_sz_cons | 2026-09-28, 2026-09-29, 2026-09-30, 2026-10-08, 2026-10-09 |
| fut_index_daily | 12 | fut_index_daily | 2026-09-28, 2026-09-29, 2026-09-30, 2026-10-08, 2026-10-09 |
| moneyflow_dc | 12 | moneyflow_dc | 2026-09-28, 2026-09-29, 2026-09-30, 2026-10-08, 2026-10-09 |
| dc_index | 11 | dc_index | 2026-09-28, 2026-09-29, 2026-09-30, 2026-10-08, 2026-10-09 |
| opt_daily | 11 | opt_daily | 2026-09-28, 2026-09-29, 2026-09-30, 2026-10-08, 2026-10-09 |
| report_rc | 11 | report_rc | 2026-10-01, 2026-10-02, 2026-10-03, 2026-10-04, 2026-10-05 |
| hk_daily | 5 | hk_daily | 2026-09-25, 2026-10-02, 2026-10-05, 2026-10-06, 2026-10-07 |

## 口径

- `expected_partition`：有明确交易日/月/季度预期，可发现从未采集的日期。
- `observed_scope_transport`：稀疏事件不虚构每日必须有数据；按声明的采集范围、分页耗尽和终态证明审计。
- `exhaustive_snapshot`：无日期数据必须有全量快照成功证明、有效空结果证明或完整分页证明。
- `backfill_in_progress`：存在历史/初始化/修复 V2 执行实例；盘中统一延后到 16:00 后执行。
- `not_backfilled`：存在缺口或未验证状态，但当前没有对应 V2 执行实例，需要补计划或人工判定上游边界。
- `history_boundary_review`：候选日期早于本地首个已观测分区，但上游没有给出该数据集的权威可用起点。交易日历只能证明市场开市，不能证明接口当日已经存在或应发布；在补充契约起点前不得把这些日期误报为缺失。
