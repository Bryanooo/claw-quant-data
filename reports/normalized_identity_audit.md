# 通用标准化表身份审计

生成时间：`2026-08-30T10:23:41.807583+00:00`

`_record_hash` 是完整上游 payload 的技术主键；业务身份字段用于版本分组和冲突审计，不承诺数据库唯一。
因此，观察数据唯一也不能单独作为创建唯一约束或 `current` 视图的依据。

## 汇总

| 合约 | 有数据 | 当前样本唯一 | 当前样本冲突 | 身份值为空 | 空表 |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 94 | 68 | 52 | 12 | 4 | 26 |

## 明细

| 接口 | 身份字段 | 可信度 | 行数 | 冲突组 | 冲突额外行 | 最大组 | 结论 |
| --- | --- | --- | ---: | ---: | ---: | ---: | --- |
| adj_factor | `trade_date, ts_code` | heuristic | 11129 | 0 | 0 | 1 | unique_in_observed_data |
| bak_daily | `trade_date, ts_code` | heuristic | 11124 | 0 | 0 | 1 | unique_in_observed_data |
| bc_bestotcqt | `trade_date, ts_code` | heuristic | 1438 | 0 | 0 | 1 | unique_in_observed_data |
| bc_otcqt | `trade_date, qt_time, bank, ts_code` | contract_reviewed | 6000 | 5 | 5 | 2 | nullable_business_identity |
| bond_blk | `trade_date, ts_code` | heuristic | 0 | 0 | 0 | 0 | empty |
| bond_blk_detail | `trade_date, ts_code` | heuristic | 0 | 0 | 0 | 0 | empty |
| cb_basic | `ts_code` | contract_reviewed | 2324 | 1162 | 1162 | 2 | non_unique_observed_identity |
| cb_call | `ts_code` | heuristic | 2 | 0 | 0 | 1 | unique_in_observed_data |
| cb_daily | `trade_date, ts_code` | contract_reviewed | 949 | 316 | 316 | 2 | non_unique_observed_identity |
| cb_factor_pro | `trade_date, ts_code` | heuristic | 633 | 0 | 0 | 1 | unique_in_observed_data |
| cb_issue | `ts_code` | heuristic | 0 | 0 | 0 | 0 | empty |
| cb_rate | `ts_code, rate_start_date, rate_end_date` | contract_reviewed | 1017 | 0 | 0 | 1 | nullable_business_identity |
| cb_rating | `ts_code, rating_date, rating_com_name, rating_type` | contract_reviewed | 776 | 0 | 0 | 1 | unique_in_observed_data |
| cb_share | `ts_code` | heuristic | 0 | 0 | 0 | 0 | empty |
| ci_daily | `trade_date, ts_code` | heuristic | 933 | 0 | 0 | 1 | unique_in_observed_data |
| ci_index_member | `ts_code` | heuristic | 5000 | 0 | 0 | 1 | unique_in_observed_data |
| cn_cpi | `month` | heuristic | 3 | 0 | 0 | 1 | unique_in_observed_data |
| cn_gdp | `quarter` | heuristic | 178 | 0 | 0 | 1 | unique_in_observed_data |
| cn_m | `month` | heuristic | 1 | 0 | 0 | 1 | unique_in_observed_data |
| cn_pmi | `month` | heuristic | 1 | 0 | 0 | 1 | unique_in_observed_data |
| cn_ppi | `month` | heuristic | 1 | 0 | 0 | 1 | unique_in_observed_data |
| cn_schedule | `month, publish_date, title` | contract_reviewed | 18 | 0 | 0 | 1 | unique_in_observed_data |
| daily_basic | `trade_date, ts_code` | contract_reviewed | 16641 | 5547 | 5547 | 2 | non_unique_observed_identity |
| daily_info | `trade_date, ts_code` | heuristic | 24 | 0 | 0 | 1 | unique_in_observed_data |
| eco_cal | `date` | heuristic | 2 | 0 | 0 | 1 | unique_in_observed_data |
| etf_basic | `ts_code` | heuristic | 1825 | 0 | 0 | 1 | unique_in_observed_data |
| etf_index | `ts_code` | heuristic | 560 | 0 | 0 | 1 | unique_in_observed_data |
| etf_sh_cons | `trade_date, ts_code, con_code` | contract_reviewed | 6000 | 0 | 0 | 1 | unique_in_observed_data |
| etf_share_size | `trade_date, ts_code` | contract_reviewed | 4217 | 922 | 922 | 2 | non_unique_observed_identity |
| etf_sz_cons | `trade_date, ts_code, con_code` | contract_reviewed | 6000 | 0 | 0 | 1 | unique_in_observed_data |
| factor_value | `trade_date, ts_code` | heuristic | 0 | 0 | 0 | 0 | empty |
| fina_audit | `ts_code` | heuristic | 0 | 0 | 0 | 0 | empty |
| ft_limit | `trade_date, ts_code` | heuristic | 1734 | 0 | 0 | 1 | unique_in_observed_data |
| fund_adj | `trade_date, ts_code` | heuristic | 4271 | 0 | 0 | 1 | unique_in_observed_data |
| fund_basic | `ts_code` | heuristic | 15000 | 0 | 0 | 1 | unique_in_observed_data |
| fund_company | `name` | contract_reviewed | 412 | 206 | 206 | 2 | non_unique_observed_identity |
| fund_daily | `trade_date, ts_code` | heuristic | 4225 | 0 | 0 | 1 | unique_in_observed_data |
| fund_div | `ts_code` | heuristic | 15 | 0 | 0 | 1 | unique_in_observed_data |
| fund_factor_pro | `trade_date, ts_code` | heuristic | 4224 | 0 | 0 | 1 | unique_in_observed_data |
| fund_manager | `ts_code, name, begin_date` | contract_reviewed | 84840 | 0 | 0 | 1 | nullable_business_identity |
| fund_nav | `nav_date, ts_code` | heuristic | 0 | 0 | 0 | 0 | empty |
| fund_portfolio | `ts_code` | heuristic | 0 | 0 | 0 | 0 | empty |
| fund_share | `trade_date, ts_code` | contract_reviewed | 5199 | 1734 | 1734 | 2 | non_unique_observed_identity |
| fut_basic | `ts_code` | contract_reviewed | 15225 | 4029 | 4029 | 2 | non_unique_observed_identity |
| fut_daily | `trade_date, ts_code` | contract_reviewed | 3216 | 1072 | 1072 | 2 | non_unique_observed_identity |
| fut_holding | `trade_date, symbol, broker` | contract_reviewed | 12000 | 4000 | 4000 | 2 | non_unique_observed_identity |
| fut_index_daily | `trade_date, ts_code` | heuristic | 0 | 0 | 0 | 0 | empty |
| fut_mapping | `trade_date, ts_code` | heuristic | 404 | 0 | 0 | 1 | unique_in_observed_data |
| fut_settle | `trade_date, ts_code` | contract_reviewed | 2733 | 911 | 911 | 2 | non_unique_observed_identity |
| fut_trade_cal | `cal_date` | heuristic | 2 | 0 | 0 | 1 | unique_in_observed_data |
| fut_weekly_detail | `week, exchange, prd` | contract_reviewed | 4000 | 0 | 0 | 1 | unique_in_observed_data |
| fut_weekly_monthly | `trade_date, ts_code` | heuristic | 0 | 0 | 0 | 0 | empty |
| fut_wsr | `trade_date, symbol, warehouse, wh_id, grade, brand, place` | contract_reviewed | 3092 | 413 | 417 | 4 | nullable_business_identity |
| gz_index | `date` | heuristic | 0 | 0 | 0 | 0 | empty |
| hibor | `date` | heuristic | 2 | 0 | 0 | 1 | unique_in_observed_data |
| hk_basic | `ts_code` | heuristic | 2781 | 0 | 0 | 1 | unique_in_observed_data |
| hk_daily | `trade_date, ts_code` | heuristic | 0 | 0 | 0 | 0 | empty |
| hk_tradecal | `cal_date` | heuristic | 2 | 0 | 0 | 1 | unique_in_observed_data |
| idx_anns | `title` | heuristic | 8 | 0 | 0 | 1 | unique_in_observed_data |
| idx_factor_pro | `trade_date, ts_code` | heuristic | 6946 | 0 | 0 | 1 | unique_in_observed_data |
| index_classify | `index_code` | heuristic | 359 | 0 | 0 | 1 | unique_in_observed_data |
| index_member_all | `ts_code` | heuristic | 3000 | 0 | 0 | 1 | unique_in_observed_data |
| index_weight | `trade_date, index_code` | heuristic | 0 | 0 | 0 | 0 | empty |
| libor | `date` | heuristic | 0 | 0 | 0 | 0 | empty |
| limit_list_ths | `trade_date, ts_code` | contract_reviewed | 239 | 81 | 81 | 2 | non_unique_observed_identity |
| major_news | `title` | heuristic | 0 | 0 | 0 | 0 | empty |
| mkt_idx_bmk | `ts_code` | heuristic | 141 | 0 | 0 | 1 | unique_in_observed_data |
| opt_basic | `ts_code` | heuristic | 12000 | 0 | 0 | 1 | unique_in_observed_data |
| opt_daily | `trade_date, ts_code` | heuristic | 30000 | 0 | 0 | 1 | unique_in_observed_data |
| p_get | `ts_code` | heuristic | 0 | 0 | 0 | 0 | empty |
| p_list | `id` | heuristic | 0 | 0 | 0 | 0 | empty |
| repo_daily | `trade_date, ts_code` | heuristic | 89 | 0 | 0 | 1 | unique_in_observed_data |
| sf_month | `month` | heuristic | 1 | 0 | 0 | 1 | unique_in_observed_data |
| shibor | `date` | heuristic | 2 | 0 | 0 | 1 | unique_in_observed_data |
| shibor_lpr | `date` | heuristic | 0 | 0 | 0 | 0 | empty |
| shibor_quote | `date, bank` | contract_reviewed | 35 | 0 | 0 | 1 | unique_in_observed_data |
| slb_len_mm | `trade_date, ts_code` | heuristic | 0 | 0 | 0 | 0 | empty |
| slb_sec | `trade_date, ts_code` | heuristic | 0 | 0 | 0 | 0 | empty |
| slb_sec_detail | `trade_date, ts_code` | heuristic | 0 | 0 | 0 | 0 | empty |
| stk_account | `date` | heuristic | 0 | 0 | 0 | 0 | empty |
| stk_factor | `trade_date, ts_code` | heuristic | 11093 | 0 | 0 | 1 | unique_in_observed_data |
| stk_mins | `ts_code` | heuristic | 0 | 0 | 0 | 0 | empty |
| stk_week_month_adj | `trade_date, ts_code` | heuristic | 0 | 0 | 0 | 0 | empty |
| sw_daily | `trade_date, ts_code` | heuristic | 878 | 0 | 0 | 1 | unique_in_observed_data |
| sz_daily_info | `trade_date, ts_code` | heuristic | 28 | 0 | 0 | 1 | unique_in_observed_data |
| top10_cb_holders | `ts_code` | heuristic | 0 | 0 | 0 | 0 | empty |
| us_basic | `ts_code` | contract_reviewed | 24230 | 52 | 54 | 4 | non_unique_observed_identity |
| us_tbr | `date` | heuristic | 2 | 0 | 0 | 1 | unique_in_observed_data |
| us_tltr | `date` | heuristic | 2 | 0 | 0 | 1 | unique_in_observed_data |
| us_tradecal | `cal_date` | heuristic | 2 | 0 | 0 | 1 | unique_in_observed_data |
| us_trltr | `date` | heuristic | 2 | 0 | 0 | 1 | unique_in_observed_data |
| us_trycr | `date` | heuristic | 2 | 0 | 0 | 1 | unique_in_observed_data |
| us_tycr | `date` | heuristic | 2 | 0 | 0 | 1 | unique_in_observed_data |
| wz_index | `date` | heuristic | 0 | 0 | 0 | 0 | empty |
