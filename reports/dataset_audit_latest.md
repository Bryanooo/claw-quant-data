# 全量数据集严格审计报告

生成时间：`2026-10-01T00:07:57.633950+08:00`

## 结论摘要

- 数据集：194；具备审计能力：194；缺少审计能力：0。
- 审计模式：`{'exhaustive_snapshot': 32, 'expected_partition': 50, 'observed_scope_transport': 112}`。
- 业务数据综合状态：`{'complete': 107, 'empty': 30, 'unverified': 56}`；最新有界审计状态：`{'complete': 124, 'empty': 32, 'unverified': 38}`。
- 已确认缺失分区：0；存在数据但不完整/缺少传输证明：0。
- 数据集历史可用起点尚未证明、不得直接当成缺失的候选分区：91930。
- 旧规则遗留、必须重审后才能判定的分区：0。
- 补采状态：`{'evidence_sidecar_not_applicable': 1, 'history_boundary_review': 19, 'manual_scope_required': 34, 'not_needed': 137, 'observed_scope_not_globally_provable': 3}`。
- V2：控制面 `installed`；业务数据集基线映射 193/193；现有 V2 补采/修复实例 9795；按任务×逻辑周期仍需 0 个实例。

> `success` 只表示任务执行完成；“最新有界审计通过”也不自动等于全部历史完整。综合状态还会合并全历史分区账本、旧规则版本和活动补采。`unverified` 不得解释为完整。

## 逐数据集明细

