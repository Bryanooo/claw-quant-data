# Tushare 通用接口标准化表

本目录由接口契约生成。完整字段、身份和类型契约统一保存在
[contracts.json](contracts.json)，不再为每张表复制一份 Markdown。每个表均保留原始记录哈希、
采集时间、契约版本和契约外字段。
原始 JSON 仍保存在 `tushare_raw_record`，标准化失败记录进入
`sys_tushare_normalization_error`，字段漂移进入 `sys_tushare_schema_drift`。

| 接口 | PostgreSQL 表 | 字段数 | 主日期字段 |
|---|---|---:|---|
| `adj_factor` | `tushare_norm_adj_factor` | 3 | `trade_date` |
| `bak_daily` | `tushare_norm_bak_daily` | 31 | `trade_date` |
| `bc_bestotcqt` | `tushare_norm_bc_bestotcqt` | 11 | `trade_date` |
| `bc_otcqt` | `tushare_norm_bc_otcqt` | 13 | `trade_date` |
| `bond_blk` | `tushare_norm_bond_blk` | 6 | `trade_date` |
| `bond_blk_detail` | `tushare_norm_bond_blk_detail` | 8 | `trade_date` |
| `cb_basic` | `tushare_norm_cb_basic` | 38 | `-` |
| `cb_call` | `tushare_norm_cb_call` | 11 | `ann_date` |
| `cb_daily` | `tushare_norm_cb_daily` | 15 | `trade_date` |
| `cb_factor_pro` | `tushare_norm_cb_factor_pro` | 89 | `trade_date` |
| `cb_issue` | `tushare_norm_cb_issue` | 35 | `ann_date` |
| `cb_rate` | `tushare_norm_cb_rate` | 5 | `-` |
| `cb_rating` | `tushare_norm_cb_rating` | 8 | `ann_date` |
| `cb_share` | `tushare_norm_cb_share` | 15 | `end_date` |
| `ci_daily` | `tushare_norm_ci_daily` | 11 | `trade_date` |
| `ci_index_member` | `tushare_norm_ci_index_member` | 11 | `-` |
| `cn_cpi` | `tushare_norm_cn_cpi` | 13 | `-` |
| `cn_gdp` | `tushare_norm_cn_gdp` | 9 | `-` |
| `cn_m` | `tushare_norm_cn_m` | 10 | `-` |
| `cn_pmi` | `tushare_norm_cn_pmi` | 60 | `-` |
| `cn_ppi` | `tushare_norm_cn_ppi` | 31 | `-` |
| `cn_schedule` | `tushare_norm_cn_schedule` | 5 | `publish_date` |
| `daily_basic` | `tushare_norm_daily_basic` | 19 | `trade_date` |
| `daily_info` | `tushare_norm_daily_info` | 14 | `trade_date` |
| `eco_cal` | `tushare_norm_eco_cal` | 8 | `date` |
| `etf_basic` | `tushare_norm_etf_basic` | 14 | `-` |
| `etf_index` | `tushare_norm_etf_index` | 8 | `-` |
| `etf_sh_cons` | `tushare_norm_etf_sh_cons` | 10 | `trade_date` |
| `etf_share_size` | `tushare_norm_etf_share_size` | 8 | `trade_date` |
| `etf_sz_cons` | `tushare_norm_etf_sz_cons` | 11 | `trade_date` |
| `factor_value` | `tushare_norm_factor_value` | 4 | `trade_date` |
| `fina_audit` | `tushare_norm_fina_audit` | 7 | `end_date` |
| `ft_limit` | `tushare_norm_ft_limit` | 8 | `trade_date` |
| `fund_adj` | `tushare_norm_fund_adj` | 3 | `trade_date` |
| `fund_basic` | `tushare_norm_fund_basic` | 25 | `-` |
| `fund_company` | `tushare_norm_fund_company` | 18 | `end_date` |
| `fund_daily` | `tushare_norm_fund_daily` | 11 | `trade_date` |
| `fund_div` | `tushare_norm_fund_div` | 16 | `ann_date` |
| `fund_factor_pro` | `tushare_norm_fund_factor_pro` | 90 | `trade_date` |
| `fund_manager` | `tushare_norm_fund_manager` | 10 | `begin_date` |
| `fund_nav` | `tushare_norm_fund_nav` | 9 | `nav_date` |
| `fund_portfolio` | `tushare_norm_fund_portfolio` | 8 | `end_date` |
| `fund_share` | `tushare_norm_fund_share` | 3 | `trade_date` |
| `fut_basic` | `tushare_norm_fut_basic` | 16 | `-` |
| `fut_daily` | `tushare_norm_fut_daily` | 16 | `trade_date` |
| `fut_holding` | `tushare_norm_fut_holding` | 10 | `trade_date` |
| `fut_index_daily` | `tushare_norm_fut_index_daily` | 11 | `trade_date` |
| `fut_mapping` | `tushare_norm_fut_mapping` | 3 | `trade_date` |
| `fut_settle` | `tushare_norm_fut_settle` | 12 | `trade_date` |
| `fut_trade_cal` | `tushare_norm_fut_trade_cal` | 4 | `cal_date` |
| `fut_weekly_detail` | `tushare_norm_fut_weekly_detail` | 17 | `-` |
| `fut_weekly_monthly` | `tushare_norm_fut_weekly_monthly` | 18 | `trade_date` |
| `fut_wsr` | `tushare_norm_fut_wsr` | 17 | `trade_date` |
| `gz_index` | `tushare_norm_gz_index` | 7 | `date` |
| `hibor` | `tushare_norm_hibor` | 9 | `date` |
| `hk_basic` | `tushare_norm_hk_basic` | 12 | `-` |
| `hk_daily` | `tushare_norm_hk_daily` | 11 | `trade_date` |
| `hk_tradecal` | `tushare_norm_hk_tradecal` | 3 | `cal_date` |
| `idx_anns` | `tushare_norm_idx_anns` | 5 | `ann_date` |
| `idx_factor_pro` | `tushare_norm_idx_factor_pro` | 89 | `trade_date` |
| `index_classify` | `tushare_norm_index_classify` | 7 | `-` |
| `index_member_all` | `tushare_norm_index_member_all` | 11 | `-` |
| `index_weight` | `tushare_norm_index_weight` | 4 | `trade_date` |
| `libor` | `tushare_norm_libor` | 9 | `date` |
| `limit_list_ths` | `tushare_norm_limit_list_ths` | 24 | `trade_date` |
| `major_news` | `tushare_norm_major_news` | 4 | `-` |
| `mkt_idx_bmk` | `tushare_norm_mkt_idx_bmk` | 8 | `-` |
| `opt_basic` | `tushare_norm_opt_basic` | 20 | `-` |
| `opt_daily` | `tushare_norm_opt_daily` | 13 | `trade_date` |
| `p_get` | `tushare_norm_p_get` | 8 | `-` |
| `p_list` | `tushare_norm_p_list` | 5 | `-` |
| `repo_daily` | `tushare_norm_repo_daily` | 12 | `trade_date` |
| `rt_hk_k` | `tushare_norm_rt_hk_k` | 8 | `-` |
| `sf_month` | `tushare_norm_sf_month` | 4 | `-` |
| `shibor` | `tushare_norm_shibor` | 9 | `date` |
| `shibor_lpr` | `tushare_norm_shibor_lpr` | 3 | `date` |
| `shibor_quote` | `tushare_norm_shibor_quote` | 18 | `date` |
| `slb_len_mm` | `tushare_norm_slb_len_mm` | 7 | `trade_date` |
| `slb_sec` | `tushare_norm_slb_sec` | 7 | `trade_date` |
| `slb_sec_detail` | `tushare_norm_slb_sec_detail` | 6 | `trade_date` |
| `stk_account` | `tushare_norm_stk_account` | 5 | `date` |
| `stk_factor` | `tushare_norm_stk_factor` | 35 | `trade_date` |
| `stk_mins` | `tushare_norm_stk_mins` | 8 | `-` |
| `stk_week_month_adj` | `tushare_norm_stk_week_month_adj` | 21 | `trade_date` |
| `sw_daily` | `tushare_norm_sw_daily` | 15 | `trade_date` |
| `sz_daily_info` | `tushare_norm_sz_daily_info` | 9 | `trade_date` |
| `top10_cb_holders` | `tushare_norm_top10_cb_holders` | 6 | `end_date` |
| `us_basic` | `tushare_norm_us_basic` | 6 | `-` |
| `us_tbr` | `tushare_norm_us_tbr` | 13 | `date` |
| `us_tltr` | `tushare_norm_us_tltr` | 4 | `date` |
| `us_tradecal` | `tushare_norm_us_tradecal` | 3 | `cal_date` |
| `us_trltr` | `tushare_norm_us_trltr` | 2 | `date` |
| `us_trycr` | `tushare_norm_us_trycr` | 6 | `date` |
| `us_tycr` | `tushare_norm_us_tycr` | 14 | `date` |
| `wz_index` | `tushare_norm_wz_index` | 13 | `date` |