| 数据集 | 审计模式 | 状态 | 缺失 | 部分/未证明 | 补采队列/运行 | 处理状态 | V2 任务/定义 | 缺失日期样例 |
|---|---|---:|---:|---:|---:|---|---|---|
| adj_factor | expected_partition | complete | 0 | 0 | 0/0 | not_needed | adj_factor/active | — |
| bak_basic | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | bak_basic/active | — |
| bak_daily | expected_partition | complete | 0 | 0 | 0/0 | not_needed | bak_daily/active | — |
| balancesheet | expected_partition | complete | 0 | 0 | 0/0 | not_needed | balancesheet/active | — |
| bc_bestotcqt | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | bc_bestotcqt/active | — |
| bc_otcqt | observed_scope_transport | unverified | 0 | 0 | 0/0 | manual_scope_required | bc_otcqt/active | — |
| block_trade | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | block_trade/active | — |
| bond_blk | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | bond_blk/active | — |
| bond_blk_detail | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | bond_blk_detail/active | — |
| broker_recommend | exhaustive_snapshot | complete | 0 | 0 | 0/0 | not_needed | broker_recommend/active | — |
| bse_mapping | exhaustive_snapshot | complete | 0 | 0 | 0/0 | not_needed | bse_mapping/active | — |
| cashflow | expected_partition | unverified | 0 | 0 | 0/0 | history_boundary_review | cashflow/active | — |
| cb_basic | exhaustive_snapshot | complete | 0 | 0 | 0/0 | not_needed | cb_basic/active | — |
| cb_call | observed_scope_transport | empty | 0 | 0 | 0/0 | not_needed | cb_call/active | — |
| cb_daily | expected_partition | complete | 0 | 0 | 0/0 | not_needed | cb_daily/active | — |
| cb_factor_pro | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | cb_factor_pro/active | — |
| cb_issue | observed_scope_transport | empty | 0 | 0 | 0/0 | not_needed | cb_issue/active | — |
| cb_rate | exhaustive_snapshot | unverified | 0 | 0 | 0/0 | manual_scope_required | cb_rate/active | — |
| cb_rating | observed_scope_transport | unverified | 0 | 0 | 0/0 | manual_scope_required | cb_rating/active | — |
| cb_share | observed_scope_transport | unverified | 0 | 0 | 0/0 | manual_scope_required | cb_share/active | — |
| ccass_hold | observed_scope_transport | empty | 0 | 0 | 0/0 | not_needed | ccass_hold/active | — |
| ccass_hold_detail | observed_scope_transport | unverified | 0 | 0 | 0/0 | manual_scope_required | ccass_hold_detail/active | — |
| ci_daily | expected_partition | complete | 0 | 0 | 0/0 | not_needed | ci_daily/active | — |
| ci_index_member | exhaustive_snapshot | unverified | 0 | 0 | 0/0 | manual_scope_required | ci_index_member/active | — |
| cn_cpi | expected_partition | empty | 0 | 0 | 0/0 | not_needed | cn_cpi/active | — |
| cn_gdp | expected_partition | empty | 0 | 0 | 0/0 | not_needed | cn_gdp/active | — |
| cn_m | expected_partition | empty | 0 | 0 | 0/0 | not_needed | cn_m/active | — |
| cn_pmi | expected_partition | complete | 0 | 0 | 0/0 | not_needed | cn_pmi/active | — |
| cn_ppi | expected_partition | empty | 0 | 0 | 0/0 | not_needed | cn_ppi/active | — |
| cn_schedule | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | cn_schedule/active | — |
| cyq_chips | observed_scope_transport | unverified | 0 | 0 | 0/0 | manual_scope_required | cyq_chips/active | — |
| cyq_perf | observed_scope_transport | unverified | 0 | 0 | 0/0 | manual_scope_required | cyq_perf/active | — |
| daily_basic | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | daily_basic/active | — |
| daily_info | expected_partition | complete | 0 | 0 | 0/0 | not_needed | daily_info/active | — |
| dc_concept | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | dc_concept/active | — |
| dc_concept_cons | observed_scope_transport | unverified | 0 | 0 | 0/0 | manual_scope_required | dc_concept_cons/active | — |
| dc_daily | expected_partition | unverified | 0 | 0 | 0/0 | history_boundary_review | dc_daily/active | — |
| dc_hot | observed_scope_transport | empty | 0 | 0 | 0/0 | not_needed | dc_hot/active | — |
| dc_index | observed_scope_transport | unverified | 0 | 0 | 0/0 | manual_scope_required | dc_index/active | — |
| dc_member | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | dc_member/active | — |
| disclosure_date | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | disclosure_date/active | — |
| dividend | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | dividend/active | — |
| eco_cal | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | eco_cal/active | — |
| etf_basic | exhaustive_snapshot | complete | 0 | 0 | 0/0 | not_needed | etf_basic/active | — |
| etf_index | exhaustive_snapshot | complete | 0 | 0 | 0/0 | not_needed | etf_index/active | — |
| etf_sh_cons | observed_scope_transport | unverified | 0 | 0 | 0/0 | manual_scope_required | etf_sh_cons/active | — |
| etf_share_size | expected_partition | complete | 0 | 0 | 0/0 | not_needed | etf_share_size/active | — |
| etf_sz_cons | observed_scope_transport | unverified | 0 | 0 | 0/0 | manual_scope_required | etf_sz_cons/active | — |
| express | observed_scope_transport | unverified | 0 | 0 | 0/0 | manual_scope_required | express/active | — |
| factor_value | observed_scope_transport | unverified | 0 | 0 | 0/0 | manual_scope_required | factor_value/active | — |
| fina_audit | observed_scope_transport | unverified | 0 | 0 | 0/0 | manual_scope_required | fina_audit/active | — |
| fina_mainbz | observed_scope_transport | unverified | 0 | 0 | 0/0 | manual_scope_required | fina_mainbz/active | — |
| financial_indicator | expected_partition | complete | 0 | 0 | 0/0 | not_needed | financial_indicator/active | — |
| forecast | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | forecast/active | — |
| forex_daily | observed_scope_transport | empty | 0 | 0 | 0/0 | not_needed | fx_daily/active | — |
| ft_limit | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | ft_limit/active | — |
| fund_adj | expected_partition | unverified | 0 | 0 | 0/0 | history_boundary_review | fund_adj/active | — |
| fund_basic | exhaustive_snapshot | unverified | 0 | 0 | 0/0 | manual_scope_required | fund_basic/active | — |
| fund_company | observed_scope_transport | unverified | 0 | 0 | 0/0 | observed_scope_not_globally_provable | fund_company/active | — |
| fund_daily | expected_partition | unverified | 0 | 0 | 0/0 | history_boundary_review | fund_daily/active | — |
| fund_div | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | fund_div/active | — |
| fund_factor_pro | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | fund_factor_pro/active | — |
| fund_manager | observed_scope_transport | unverified | 0 | 0 | 0/0 | observed_scope_not_globally_provable | fund_manager/active | — |
| fund_nav | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | fund_nav/active | — |
| fund_portfolio | observed_scope_transport | empty | 0 | 0 | 0/0 | not_needed | fund_portfolio/active | — |
| fund_share | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | fund_share/active | — |
| fut_basic | exhaustive_snapshot | unverified | 0 | 0 | 0/0 | manual_scope_required | fut_basic/active | — |
| fut_daily | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | fut_daily/active | — |
| fut_holding | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | fut_holding/active | — |
| fut_index_daily | observed_scope_transport | unverified | 0 | 0 | 0/0 | manual_scope_required | fut_index_daily/active | — |
| fut_mapping | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | fut_mapping/active | — |
| fut_settle | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | fut_settle/active | — |
| fut_trade_cal | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | fut_trade_cal/active | — |
| fut_weekly_detail | exhaustive_snapshot | complete | 0 | 0 | 0/0 | not_needed | fut_weekly_detail/active | — |
| fut_weekly_monthly | observed_scope_transport | unverified | 0 | 0 | 0/0 | manual_scope_required | fut_weekly_monthly/active | — |
| fut_wsr | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | fut_wsr/active | — |
| fx_obasic | exhaustive_snapshot | complete | 0 | 0 | 0/0 | not_needed | fx_obasic/active | — |
| ggt_daily | observed_scope_transport | empty | 0 | 0 | 0/0 | not_needed | ggt_daily/active | — |
| ggt_monthly | expected_partition | complete | 0 | 0 | 0/0 | not_needed | ggt_monthly/active | — |
| ggt_top10 | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | ggt_top10/active | — |
| gz_index | observed_scope_transport | empty | 0 | 0 | 0/0 | not_needed | gz_index/active | — |
| hibor | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | hibor/active | — |
| hk_basic | exhaustive_snapshot | complete | 0 | 0 | 0/0 | not_needed | hk_basic/active | — |
| hk_daily | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | hk_daily/active | — |
| hk_hold | observed_scope_transport | empty | 0 | 0 | 0/0 | not_needed | hk_hold/active | — |
| hk_tradecal | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | hk_tradecal/active | — |
| hm_list | exhaustive_snapshot | complete | 0 | 0 | 0/0 | not_needed | hm_list/active | — |
| hsgt_top10 | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | hsgt_top10/active | — |
| idx_anns | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | idx_anns/active | — |
| idx_factor_pro | expected_partition | unverified | 0 | 0 | 0/0 | history_boundary_review | idx_factor_pro/active | — |
| income | expected_partition | complete | 0 | 0 | 0/0 | not_needed | income/active | — |
| index_basic | exhaustive_snapshot | complete | 0 | 0 | 0/0 | not_needed | index_basic/active | — |
| index_classify | exhaustive_snapshot | complete | 0 | 0 | 0/0 | not_needed | index_classify/active | — |
| index_daily | expected_partition | complete | 0 | 0 | 0/0 | not_needed | index_daily/active | — |
| index_dailybasic | expected_partition | complete | 0 | 0 | 0/0 | not_needed | index_dailybasic/active | — |
| index_global | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | index_global/active | — |
| index_member_all | exhaustive_snapshot | unverified | 0 | 0 | 0/0 | manual_scope_required | index_member_all/active | — |
| index_monthly | expected_partition | unverified | 0 | 0 | 0/0 | history_boundary_review | index_monthly/active | — |
| index_weekly | expected_partition | unverified | 0 | 0 | 0/0 | history_boundary_review | index_weekly/active | — |
| index_weight | observed_scope_transport | unverified | 0 | 0 | 0/0 | manual_scope_required | index_weight/active | — |
| industry_daily | expected_partition | complete | 0 | 0 | 0/0 | not_needed | ths_daily/active | — |
| kpl_concept_cons | expected_partition | unverified | 0 | 0 | 0/0 | history_boundary_review | kpl_concept_cons/active | — |
| kpl_list | observed_scope_transport | empty | 0 | 0 | 0/0 | not_needed | kpl_list/active | — |
| libor | observed_scope_transport | empty | 0 | 0 | 0/0 | not_needed | libor/active | — |
| limit_cpt_list | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | limit_cpt_list/active | — |
| limit_list_d | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | limit_list_d/active | — |
| limit_list_ths | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | limit_list_ths/active | — |
| limit_step | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | limit_step/active | — |
| major_news | exhaustive_snapshot | complete | 0 | 0 | 0/0 | not_needed | major_news/active | — |
| margin | expected_partition | unverified | 0 | 0 | 0/0 | history_boundary_review | margin/active | — |
| margin_detail | expected_partition | unverified | 0 | 0 | 0/0 | history_boundary_review | margin_detail/active | — |
| margin_secs | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | margin_secs/active | — |
| mkt_idx_bmk | exhaustive_snapshot | complete | 0 | 0 | 0/0 | not_needed | mkt_idx_bmk/active | — |
| moneyflow | expected_partition | unverified | 0 | 0 | 0/0 | history_boundary_review | moneyflow/active | — |
| moneyflow_cnt_ths | expected_partition | complete | 0 | 0 | 0/0 | not_needed | moneyflow_cnt_ths/active | — |
| moneyflow_dc | observed_scope_transport | unverified | 0 | 0 | 0/0 | manual_scope_required | moneyflow_dc/active | — |
| moneyflow_hsgt | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | moneyflow_hsgt/active | — |
| moneyflow_ind_dc | expected_partition | complete | 0 | 0 | 0/0 | not_needed | moneyflow_ind_dc/active | — |
| moneyflow_ind_ths | expected_partition | unverified | 0 | 0 | 0/0 | history_boundary_review | moneyflow_ind_ths/active | — |
| moneyflow_mkt_dc | expected_partition | unverified | 0 | 0 | 0/0 | history_boundary_review | moneyflow_mkt_dc/active | — |
| moneyflow_ths | expected_partition | complete | 0 | 0 | 0/0 | not_needed | moneyflow_ths/active | — |
| namechange | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | namechange/active | — |
| new_share | exhaustive_snapshot | empty | 0 | 0 | 0/0 | not_needed | new_share/active | — |
| opt_basic | exhaustive_snapshot | complete | 0 | 0 | 0/0 | not_needed | opt_basic/active | — |
| opt_daily | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | opt_daily/active | — |
| p_get | exhaustive_snapshot | unverified | 0 | 0 | 0/0 | manual_scope_required | p_get/active | — |
| p_list | exhaustive_snapshot | complete | 0 | 0 | 0/0 | not_needed | p_list/active | — |
| pledge_detail | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | pledge_detail/active | — |
| pledge_stat | observed_scope_transport | unverified | 0 | 0 | 0/0 | manual_scope_required | pledge_stat/active | — |
| repo_daily | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | repo_daily/active | — |
| report_rc | exhaustive_snapshot | complete | 0 | 0 | 0/0 | not_needed | report_rc/active | — |
| repurchase | expected_partition | complete | 0 | 0 | 0/0 | not_needed | repurchase/active | — |
| rt_hk_k | exhaustive_snapshot | unverified | 0 | 0 | 0/0 | manual_scope_required | rt_hk_k/active | — |
| sf_month | expected_partition | empty | 0 | 0 | 0/0 | not_needed | sf_month/active | — |
| sge_basic | exhaustive_snapshot | complete | 0 | 0 | 0/0 | not_needed | sge_basic/active | — |
| sge_daily | expected_partition | unverified | 0 | 0 | 0/0 | history_boundary_review | sge_daily/active | — |
| share_float | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | share_float/active | — |
| shibor | expected_partition | unverified | 0 | 0 | 0/0 | history_boundary_review | shibor/active | — |
| shibor_lpr | expected_partition | empty | 0 | 0 | 0/0 | not_needed | shibor_lpr/active | — |
| shibor_quote | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | shibor_quote/active | — |
| slb_len | observed_scope_transport | empty | 0 | 0 | 0/0 | not_needed | slb_len/active | — |
| slb_len_mm | observed_scope_transport | empty | 0 | 0 | 0/0 | not_needed | slb_len_mm/active | — |
| slb_sec | observed_scope_transport | empty | 0 | 0 | 0/0 | not_needed | slb_sec/active | — |
| slb_sec_detail | observed_scope_transport | empty | 0 | 0 | 0/0 | not_needed | slb_sec_detail/active | — |
| stk_account | observed_scope_transport | empty | 0 | 0 | 0/0 | not_needed | stk_account/active | — |
| stk_ah_comparison | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | stk_ah_comparison/active | — |
| stk_alert | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | stk_alert/active | — |
| stk_auction | expected_partition | unverified | 0 | 0 | 0/0 | history_boundary_review | stk_auction/active | — |
| stk_auction_c | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | stk_auction_c/active | — |
| stk_auction_o | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | stk_auction_o/active | — |
| stk_factor | expected_partition | unverified | 0 | 0 | 0/0 | history_boundary_review | stk_factor/active | — |
| stk_factor_pro | expected_partition | unverified | 0 | 0 | 0/0 | history_boundary_review | stk_factor_pro/active | — |
| stk_high_shock | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | stk_high_shock/active | — |
| stk_holdernumber | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | stk_holdernumber/active | — |
| stk_holdertrade | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | stk_holdertrade/active | — |
| stk_managers | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | stk_managers/active | — |
| stk_mins | exhaustive_snapshot | unverified | 0 | 0 | 0/0 | manual_scope_required | stk_mins/active | — |
| stk_nineturn | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | stk_nineturn/active | — |
| stk_rewards | observed_scope_transport | unverified | 0 | 0 | 0/0 | manual_scope_required | stk_rewards/active | — |
| stk_shock | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | stk_shock/active | — |
| stk_surv | observed_scope_transport | empty | 0 | 0 | 0/0 | not_needed | stk_surv/active | — |
| stk_week_month_adj | observed_scope_transport | unverified | 0 | 0 | 0/0 | manual_scope_required | stk_week_month_adj/active | — |
| stk_weekly_monthly | observed_scope_transport | unverified | 0 | 0 | 0/0 | observed_scope_not_globally_provable | stk_weekly_monthly/active | — |
| stock_basic | exhaustive_snapshot | complete | 0 | 0 | 0/0 | not_needed | stock_basic/active | — |
| stock_company | exhaustive_snapshot | complete | 0 | 0 | 0/0 | not_needed | stock_company/active | — |
| stock_daily | expected_partition | complete | 0 | 0 | 0/0 | not_needed | daily/active | — |
| stock_daily_basic | expected_partition | complete | 0 | 0 | 0/0 | not_needed | daily_basic/active | — |
| stock_hsgt | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | stock_hsgt/active | — |
| stock_limit | expected_partition | complete | 0 | 0 | 0/0 | not_needed | stk_limit/active | — |
| stock_st | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | stock_st/active | — |
| stock_suspend | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | suspend_d/active | — |
| sw_daily | expected_partition | complete | 0 | 0 | 0/0 | not_needed | sw_daily/active | — |
| sz_daily_info | expected_partition | unverified | 0 | 0 | 0/0 | history_boundary_review | sz_daily_info/active | — |
| tdx_daily | expected_partition | complete | 0 | 0 | 0/0 | not_needed | tdx_daily/active | — |
| tdx_index | expected_partition | complete | 0 | 0 | 0/0 | not_needed | tdx_index/active | — |
| tdx_member | observed_scope_transport | unverified | 0 | 0 | 0/0 | manual_scope_required | tdx_member/active | — |
| ths_hot | expected_partition | complete | 0 | 0 | 0/0 | not_needed | ths_hot/active | — |
| ths_index | exhaustive_snapshot | complete | 0 | 0 | 0/0 | not_needed | ths_index/active | — |
| ths_member | exhaustive_snapshot | unverified | 0 | 0 | 0/0 | manual_scope_required | ths_member/active | — |
| top10_cb_holders | observed_scope_transport | unverified | 0 | 0 | 0/0 | manual_scope_required | top10_cb_holders/active | — |
| top10_floatholders | observed_scope_transport | unverified | 0 | 0 | 0/0 | manual_scope_required | top10_floatholders/active | — |
| top10_holders | observed_scope_transport | unverified | 0 | 0 | 0/0 | manual_scope_required | top10_holders/active | — |
| top_inst | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | top_inst/active | — |
| top_list | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | top_list/active | — |
| trade_calendar | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | trade_cal/active | — |
| tushare_raw | exhaustive_snapshot | unverified | 0 | 0 | 0/0 | evidence_sidecar_not_applicable | —/not_applicable | — |
| us_basic | exhaustive_snapshot | complete | 0 | 0 | 0/0 | not_needed | us_basic/active | — |
| us_tbr | observed_scope_transport | empty | 0 | 0 | 0/0 | not_needed | us_tbr/active | — |
| us_tltr | observed_scope_transport | empty | 0 | 0 | 0/0 | not_needed | us_tltr/active | — |
| us_tradecal | observed_scope_transport | complete | 0 | 0 | 0/0 | not_needed | us_tradecal/active | — |
| us_trltr | observed_scope_transport | empty | 0 | 0 | 0/0 | not_needed | us_trltr/active | — |
| us_trycr | observed_scope_transport | empty | 0 | 0 | 0/0 | not_needed | us_trycr/active | — |
| us_tycr | observed_scope_transport | empty | 0 | 0 | 0/0 | not_needed | us_tycr/active | — |
| wz_index | observed_scope_transport | empty | 0 | 0 | 0/0 | not_needed | wz_index/active | — |

## V2 缺口实例规划（只读）

| 任务 | 逻辑周期实例数 | 输出数据集 | 周期样例 |
|---|---:|---|---|

## 口径

- `expected_partition`：有明确交易日/月/季度预期，可发现从未采集的日期。
- `observed_scope_transport`：稀疏事件不虚构每日必须有数据；按声明的采集范围、分页耗尽和终态证明审计。
- `exhaustive_snapshot`：无日期数据必须有全量快照成功证明、有效空结果证明或完整分页证明。
- `backfill_in_progress`：存在历史/初始化/修复 V2 执行实例；盘中统一延后到 16:00 后执行。
- `not_backfilled`：存在缺口或未验证状态，但当前没有对应 V2 执行实例，需要补计划或人工判定上游边界。
- `history_boundary_review`：候选日期早于本地首个已观测分区，但上游没有给出该数据集的权威可用起点。交易日历只能证明市场开市，不能证明接口当日已经存在或应发布；在补充契约起点前不得把这些日期误报为缺失。
