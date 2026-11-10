# 采集与派生能力核查

核查开始：2026-11-10 21:35:03.871463+08:00；完成：2026-11-10 21:49:16.639746+08:00。

> 近期待检范围按任务周期选择；完整历史另按契约起点比较。表内有行、任务 success、当前规则通过是不同证据。权限按登记契约列出，本次没有逐接口消耗额度探测。

已登记业务接口 419；对应常规采集与专项流程 203；采集自动入口分类 {'cron': 147, 'supplementary': 13, 'paused_policy': 31, 'manual': 12}。派生蓝图 15，已发布 4。

## 采集能力与启用范围

| 来源 | 业务接口 | 已映射任务 | 有自动入口 |
|---|---:|---:|---:|
| tushare | 245 | 203 | 157 |
| financial_data | 163 | 7 | 7 |
| chinabond | 2 | 1 | 1 |
| chinamoney | 2 | 1 | 1 |
| cninfo | 2 | 1 | 1 |
| pboc | 1 | 0 | 0 |
| sina | 3 | 0 | 0 |
| sse | 1 | 0 | 0 |

需明确范围后手动运行：`cb_rate`、`cb_rating`、`cb_share`、`dc_concept_cons`、`fina_audit`、`fina_mainbz`、`p_get`、`stk_mins`、`stk_week_month_adj`、`stk_weekly_monthly`、`tdx_member`、`top10_cb_holders`。

按策略暂停新增自动采集：`bc_bestotcqt`、`bc_otcqt`、`bond_blk`、`bond_blk_detail`、`ccass_hold`、`ccass_hold_detail`、`factor_value`、`ft_limit`、`fut_basic`、`fut_daily`、`fut_holding`、`fut_index_daily`、`fut_mapping`、`fut_settle`、`fut_trade_cal`、`fut_weekly_detail`、`fut_weekly_monthly`、`fut_wsr`、`fx_obasic`、`gz_index`、`hk_basic`、`hk_daily`、`hk_tradecal`、`libor`、`opt_basic`、`opt_daily`、`rt_hk_k`、`us_basic`、`us_daily`、`us_tradecal`、`wz_index`。

另有独立于上述V2流程的盘中观察循环，消费4个蚂蚁路由，按当前代码每15分钟执行，只覆盖宽基ETF/指数代理、行业与明确开启观察的自选股。最近5个已结束交易日应有80轮，有记录48轮，状态{'success': 39, 'failed': 4, 'attention': 5}，缺少32轮。完整缺轮及问题回执列在JSON的 `intraday_review`；缺轮不能解释为上游没有数据。历史回放不算自动采集覆盖。

自动采集流程的近期产出状态：{'complete': 78, 'unverified': 73, 'gaps': 6, 'sample_manifest_only': 1, 'empty': 2}。

`complete` 只覆盖表内检查范围；`unverified` 表示缺少足够请求/范围证据；`gaps` 表示已定位到缺分区、实体不足或现行规则不通过；`empty` 只表示相应审计结果为空，须结合契约的 verified-empty 证据判断，不推定上游没有数据。检查超时保留为未核实。控制面已通过的某个周期与更宽窗口未通过可以同时成立。历史范围与旧规则问题另见 [历史审计账本汇总](dataset_audit_latest.md)，不能用本次近30日检查替代全历史认证。

## 派生数据完整周期

| 产出 | 契约起点 | 截止 | 应有周期 | 有物理记录 | 当前规则通过 | 缺物理记录 |
|---|---|---|---:|---:|---:|---:|
| fama_french_daily | 2020-01-02 | 2026-11-09 | 1659 | 1659 | 24 | 0 |
| ggt_monthly | 2014-11-01 | 2026-10-31 | 144 | 144 | 1 | 0 |
| local_factor_snapshot | 2016-01-04 | 2026-11-09 | 2634 | 26 | 0 | 2608 |
| technical_factor_snapshot | 2016-01-04 | 2026-11-09 | 2634 | 26 | 26 | 2608 |
| valuation_percentile_snapshot | 2026-10-30 | 2026-11-09 | 7 | 7 | 2 | 0 |

周期统计按当前契约与成熟日历计算；当前规则通过列来自现行版本的分区证书，不代表本次重新计算了每个历史数值。`technical_factor_snapshot` 是同一因子任务的兼容视图。

派生缺口分类：本地272因子与技术视图缺少早期物化周期；财务输入缺失、冲突及公式保护分别记录在 JSON 的 `derived_history.local_factor_input_issues`。Fama-French 和估值分位还存在旧公式历史，须使用当前公式重新计算并独立验收。港股通月汇总有物理行，但多数历史月份仍缺源数据完整证据或聚合值不一致，不能直接认证。

| 产出 | 缺物理周期的最新任务状态 | 有数据但未认证周期的最新任务状态 |
|---|---|---|
| fama_french_daily | {} | {'success': 1635} |
| ggt_monthly | {} | {'not_requested': 143} |
| local_factor_snapshot | {'not_requested': 2608} | {'attention': 26} |
| technical_factor_snapshot | {'not_requested': 2608} | {} |
| valuation_percentile_snapshot | {} | {'not_requested': 5} |

`not_requested` 表示现有执行账本没有该周期的有效请求，不推定供应商没有数据。原始历史导入、旧公式 success、现行规则 attention 分开统计。完整缺期列表在 JSON 中。

尚未实现、没有投产计算入口的派生蓝图：`adjusted_price_return`、`canonical_period_bars`、`etf_flow`、`etf_state_team_signal`、`industry_fundamental_snapshot`、`investment_event_calendar`、`macro_regime`、`market_breadth`、`repurchase_progress_snapshot`、`sector_breadth`、`sector_rotation`。

## 已修复和清理

已修复旧定义被替代后仍占用例行幂等身份的问题；仅为明确的定义替换创建新版本实例，不恢复人工取消或策略停采。蚂蚁股本结构与自由流通股本的2026-W45实例 197405、197407已成功，受控产出范围均为11月2日至8日，且通过当前契约。

研报按自然日覆盖周末，当日请求等待22:30最终发布时点；提前执行则保留检查点等待，不把尚未成熟的周期报成永久失败。已识别的旧提前失败按稳定身份补建最终发布实例。

本次已清理的过期数据库记录：{'expired_query_cache': 9, 'expired_scheduled_checkpoints': 0, 'expired_process_heartbeats': 1851}。旧报告与临时构建文件归档并校验共20项；历史验收参考改名明确标记。每日保留策略见 [数据来源文档](../docs/DATA_SOURCES.md#原始证据与缓存)。

## 每项任务与近期范围

| 任务 | 类型 | 自动入口 | 检查范围 | 产出及状态 | 最近受控产出范围 | 原因 |
|---|---|---|---|---|---|---|
| adj_factor | acquisition | cron | 2026-10-12..2026-11-10 | adj_factor: complete | 2026-11-10..2026-11-10: complete |  |
| adjusted_price_return | transformation | not_published | —..— | adjusted_price_return: draft_not_implemented | 无受控产出 |  |
| ant_actual_controller | acquisition | cron | 2026-10-10..2026-11-08 | ant_actual_controller: unverified | 2026-11-02..2026-11-08: complete | scope_transport_unverified |
| ant_controlling_shareholder | acquisition | cron | 2026-10-10..2026-11-08 | ant_controlling_shareholder: unverified | 2026-11-02..2026-11-08: complete | scope_transport_unverified |
| ant_equity_structure | acquisition | cron | 2026-10-10..2026-11-08 | ant_equity_structure: unverified | 2026-11-02..2026-11-08: complete | scope_transport_unverified |
| ant_free_float | acquisition | cron | 2026-10-10..2026-11-08 | ant_free_float: unverified | 2026-11-02..2026-11-08: complete | scope_transport_unverified |
| ant_hot_plate_rank | acquisition | cron | 2026-10-12..2026-11-10 | ant_hot_plate_rank: unverified | 2026-11-10..2026-11-10: complete | scope_transport_unverified |
| ant_hot_stock_rank | acquisition | cron | 2026-10-12..2026-11-10 | ant_hot_stock_rank: unverified | 2026-11-10..2026-11-10: complete | scope_transport_unverified |
| ant_style_classification | acquisition | cron | 2026-10-10..2026-11-08 | ant_style_classification: unverified | 2026-11-02..2026-11-08: complete | scope_transport_unverified |
| bak_basic | acquisition | cron | 2026-10-12..2026-11-10 | bak_basic: unverified | 2026-11-10..2026-11-10: complete | scope_transport_unverified |
| bak_daily | acquisition | cron | 2026-10-12..2026-11-10 | bak_daily: complete | 2026-11-10..2026-11-10: complete |  |
| balancesheet | acquisition | supplementary | 2026-07-01..2026-09-30 | balancesheet: complete | 2026-07-01..2026-09-30: complete |  |
| bc_bestotcqt | acquisition | paused_policy | 2026-10-12..2026-11-10 | bc_bestotcqt: unverified | 2026-11-09..2026-11-09: complete | scope_transport_unverified |
| bc_otcqt | acquisition | paused_policy | 2026-10-12..2026-11-10 | bc_otcqt: unverified | 无受控产出 | scope_transport_unverified |
| block_trade | acquisition | cron | 2026-10-12..2026-11-10 | block_trade: unverified | 2026-11-10..2026-11-10: complete | scope_transport_unverified |
| bond_blk | acquisition | paused_policy | 2026-10-12..2026-11-10 | bond_blk: unverified | 2026-11-09..2026-11-09: complete | scope_transport_unverified |
| bond_blk_detail | acquisition | paused_policy | 2026-10-12..2026-11-10 | bond_blk_detail: unverified | 2026-11-09..2026-11-09: complete | scope_transport_unverified |
| broker_recommend | acquisition | cron | 2026-10-01..2026-10-31 | broker_recommend: complete | 2026-10-01..2026-10-31: complete |  |
| bse_mapping | acquisition | cron | 2026-11-02..2026-11-08 | bse_mapping: complete | 2026-11-02..2026-11-08: complete |  |
| canonical_period_bars | transformation | not_published | —..— | canonical_period_bars: draft_not_implemented | 无受控产出 |  |
| cashflow | acquisition | supplementary | 2026-07-01..2026-09-30 | cashflow: complete | 2026-07-01..2026-09-30: complete |  |
| cb_basic | acquisition | cron | 2026-11-02..2026-11-08 | cb_basic: complete | 2026-11-02..2026-11-08: complete |  |
| cb_call | acquisition | cron | 2026-10-12..2026-11-10 | cb_call: unverified | 2026-11-10..2026-11-10: empty_verified | scope_transport_unverified |
| cb_daily | acquisition | cron | 2026-10-12..2026-11-10 | cb_daily: complete | 2026-11-10..2026-11-10: complete |  |
| cb_factor_pro | acquisition | cron | 2026-10-12..2026-11-10 | cb_factor_pro: complete | 2026-11-10..2026-11-10: partial |  |
| cb_issue | acquisition | cron | 2026-10-12..2026-11-10 | cb_issue: unverified | 2026-11-10..2026-11-10: empty_verified | scope_transport_unverified |
| cb_rate | acquisition | manual | 2026-11-09..2026-11-09 | cb_rate: unverified | 无受控产出 | scope_transport_unverified |
| cb_rating | acquisition | manual | 2026-10-12..2026-11-10 | cb_rating: unverified | 无受控产出 | scope_transport_unverified |
| cb_share | acquisition | manual | 2026-10-12..2026-11-10 | cb_share: unverified | 无受控产出 | scope_transport_unverified |
| ccass_hold | acquisition | paused_policy | 2026-10-12..2026-11-10 | ccass_hold: unverified | 2026-11-06..2026-11-06: complete | scope_transport_unverified |
| ccass_hold_detail | acquisition | paused_policy | 2026-10-12..2026-11-10 | ccass_hold_detail: unverified | 2026-10-30..2026-10-30: complete | scope_transport_unverified |
| chinabond_yield_curve | acquisition | cron | 2026-10-12..2026-11-10 | chinabond_yield_curve: complete | 2026-11-10..2026-11-10: complete |  |
| ci_daily | acquisition | cron | 2026-10-12..2026-11-10 | ci_daily: complete | 2026-11-10..2026-11-10: complete |  |
| ci_index_member | acquisition | supplementary | 2026-11-10..2026-11-10 | ci_index_member: complete | 2026-11-10..2026-11-10: complete |  |
| cn_cpi | acquisition | cron | 2026-09-01..2026-09-30 | cn_cpi: complete | 2026-10-01..2026-10-31: empty_verified |  |
| cn_gdp | acquisition | cron | 2026-07-01..2026-09-30 | cn_gdp: complete | 2026-07-01..2026-09-30: complete |  |
| cn_lpr | acquisition | cron | 2026-09-01..2026-09-30 | cn_lpr: complete | 2026-11-10..2026-11-10: empty_verified |  |
| cn_m | acquisition | cron | 2026-09-01..2026-09-30 | cn_m: complete | 2026-10-01..2026-10-31: empty_verified |  |
| cn_pmi | acquisition | cron | 2026-10-01..2026-10-31 | cn_pmi: complete | 2026-10-01..2026-10-31: complete |  |
| cn_ppi | acquisition | cron | 2026-09-01..2026-09-30 | cn_ppi: complete | 2026-10-01..2026-10-31: empty_verified |  |
| cn_schedule | acquisition | cron | 2026-10-02..2026-10-31 | cn_schedule: complete | 2026-10-01..2026-10-31: complete |  |
| cninfo_announcements | acquisition | cron | 2026-10-12..2026-11-10 | stock_announcements: gaps | 2026-11-09..2026-11-09: complete | missing_partition |
| cyq_chips | acquisition | cron | 2026-10-10..2026-11-08 | cyq_chips: gaps | 2026-10-26..2026-11-01: complete | transport_or_business_incomplete, entity_coverage_below_threshold |
| cyq_perf | acquisition | cron | 2026-10-10..2026-11-08 | cyq_perf: gaps | 2026-10-26..2026-11-01: complete | transport_or_business_incomplete, entity_coverage_below_threshold |
| daily | acquisition | cron | 2026-10-12..2026-11-10 | stock_daily: complete | 2026-11-10..2026-11-10: complete |  |
| daily_basic | acquisition | cron | 2026-10-12..2026-11-10 | daily_basic: complete | 2026-11-10..2026-11-10: complete |  |
| daily_info | acquisition | cron | 2026-10-12..2026-11-10 | daily_info: complete | 2026-11-10..2026-11-10: complete |  |
| dc_concept | acquisition | cron | 2026-10-12..2026-11-10 | dc_concept: unverified | 2026-11-10..2026-11-10: complete | scope_transport_unverified |
| dc_concept_cons | acquisition | manual | 2026-10-12..2026-11-10 | dc_concept_cons: unverified | 无受控产出 | scope_transport_unverified |
| dc_daily | acquisition | cron | 2026-10-12..2026-11-10 | dc_daily: complete | 2026-11-10..2026-11-10: complete |  |
| dc_hot | acquisition | cron | 2026-10-12..2026-11-10 | dc_hot: unverified | 2026-11-10..2026-11-10: indeterminate | scope_transport_unverified |
| dc_index | acquisition | cron | 2026-10-12..2026-11-10 | dc_index: gaps | 2026-11-10..2026-11-10: complete | transport_or_business_incomplete |
| dc_member | acquisition | cron | 2026-10-12..2026-11-10 | dc_member: unverified | 2026-11-10..2026-11-10: complete | scope_transport_unverified |
| disclosure_date | acquisition | cron | 2026-09-01..2026-09-30 | disclosure_date: complete | 2026-07-01..2026-09-30: complete |  |
| dividend | acquisition | cron | 2026-10-12..2026-11-10 | dividend: unverified | 2026-11-10..2026-11-10: complete | scope_transport_unverified |
| eco_cal | acquisition | cron | 2026-10-12..2026-11-10 | eco_cal: unverified | 2026-11-10..2026-11-10: complete | scope_transport_unverified |
| etf_basic | acquisition | cron | 2026-11-02..2026-11-08 | etf_basic: complete | 2026-11-02..2026-11-08: complete |  |
| etf_flow | transformation | not_published | —..— | etf_flow: draft_not_implemented | 无受控产出 |  |
| etf_index | acquisition | cron | 2026-11-02..2026-11-08 | etf_index: complete | 2026-11-02..2026-11-08: complete |  |
| etf_sh_cons | acquisition | cron | 2026-10-10..2026-11-08 | etf_sh_cons: gaps | 2026-11-02..2026-11-08: complete | transport_or_business_incomplete |
| etf_share_size | acquisition | cron | 2026-10-12..2026-11-10 | etf_share_size: complete | 2026-11-09..2026-11-09: complete |  |
| etf_state_team_signal | transformation | not_published | —..— | etf_state_team_signal: draft_not_implemented | 无受控产出 |  |
| etf_sz_cons | acquisition | cron | 2026-10-10..2026-11-08 | etf_sz_cons: complete | 2026-11-02..2026-11-08: complete |  |
| express | acquisition | supplementary | 2026-10-12..2026-11-10 | express: unverified | 2026-07-01..2026-09-30: complete | scope_transport_unverified |
| factor_reference_sample | acquisition | supplementary | —..— | factor_reference_sample: sample_manifest_only | 2026-10-30..2026-10-30: complete |  |
| factor_value | acquisition | paused_policy | 2026-10-12..2026-11-10 | factor_value: gaps | 2026-10-30..2026-10-30: complete | transport_or_business_incomplete, missing_partition |
| fama_french_daily | transformation | dependency | 2026-10-12..2026-11-10 | fama_french_daily: complete | 2026-11-10..2026-11-10: complete |  |
| fina_audit | acquisition | manual | 2026-10-12..2026-11-10 | fina_audit: unverified | 无受控产出 | scope_transport_unverified |
| fina_mainbz | acquisition | manual | 2026-07-01..2026-09-30 | fina_mainbz: complete | 2026-07-01..2026-09-30: complete |  |
| financial_indicator | acquisition | supplementary | 2026-07-01..2026-09-30 | financial_indicator: complete | 2026-07-01..2026-09-30: complete |  |
| forecast | acquisition | cron | 2026-09-01..2026-09-30 | forecast: complete | 2026-07-01..2026-09-30: complete |  |
| ft_limit | acquisition | paused_policy | 2026-10-12..2026-11-10 | ft_limit: unverified | 2026-11-09..2026-11-09: complete | scope_transport_unverified |
| fund_adj | acquisition | cron | 2026-10-12..2026-11-10 | fund_adj: complete | 2026-11-10..2026-11-10: complete |  |
| fund_basic | acquisition | supplementary | 2026-11-10..2026-11-10 | fund_basic: complete | 2026-11-10..2026-11-10: complete |  |
| fund_company | acquisition | cron | 2026-11-02..2026-11-08 | fund_company: complete | 2026-11-02..2026-11-08: complete |  |
| fund_daily | acquisition | cron | 2026-10-12..2026-11-10 | fund_daily: complete | 2026-11-10..2026-11-10: complete |  |
| fund_div | acquisition | cron | 2026-10-12..2026-11-10 | fund_div: unverified | 2026-11-10..2026-11-10: complete | scope_transport_unverified |
| fund_factor_pro | acquisition | cron | 2026-10-12..2026-11-10 | fund_factor_pro: complete | 2026-11-10..2026-11-10: complete |  |
| fund_manager | acquisition | cron | 2026-10-10..2026-11-08 | fund_manager: complete | 2026-11-02..2026-11-08: complete |  |
| fund_nav | acquisition | cron | 2026-10-12..2026-11-10 | fund_nav: unverified | 2026-11-10..2026-11-10: empty_verified | scope_transport_unverified |
| fund_portfolio | acquisition | cron | 2026-09-01..2026-09-30 | fund_portfolio: empty | 2026-07-01..2026-09-30: empty_verified |  |
| fund_share | acquisition | cron | 2026-10-12..2026-11-10 | fund_share: unverified | 2026-11-10..2026-11-10: empty_verified | scope_transport_unverified |
| fut_basic | acquisition | paused_policy | 2026-11-10..2026-11-10 | fut_basic: complete | 2026-11-10..2026-11-10: complete |  |
| fut_daily | acquisition | paused_policy | 2026-10-12..2026-11-10 | fut_daily: unverified | 2026-11-09..2026-11-09: complete | scope_transport_unverified |
| fut_holding | acquisition | paused_policy | 2026-10-12..2026-11-10 | fut_holding: unverified | 2026-09-23..2026-09-23: complete | scope_transport_unverified |
| fut_index_daily | acquisition | paused_policy | 2026-10-12..2026-11-10 | fut_index_daily: gaps | 2026-11-03..2026-11-03: complete | transport_or_business_incomplete, missing_partition |
| fut_mapping | acquisition | paused_policy | 2026-10-12..2026-11-10 | fut_mapping: unverified | 2026-11-09..2026-11-09: complete | scope_transport_unverified |
| fut_settle | acquisition | paused_policy | 2026-10-12..2026-11-10 | fut_settle: unverified | 2026-11-09..2026-11-09: complete | scope_transport_unverified |
| fut_trade_cal | acquisition | paused_policy | 2026-10-12..2026-11-10 | fut_trade_cal: unverified | 2026-11-09..2026-11-09: complete | scope_transport_unverified |
| fut_weekly_detail | acquisition | paused_policy | 2026-10-10..2026-11-08 | fut_weekly_detail: empty | 2026-11-02..2026-11-08: indeterminate |  |
| fut_weekly_monthly | acquisition | paused_policy | 2026-10-12..2026-11-10 | fut_weekly_monthly: unverified | 无受控产出 | scope_transport_unverified |
| fut_wsr | acquisition | paused_policy | 2026-10-12..2026-11-10 | fut_wsr: unverified | 2026-11-09..2026-11-09: complete | scope_transport_unverified |
| fx_daily | acquisition | cron | 2026-10-12..2026-11-10 | forex_daily: unverified | 2026-11-10..2026-11-10: indeterminate | scope_transport_unverified |
| fx_obasic | acquisition | paused_policy | 2026-11-02..2026-11-08 | fx_obasic: complete | 2026-11-02..2026-11-08: complete |  |
| ggt_daily | acquisition | cron | 2026-10-12..2026-11-10 | ggt_daily: unverified | 2026-11-10..2026-11-10: indeterminate | scope_transport_unverified |
| ggt_monthly | transformation | dependency | 2026-10-01..2026-10-31 | ggt_monthly: complete | 2026-10-01..2026-10-31: complete |  |
| ggt_top10 | acquisition | cron | 2026-10-12..2026-11-10 | ggt_top10: unverified | 2026-11-10..2026-11-10: complete | scope_transport_unverified |
| gz_index | acquisition | paused_policy | 2026-10-12..2026-11-10 | gz_index: unverified | 2026-11-09..2026-11-09: empty_verified | scope_transport_unverified |
| hibor | acquisition | cron | 2026-10-12..2026-11-10 | hibor: unverified | 2026-11-10..2026-11-10: complete | scope_transport_unverified |
| hk_basic | acquisition | paused_policy | 2026-11-02..2026-11-08 | hk_basic: complete | 2026-11-02..2026-11-08: complete |  |
| hk_daily | acquisition | paused_policy | 2026-10-12..2026-11-10 | hk_daily: gaps | 2026-11-06..2026-11-06: complete | missing_partition |
| hk_hold | acquisition | cron | 2026-10-12..2026-11-10 | hk_hold: unverified | 2026-11-10..2026-11-10: indeterminate | scope_transport_unverified |
| hk_tradecal | acquisition | paused_policy | 2026-10-12..2026-11-10 | hk_tradecal: unverified | 2026-11-09..2026-11-09: complete | scope_transport_unverified |
| hm_list | acquisition | cron | 2026-11-02..2026-11-08 | hm_list: complete | 2026-11-02..2026-11-08: complete |  |
| hsgt_top10 | acquisition | cron | 2026-10-12..2026-11-10 | hsgt_top10: unverified | 2026-11-10..2026-11-10: complete | scope_transport_unverified |
| idx_anns | acquisition | cron | 2026-10-12..2026-11-10 | idx_anns: unverified | 2026-11-10..2026-11-10: complete | scope_transport_unverified |
| idx_factor_pro | acquisition | cron | 2026-10-12..2026-11-10 | idx_factor_pro: complete | 2026-11-10..2026-11-10: complete |  |
| income | acquisition | supplementary | 2026-07-01..2026-09-30 | income: complete | 2026-07-01..2026-09-30: complete |  |
| index_basic | acquisition | cron | 2026-11-02..2026-11-08 | index_basic: complete | 2026-11-02..2026-11-08: complete |  |
| index_classify | acquisition | cron | 2026-11-02..2026-11-08 | index_classify: complete | 2026-11-02..2026-11-08: complete |  |
| index_daily | acquisition | cron | 2026-10-12..2026-11-10 | index_daily: complete | 2026-11-10..2026-11-10: partial |  |
| index_dailybasic | acquisition | cron | 2026-10-12..2026-11-10 | index_dailybasic: complete | 2026-11-10..2026-11-10: complete |  |
| index_global | acquisition | cron | 2026-10-12..2026-11-10 | index_global: unverified | 2026-11-10..2026-11-10: complete | scope_transport_unverified |
| index_member_all | acquisition | supplementary | 2026-11-10..2026-11-10 | index_member_all: complete | 2026-11-10..2026-11-10: complete |  |
| index_monthly | acquisition | cron | 2026-10-01..2026-10-31 | index_monthly: complete | 2026-10-01..2026-10-31: complete |  |
| index_weekly | acquisition | cron | 2026-10-10..2026-11-08 | index_weekly: complete | 2026-11-02..2026-11-08: complete |  |
| index_weight | acquisition | supplementary | 2026-10-12..2026-11-10 | index_weight: unverified | 2026-09-01..2026-10-30: complete | scope_transport_unverified |
| industry_fundamental_snapshot | transformation | not_published | —..— | industry_fundamental_snapshot: draft_not_implemented | 无受控产出 |  |
| investment_event_calendar | transformation | not_published | —..— | investment_event_calendar: draft_not_implemented | 无受控产出 |  |
| kpl_concept_cons | acquisition | cron | 2026-10-12..2026-11-10 | kpl_concept_cons: complete | 2026-11-10..2026-11-10: complete |  |
| kpl_list | acquisition | cron | 2026-10-12..2026-11-10 | kpl_list: unverified | 2026-11-10..2026-11-10: indeterminate | scope_transport_unverified |
| libor | acquisition | paused_policy | 2026-10-12..2026-11-10 | libor: unverified | 2026-11-09..2026-11-09: empty_verified | scope_transport_unverified |
| limit_cpt_list | acquisition | cron | 2026-10-12..2026-11-10 | limit_cpt_list: unverified | 2026-11-10..2026-11-10: complete | scope_transport_unverified |
| limit_list_d | acquisition | cron | 2026-10-12..2026-11-10 | limit_list_d: unverified | 2026-11-10..2026-11-10: complete | scope_transport_unverified |
| limit_list_ths | acquisition | cron | 2026-10-12..2026-11-10 | limit_list_ths: unverified | 2026-11-10..2026-11-10: complete | scope_transport_unverified |
| limit_step | acquisition | cron | 2026-10-12..2026-11-10 | limit_step: unverified | 2026-11-10..2026-11-10: complete | scope_transport_unverified |
| local_factor_snapshot | transformation | dependency | 2026-10-12..2026-11-10 | local_factor_snapshot: gaps | 2026-11-09..2026-11-09: partial | derived_payload_invalid, local_factor_issues_recorded, ready_entity_coverage_below_threshold, missing_partition |
| local_factor_snapshot | transformation | dependency | 2026-10-12..2026-11-10 | technical_factor_snapshot: gaps | 2026-11-09..2026-11-09: complete | missing_partition |
| macro_regime | transformation | not_published | —..— | macro_regime: draft_not_implemented | 无受控产出 |  |
| major_news | acquisition | cron | 2026-11-10..2026-11-10 | major_news: unverified | 2026-11-06..2026-11-06: complete | scope_transport_unverified |
| margin | acquisition | cron | 2026-10-12..2026-11-10 | margin: complete | 2026-11-09..2026-11-09: complete |  |
| margin_detail | acquisition | cron | 2026-10-12..2026-11-10 | margin_detail: complete | 2026-11-09..2026-11-09: complete |  |
| margin_secs | acquisition | cron | 2026-10-12..2026-11-10 | margin_secs: unverified | 2026-11-10..2026-11-10: complete | scope_transport_unverified |
| market_breadth | transformation | not_published | —..— | market_breadth: draft_not_implemented | 无受控产出 |  |
| mkt_idx_bmk | acquisition | cron | 2026-11-02..2026-11-08 | mkt_idx_bmk: complete | 2026-11-02..2026-11-08: complete |  |
| moneyflow | acquisition | cron | 2026-10-12..2026-11-10 | moneyflow: complete | 2026-11-10..2026-11-10: complete |  |
| moneyflow_cnt_ths | acquisition | cron | 2026-10-12..2026-11-10 | moneyflow_cnt_ths: complete | 2026-11-10..2026-11-10: complete |  |
| moneyflow_dc | acquisition | cron | 2026-10-10..2026-11-08 | moneyflow_dc: complete | 2026-11-02..2026-11-08: complete |  |
| moneyflow_hsgt | acquisition | cron | 2026-10-12..2026-11-10 | moneyflow_hsgt: unverified | 2026-11-10..2026-11-10: complete | scope_transport_unverified |
| moneyflow_ind_dc | acquisition | cron | 2026-10-12..2026-11-10 | moneyflow_ind_dc: complete | 2026-11-10..2026-11-10: complete |  |
| moneyflow_ind_ths | acquisition | cron | 2026-10-12..2026-11-10 | moneyflow_ind_ths: complete | 2026-11-10..2026-11-10: complete |  |
| moneyflow_mkt_dc | acquisition | cron | 2026-10-12..2026-11-10 | moneyflow_mkt_dc: complete | 2026-11-10..2026-11-10: complete |  |
| moneyflow_ths | acquisition | cron | 2026-10-12..2026-11-10 | moneyflow_ths: complete | 2026-11-10..2026-11-10: complete |  |
| namechange | acquisition | cron | 2026-10-12..2026-11-10 | namechange: unverified | 2026-11-10..2026-11-10: complete | scope_transport_unverified |
| new_share | acquisition | cron | 2026-10-12..2026-11-10 | new_share: unverified | 2026-11-10..2026-11-10: empty_verified | scope_transport_unverified |
| opt_basic | acquisition | paused_policy | 2026-11-02..2026-11-08 | opt_basic: complete | 2026-11-02..2026-11-08: complete |  |
| opt_daily | acquisition | paused_policy | 2026-10-12..2026-11-10 | opt_daily: gaps | 2026-11-09..2026-11-09: complete | transport_or_business_incomplete |
| p_get | acquisition | manual | 2026-11-09..2026-11-09 | p_get: unverified | 无受控产出 | scope_transport_unverified |
| p_list | acquisition | cron | 2026-11-02..2026-11-08 | p_list: empty | 2026-11-02..2026-11-08: empty_verified |  |
| pledge_detail | acquisition | cron | 2026-10-12..2026-11-10 | pledge_detail: unverified | 2026-11-10..2026-11-10: complete | scope_transport_unverified |
| pledge_stat | acquisition | supplementary | 2026-10-12..2026-11-10 | pledge_stat: unverified | 2026-11-06..2026-11-06: complete | scope_transport_unverified |
| repo_daily | acquisition | cron | 2026-10-12..2026-11-10 | repo_daily: unverified | 2026-11-10..2026-11-10: complete | scope_transport_unverified |
| report_rc | acquisition | cron | 2026-10-12..2026-11-10 | report_rc: gaps | 2026-11-09..2026-11-09: complete | missing_partition |
| repurchase | acquisition | cron | 2026-10-01..2026-10-31 | repurchase: complete | 2026-11-10..2026-11-10: complete |  |
| repurchase_progress_snapshot | transformation | not_published | —..— | repurchase_progress_snapshot: draft_not_implemented | 无受控产出 |  |
| rt_hk_k | acquisition | paused_policy | 2026-11-09..2026-11-09 | rt_hk_k: unverified | 无受控产出 | scope_transport_unverified |
| sector_breadth | transformation | not_published | —..— | sector_breadth: draft_not_implemented | 无受控产出 |  |
| sector_rotation | transformation | not_published | —..— | sector_rotation: draft_not_implemented | 无受控产出 |  |
| sf_month | acquisition | cron | 2026-09-01..2026-09-30 | sf_month: complete | 2026-10-01..2026-10-31: empty_verified |  |
| sge_basic | acquisition | cron | 2026-11-02..2026-11-08 | sge_basic: complete | 2026-11-02..2026-11-08: complete |  |
| sge_daily | acquisition | cron | 2026-10-12..2026-11-10 | sge_daily: complete | 2026-11-10..2026-11-10: complete |  |
| share_float | acquisition | cron | 2026-10-12..2026-11-10 | share_float: unverified | 2026-11-04..2026-11-04: complete | scope_transport_unverified |
| shibor | acquisition | cron | 2026-10-12..2026-11-10 | shibor: complete | 2026-11-10..2026-11-10: complete |  |
| shibor_quote | acquisition | cron | 2026-10-12..2026-11-10 | shibor_quote: unverified | 2026-11-10..2026-11-10: complete | scope_transport_unverified |
| slb_len | acquisition | cron | 2026-10-12..2026-11-10 | slb_len: unverified | 2026-11-10..2026-11-10: empty_verified | scope_transport_unverified |
| slb_len_mm | acquisition | cron | 2026-10-12..2026-11-10 | slb_len_mm: unverified | 2026-11-10..2026-11-10: empty_verified | scope_transport_unverified |
| slb_sec | acquisition | cron | 2026-10-12..2026-11-10 | slb_sec: unverified | 2026-11-10..2026-11-10: empty_verified | scope_transport_unverified |
| slb_sec_detail | acquisition | cron | 2026-10-12..2026-11-10 | slb_sec_detail: unverified | 2026-11-10..2026-11-10: empty_verified | scope_transport_unverified |
| stk_account | acquisition | cron | 2026-10-12..2026-11-10 | stk_account: unverified | 2026-11-10..2026-11-10: empty_verified | scope_transport_unverified |
| stk_ah_comparison | acquisition | cron | 2026-10-12..2026-11-10 | stk_ah_comparison: unverified | 2026-11-10..2026-11-10: complete | scope_transport_unverified |
| stk_alert | acquisition | cron | 2026-10-12..2026-11-10 | stk_alert: unverified | 2026-11-10..2026-11-10: complete | scope_transport_unverified |
| stk_auction | acquisition | cron | 2026-10-12..2026-11-10 | stk_auction: complete | 2026-11-10..2026-11-10: complete |  |
| stk_auction_c | acquisition | cron | 2026-10-12..2026-11-10 | stk_auction_c: unverified | 2026-11-10..2026-11-10: indeterminate | scope_transport_unverified |
| stk_auction_o | acquisition | cron | 2026-10-12..2026-11-10 | stk_auction_o: unverified | 2026-11-10..2026-11-10: indeterminate | scope_transport_unverified |
| stk_factor | acquisition | cron | 2026-10-12..2026-11-10 | stk_factor: complete | 2026-11-10..2026-11-10: partial |  |
| stk_factor_pro | acquisition | cron | 2026-10-12..2026-11-10 | stk_factor_pro: complete | 2026-11-10..2026-11-10: partial |  |
| stk_high_shock | acquisition | cron | 2026-10-12..2026-11-10 | stk_high_shock: unverified | 2026-11-10..2026-11-10: empty_verified | scope_transport_unverified |
| stk_holdernumber | acquisition | cron | 2026-10-12..2026-11-10 | stk_holdernumber: unverified | 2026-11-10..2026-11-10: complete | scope_transport_unverified |
| stk_holdertrade | acquisition | cron | 2026-10-12..2026-11-10 | stk_holdertrade: unverified | 2026-11-10..2026-11-10: complete | scope_transport_unverified |
| stk_limit | acquisition | cron | 2026-10-12..2026-11-10 | stock_limit: complete | 2026-11-10..2026-11-10: complete |  |
| stk_managers | acquisition | cron | 2026-10-12..2026-11-10 | stk_managers: unverified | 2026-11-10..2026-11-10: empty_verified | scope_transport_unverified |
| stk_mins | acquisition | manual | 2026-11-09..2026-11-09 | stk_mins: unverified | 无受控产出 | scope_transport_unverified |
| stk_nineturn | acquisition | cron | 2026-10-12..2026-11-10 | stk_nineturn: unverified | 2026-11-10..2026-11-10: complete | scope_transport_unverified |
| stk_rewards | acquisition | supplementary | 2026-10-12..2026-11-10 | stk_rewards: unverified | 2025-12-31..2025-12-31: complete | scope_transport_unverified |
| stk_seasoned | acquisition | cron | 2026-10-12..2026-11-10 | stk_seasoned: unverified | 2026-11-09..2026-11-09: complete | scope_transport_unverified |
| stk_shock | acquisition | cron | 2026-10-12..2026-11-10 | stk_shock: unverified | 2026-11-10..2026-11-10: complete | scope_transport_unverified |
| stk_surv | acquisition | cron | 2026-10-12..2026-11-10 | stk_surv: unverified | 2026-11-10..2026-11-10: empty_verified | scope_transport_unverified |
| stk_week_month_adj | acquisition | manual | 2026-10-12..2026-11-10 | stk_week_month_adj: unverified | 无受控产出 | scope_transport_unverified |
| stk_weekly_monthly | acquisition | manual | 2026-10-12..2026-11-10 | stk_weekly_monthly: unverified | 无受控产出 | scope_transport_unverified |
| stock_basic | acquisition | cron | 2026-11-10..2026-11-10 | stock_basic: complete | 2026-11-10..2026-11-10: complete |  |
| stock_company | acquisition | cron | 2026-11-02..2026-11-08 | stock_company: complete | 2026-11-02..2026-11-08: complete |  |
| stock_hsgt | acquisition | supplementary | 2026-10-12..2026-11-10 | stock_hsgt: unverified | 2026-11-10..2026-11-10: complete | scope_transport_unverified |
| stock_st | acquisition | cron | 2026-10-12..2026-11-10 | stock_st: complete | 2026-11-10..2026-11-10: complete |  |
| suspend_d | acquisition | cron | 2026-10-12..2026-11-10 | stock_suspend: unverified | 2026-11-10..2026-11-10: complete | scope_transport_unverified |
| sw_daily | acquisition | cron | 2026-10-12..2026-11-10 | sw_daily: complete | 2026-11-10..2026-11-10: complete |  |
| sz_daily_info | acquisition | cron | 2026-10-12..2026-11-10 | sz_daily_info: complete | 2026-11-10..2026-11-10: complete |  |
| tdx_daily | acquisition | cron | 2026-10-12..2026-11-10 | tdx_daily: complete | 2026-11-10..2026-11-10: complete |  |
| tdx_index | acquisition | cron | 2026-10-12..2026-11-10 | tdx_index: complete | 2026-11-10..2026-11-10: complete |  |
| tdx_member | acquisition | manual | 2026-10-12..2026-11-10 | tdx_member: unverified | 无受控产出 | scope_transport_unverified |
| ths_daily | acquisition | cron | 2026-10-12..2026-11-10 | industry_daily: complete | 2026-11-10..2026-11-10: complete |  |
| ths_hot | acquisition | cron | 2026-10-12..2026-11-10 | ths_hot: complete | 2026-11-09..2026-11-09: complete |  |
| ths_index | acquisition | cron | 2026-11-02..2026-11-08 | ths_index: complete | 2026-11-02..2026-11-08: complete |  |
| ths_member | acquisition | cron | 2026-11-02..2026-11-08 | ths_member: unverified | 2026-10-26..2026-11-01: complete | scope_transport_unverified |
| top10_cb_holders | acquisition | manual | 2026-10-12..2026-11-10 | top10_cb_holders: unverified | 无受控产出 | scope_transport_unverified |
| top10_floatholders | acquisition | cron | 2026-07-01..2026-09-30 | top10_floatholders: complete | 2026-07-01..2026-09-30: complete |  |
| top10_holders | acquisition | cron | 2026-07-01..2026-09-30 | top10_holders: complete | 2026-07-01..2026-09-30: complete |  |
| top_inst | acquisition | cron | 2026-10-12..2026-11-10 | top_inst: unverified | 2026-11-10..2026-11-10: complete | scope_transport_unverified |
| top_list | acquisition | cron | 2026-10-12..2026-11-10 | top_list: unverified | 2026-11-10..2026-11-10: complete | scope_transport_unverified |
| trade_cal | acquisition | cron | 2026-10-12..2026-11-10 | trade_calendar: unverified | 2026-11-10..2026-11-10: complete | scope_transport_unverified |
| us_basic | acquisition | paused_policy | 2026-11-02..2026-11-08 | us_basic: complete | 2026-11-02..2026-11-08: complete |  |
| us_daily | acquisition | paused_policy | 2026-10-12..2026-11-10 | us_daily: gaps | 无受控产出 | transport_or_business_incomplete, missing_partition |
| us_tbr | acquisition | cron | 2026-10-12..2026-11-10 | us_tbr: unverified | 2026-11-09..2026-11-09: indeterminate | scope_transport_unverified |
| us_tltr | acquisition | cron | 2026-10-12..2026-11-10 | us_tltr: unverified | 2026-11-09..2026-11-09: indeterminate | scope_transport_unverified |
| us_tradecal | acquisition | paused_policy | 2026-10-12..2026-11-10 | us_tradecal: unverified | 2026-11-09..2026-11-09: complete | scope_transport_unverified |
| us_trltr | acquisition | cron | 2026-10-12..2026-11-10 | us_trltr: unverified | 2026-11-09..2026-11-09: indeterminate | scope_transport_unverified |
| us_trycr | acquisition | cron | 2026-10-12..2026-11-10 | us_trycr: unverified | 2026-11-09..2026-11-09: indeterminate | scope_transport_unverified |
| us_tycr | acquisition | cron | 2026-10-12..2026-11-10 | us_tycr: unverified | 2026-11-09..2026-11-09: indeterminate | scope_transport_unverified |
| valuation_percentile_snapshot | transformation | dependency | 2026-10-30..2026-11-10 | valuation_percentile_snapshot: gaps | 2026-11-10..2026-11-10: complete | required_value_mismatch:audit_status, required_value_mismatch:formula_version, valuation_constituent_inputs_incomplete |
| wz_index | acquisition | paused_policy | 2026-10-12..2026-11-10 | wz_index: unverified | 2026-11-09..2026-11-09: empty_verified | scope_transport_unverified |

## 接口到任务的完整映射

| 来源 | 接口 | 任务 | 有自动入口的任务 | 模式 |
|---|---|---|---|---|
| tushare | adj_factor | adj_factor | adj_factor | scheduled_pull |
| tushare | anns_d | 无定时任务 | — | catalogued_unavailable |
| tushare | bak_basic | bak_basic | bak_basic | scheduled_pull |
| tushare | bak_daily | bak_daily | bak_daily | scheduled_pull |
| tushare | balancesheet | balancesheet | balancesheet | scheduled_pull |
| tushare | balancesheet_vip | balancesheet | balancesheet | scheduled_pull |
| tushare | bc_bestotcqt | bc_bestotcqt | — | scheduled_pull |
| tushare | bc_otcqt | bc_otcqt | — | scheduled_pull |
| tushare | block_trade | block_trade | block_trade | scheduled_pull |
| tushare | bond_blk | bond_blk | — | scheduled_pull |
| tushare | bond_blk_detail | bond_blk_detail | — | scheduled_pull |
| tushare | broker_recommend | broker_recommend | broker_recommend | scheduled_pull |
| tushare | bse_mapping | bse_mapping | bse_mapping | scheduled_pull |
| tushare | cashflow | cashflow | cashflow | scheduled_pull |
| tushare | cashflow_vip | cashflow | cashflow | scheduled_pull |
| tushare | cb_basic | cb_basic | cb_basic | scheduled_pull |
| tushare | cb_call | cb_call | cb_call | scheduled_pull |
| tushare | cb_daily | cb_daily | cb_daily | scheduled_pull |
| tushare | cb_factor_pro | cb_factor_pro | cb_factor_pro | scheduled_pull |
| tushare | cb_issue | cb_issue | cb_issue | scheduled_pull |
| tushare | cb_price_chg | 无定时任务 | — | catalogued_unavailable |
| tushare | cb_rate | cb_rate | — | scheduled_pull |
| tushare | cb_rating | cb_rating | — | scheduled_pull |
| tushare | cb_share | cb_share | — | scheduled_pull |
| tushare | ccass_hold | ccass_hold | — | scheduled_pull |
| tushare | ccass_hold_detail | ccass_hold_detail | — | scheduled_pull |
| tushare | cctv_news | 无定时任务 | — | catalogued_unavailable |
| tushare | ci_daily | ci_daily | ci_daily | scheduled_pull |
| tushare | ci_index_member | ci_index_member | ci_index_member | scheduled_pull |
| tushare | cn_cpi | cn_cpi | cn_cpi | scheduled_pull |
| tushare | cn_gdp | cn_gdp | cn_gdp | scheduled_pull |
| tushare | cn_m | cn_m | cn_m | scheduled_pull |
| tushare | cn_pmi | cn_pmi | cn_pmi | scheduled_pull |
| tushare | cn_ppi | cn_ppi | cn_ppi | scheduled_pull |
| tushare | cn_schedule | cn_schedule | cn_schedule | scheduled_pull |
| tushare | cyq_chips | cyq_chips | cyq_chips | scheduled_pull |
| tushare | cyq_perf | cyq_perf | cyq_perf | scheduled_pull |
| tushare | daily | daily | daily | scheduled_pull |
| tushare | daily_basic | daily_basic | daily_basic | scheduled_pull |
| tushare | daily_info | daily_info | daily_info | scheduled_pull |
| tushare | dc_concept | dc_concept | dc_concept | scheduled_pull |
| tushare | dc_concept_cons | dc_concept_cons | — | scheduled_pull |
| tushare | dc_daily | dc_daily | dc_daily | scheduled_pull |
| tushare | dc_hot | dc_hot | dc_hot | scheduled_pull |
| tushare | dc_index | dc_index | dc_index | scheduled_pull |
| tushare | dc_member | dc_member | dc_member | scheduled_pull |
| tushare | disclosure_date | disclosure_date | disclosure_date | scheduled_pull |
| tushare | dividend | dividend | dividend | scheduled_pull |
| tushare | eco_cal | eco_cal | eco_cal | scheduled_pull |
| tushare | etf_basic | etf_basic | etf_basic | scheduled_pull |
| tushare | etf_index | etf_index | etf_index | scheduled_pull |
| tushare | etf_mins | 无定时任务 | — | catalogued_unavailable |
| tushare | etf_sh_cons | etf_sh_cons | etf_sh_cons | scheduled_pull |
| tushare | etf_share_size | etf_share_size | etf_share_size | scheduled_pull |
| tushare | etf_sz_cons | etf_sz_cons | etf_sz_cons | scheduled_pull |
| tushare | express | express | express | scheduled_pull |
| tushare | express_vip | express | express | scheduled_pull |
| tushare | factor_list | 无定时任务 | — | catalogued_unavailable |
| tushare | factor_value | factor_value | — | scheduled_pull |
| tushare | fina_audit | fina_audit | — | scheduled_pull |
| tushare | fina_indicator | financial_indicator | financial_indicator | scheduled_pull |
| tushare | fina_indicator_vip | financial_indicator | financial_indicator | scheduled_pull |
| tushare | fina_mainbz | fina_mainbz | — | scheduled_pull |
| tushare | fina_mainbz_vip | fina_mainbz | — | scheduled_pull |
| tushare | forecast | forecast | forecast | scheduled_pull |
| tushare | forecast_vip | forecast | forecast | scheduled_pull |
| tushare | ft_limit | ft_limit | — | scheduled_pull |
| tushare | ft_mins | 无定时任务 | — | catalogued_unavailable |
| tushare | fund_adj | fund_adj | fund_adj | scheduled_pull |
| tushare | fund_basic | fund_basic | fund_basic | scheduled_pull |
| tushare | fund_company | fund_company | fund_company | scheduled_pull |
| tushare | fund_daily | fund_daily | fund_daily | scheduled_pull |
| tushare | fund_div | fund_div | fund_div | scheduled_pull |
| tushare | fund_factor_pro | fund_factor_pro | fund_factor_pro | scheduled_pull |
| tushare | fund_manager | fund_manager | fund_manager | scheduled_pull |
| tushare | fund_nav | fund_nav | fund_nav | scheduled_pull |
| tushare | fund_portfolio | fund_portfolio | fund_portfolio | scheduled_pull |
| tushare | fund_share | fund_share | fund_share | scheduled_pull |
| tushare | fut_basic | fut_basic | — | scheduled_pull |
| tushare | fut_daily | fut_daily | — | scheduled_pull |
| tushare | fut_holding | fut_holding | — | scheduled_pull |
| tushare | fut_index_daily | fut_index_daily | — | scheduled_pull |
| tushare | fut_mapping | fut_mapping | — | scheduled_pull |
| tushare | fut_settle | fut_settle | — | scheduled_pull |
| tushare | fut_trade_cal | fut_trade_cal | — | scheduled_pull |
| tushare | fut_weekly_detail | fut_weekly_detail | — | scheduled_pull |
| tushare | fut_weekly_monthly | fut_weekly_monthly | — | scheduled_pull |
| tushare | fut_wsr | fut_wsr | — | scheduled_pull |
| tushare | fx_daily | fx_daily | fx_daily | scheduled_pull |
| tushare | fx_obasic | fx_obasic | — | scheduled_pull |
| tushare | ggt_daily | ggt_daily | ggt_daily | scheduled_pull |
| tushare | ggt_top10 | ggt_top10 | ggt_top10 | scheduled_pull |
| tushare | gz_index | gz_index | — | scheduled_pull |
| tushare | hibor | hibor | hibor | scheduled_pull |
| tushare | hk_adjfactor | 无定时任务 | — | catalogued_unavailable |
| tushare | hk_balancesheet | 无定时任务 | — | catalogued_unavailable |
| tushare | hk_basic | hk_basic | — | scheduled_pull |
| tushare | hk_cashflow | 无定时任务 | — | catalogued_unavailable |
| tushare | hk_daily | hk_daily | — | scheduled_pull |
| tushare | hk_daily_adj | 无定时任务 | — | catalogued_unavailable |
| tushare | hk_fina_indicator | 无定时任务 | — | catalogued_unavailable |
| tushare | hk_hold | hk_hold | hk_hold | scheduled_pull |
| tushare | hk_income | 无定时任务 | — | catalogued_unavailable |
| tushare | hk_mins | 无定时任务 | — | catalogued_unavailable |
| tushare | hk_tradecal | hk_tradecal | — | scheduled_pull |
| tushare | hm_detail | 无定时任务 | — | catalogued_unavailable |
| tushare | hm_list | hm_list | hm_list | scheduled_pull |
| tushare | hsgt_top10 | hsgt_top10 | hsgt_top10 | scheduled_pull |
| tushare | idx_anns | idx_anns | idx_anns | scheduled_pull |
| tushare | idx_factor_pro | idx_factor_pro | idx_factor_pro | scheduled_pull |
| tushare | idx_mins | 无定时任务 | — | catalogued_unavailable |
| tushare | income | income | income | scheduled_pull |
| tushare | income_vip | income | income | scheduled_pull |
| tushare | index_basic | index_basic | index_basic | scheduled_pull |
| tushare | index_classify | index_classify | index_classify | scheduled_pull |
| tushare | index_daily | index_daily | index_daily | scheduled_pull |
| tushare | index_dailybasic | index_dailybasic | index_dailybasic | scheduled_pull |
| tushare | index_global | index_global | index_global | scheduled_pull |
| tushare | index_member_all | index_member_all | index_member_all | scheduled_pull |
| tushare | index_monthly | index_monthly | index_monthly | scheduled_pull |
| tushare | index_weekly | index_weekly | index_weekly | scheduled_pull |
| tushare | index_weight | index_weight | index_weight | scheduled_pull |
| tushare | irm_qa_sh | 无定时任务 | — | catalogued_unavailable |
| tushare | irm_qa_sz | 无定时任务 | — | catalogued_unavailable |
| tushare | kpl_concept_cons | kpl_concept_cons | kpl_concept_cons | scheduled_pull |
| tushare | kpl_list | kpl_list | kpl_list | scheduled_pull |
| tushare | libor | libor | — | scheduled_pull |
| tushare | limit_cpt_list | limit_cpt_list | limit_cpt_list | scheduled_pull |
| tushare | limit_list_d | limit_list_d | limit_list_d | scheduled_pull |
| tushare | limit_list_ths | limit_list_ths | limit_list_ths | scheduled_pull |
| tushare | limit_step | limit_step | limit_step | scheduled_pull |
| tushare | major_news | major_news | major_news | scheduled_pull |
| tushare | margin | margin | margin | scheduled_pull |
| tushare | margin_detail | margin_detail | margin_detail | scheduled_pull |
| tushare | margin_secs | margin_secs | margin_secs | scheduled_pull |
| tushare | mkt_idx_bmk | mkt_idx_bmk | mkt_idx_bmk | scheduled_pull |
| tushare | monetary_policy | 无定时任务 | — | catalogued_unavailable |
| tushare | moneyflow | moneyflow | moneyflow | scheduled_pull |
| tushare | moneyflow_cnt_ths | moneyflow_cnt_ths | moneyflow_cnt_ths | scheduled_pull |
| tushare | moneyflow_dc | moneyflow_dc | moneyflow_dc | scheduled_pull |
| tushare | moneyflow_hsgt | moneyflow_hsgt | moneyflow_hsgt | scheduled_pull |
| tushare | moneyflow_ind_dc | moneyflow_ind_dc | moneyflow_ind_dc | scheduled_pull |
| tushare | moneyflow_ind_ths | moneyflow_ind_ths | moneyflow_ind_ths | scheduled_pull |
| tushare | moneyflow_mkt_dc | moneyflow_mkt_dc | moneyflow_mkt_dc | scheduled_pull |
| tushare | moneyflow_ths | moneyflow_ths | moneyflow_ths | scheduled_pull |
| tushare | monthly | stk_weekly_monthly | — | scheduled_pull |
| tushare | namechange | namechange | namechange | scheduled_pull |
| tushare | new_share | new_share | new_share | scheduled_pull |
| tushare | news | 无定时任务 | — | catalogued_unavailable |
| tushare | npr | 无定时任务 | — | catalogued_unavailable |
| tushare | opt_basic | opt_basic | — | scheduled_pull |
| tushare | opt_daily | opt_daily | — | scheduled_pull |
| tushare | opt_mins | 无定时任务 | — | catalogued_unavailable |
| tushare | p_delete | 无定时任务 | — | catalogued_unavailable |
| tushare | p_get | p_get | — | scheduled_pull |
| tushare | p_list | p_list | p_list | scheduled_pull |
| tushare | p_save | 无定时任务 | — | catalogued_unavailable |
| tushare | pledge_detail | pledge_detail | pledge_detail | scheduled_pull |
| tushare | pledge_stat | pledge_stat | pledge_stat | scheduled_pull |
| tushare | pro_bar | 无定时任务 | — | catalogued_unavailable |
| tushare | repo_daily | repo_daily | repo_daily | scheduled_pull |
| tushare | report_rc | report_rc | report_rc | scheduled_pull |
| tushare | repurchase | repurchase | repurchase | scheduled_pull |
| tushare | research_report | 无定时任务 | — | catalogued_unavailable |
| tushare | rt_etf_sz_iopv | 无定时任务 | — | catalogued_unavailable |
| tushare | rt_fut_min | 无定时任务 | — | catalogued_unavailable |
| tushare | rt_fut_min_daily | 无定时任务 | — | catalogued_unavailable |
| tushare | rt_hk_k | rt_hk_k | — | scheduled_pull |
| tushare | rt_idx_k | 无定时任务 | — | catalogued_unavailable |
| tushare | rt_idx_min | 无定时任务 | — | catalogued_unavailable |
| tushare | rt_idx_min_daily | 无定时任务 | — | catalogued_unavailable |
| tushare | rt_sw_k | 无定时任务 | — | catalogued_unavailable |
| tushare | sf_month | sf_month | sf_month | scheduled_pull |
| tushare | sge_basic | sge_basic | sge_basic | scheduled_pull |
| tushare | sge_daily | sge_daily | sge_daily | scheduled_pull |
| tushare | share_float | share_float | share_float | scheduled_pull |
| tushare | shibor | shibor | shibor | scheduled_pull |
| tushare | shibor_lpr | cn_lpr | cn_lpr | scheduled_pull |
| tushare | shibor_quote | shibor_quote | shibor_quote | scheduled_pull |
| tushare | slb_len | slb_len | slb_len | scheduled_pull |
| tushare | slb_len_mm | slb_len_mm | slb_len_mm | scheduled_pull |
| tushare | slb_sec | slb_sec | slb_sec | scheduled_pull |
| tushare | slb_sec_detail | slb_sec_detail | slb_sec_detail | scheduled_pull |
| tushare | st | stock_st | stock_st | scheduled_pull |
| tushare | stk_account | stk_account | stk_account | scheduled_pull |
| tushare | stk_account_old | 无定时任务 | — | catalogued_unavailable |
| tushare | stk_ah_comparison | stk_ah_comparison | stk_ah_comparison | scheduled_pull |
| tushare | stk_alert | stk_alert | stk_alert | scheduled_pull |
| tushare | stk_auction | stk_auction | stk_auction | scheduled_pull |
| tushare | stk_auction_c | stk_auction_c | stk_auction_c | scheduled_pull |
| tushare | stk_auction_o | stk_auction_o | stk_auction_o | scheduled_pull |
| tushare | stk_factor | stk_factor | stk_factor | scheduled_pull |
| tushare | stk_factor_pro | stk_factor_pro | stk_factor_pro | scheduled_pull |
| tushare | stk_high_shock | stk_high_shock | stk_high_shock | scheduled_pull |
| tushare | stk_holdernumber | stk_holdernumber | stk_holdernumber | scheduled_pull |
| tushare | stk_holdertrade | stk_holdertrade | stk_holdertrade | scheduled_pull |
| tushare | stk_limit | stk_limit | stk_limit | scheduled_pull |
| tushare | stk_managers | stk_managers | stk_managers | scheduled_pull |
| tushare | stk_mins | stk_mins | — | scheduled_pull |
| tushare | stk_nineturn | stk_nineturn | stk_nineturn | scheduled_pull |
| tushare | stk_premarket | 无定时任务 | — | catalogued_unavailable |
| tushare | stk_rewards | stk_rewards | stk_rewards | scheduled_pull |
| tushare | stk_seasoned | stk_seasoned | stk_seasoned | scheduled_pull |
| tushare | stk_shock | stk_shock | stk_shock | scheduled_pull |
| tushare | stk_surv | stk_surv | stk_surv | scheduled_pull |
| tushare | stk_week_month_adj | stk_week_month_adj | — | scheduled_pull |
| tushare | stk_weekly_monthly | stk_weekly_monthly | — | scheduled_pull |
| tushare | stock_basic | stock_basic | stock_basic | scheduled_pull |
| tushare | stock_company | stock_company | stock_company | scheduled_pull |
| tushare | stock_hsgt | stock_hsgt | stock_hsgt | scheduled_pull |
| tushare | stock_st | stock_st | stock_st | scheduled_pull |
| tushare | suspend_d | suspend_d | suspend_d | scheduled_pull |
| tushare | sw_daily | sw_daily | sw_daily | scheduled_pull |
| tushare | sw_mins | 无定时任务 | — | catalogued_unavailable |
| tushare | sz_daily_info | sz_daily_info | sz_daily_info | scheduled_pull |
| tushare | tdx_daily | tdx_daily | tdx_daily | scheduled_pull |
| tushare | tdx_index | tdx_index | tdx_index | scheduled_pull |
| tushare | tdx_member | tdx_member | — | scheduled_pull |
| tushare | ths_daily | ths_daily | ths_daily | scheduled_pull |
| tushare | ths_hot | ths_hot | ths_hot | scheduled_pull |
| tushare | ths_index | ths_index | ths_index | scheduled_pull |
| tushare | ths_member | ths_member | ths_member | scheduled_pull |
| tushare | top10_cb_holders | top10_cb_holders | — | scheduled_pull |
| tushare | top10_floatholders | top10_floatholders | top10_floatholders | scheduled_pull |
| tushare | top10_holders | top10_holders | top10_holders | scheduled_pull |
| tushare | top_inst | top_inst | top_inst | scheduled_pull |
| tushare | top_list | top_list | top_list | scheduled_pull |
| tushare | trade_cal | trade_cal | trade_cal | scheduled_pull |
| tushare | us_adjfactor | 无定时任务 | — | catalogued_unavailable |
| tushare | us_balancesheet | 无定时任务 | — | catalogued_unavailable |
| tushare | us_basic | us_basic | — | scheduled_pull |
| tushare | us_cashflow | 无定时任务 | — | catalogued_unavailable |
| tushare | us_daily | us_daily | — | scheduled_pull |
| tushare | us_daily_adj | 无定时任务 | — | catalogued_unavailable |
| tushare | us_fina_indicator | 无定时任务 | — | catalogued_unavailable |
| tushare | us_income | 无定时任务 | — | catalogued_unavailable |
| tushare | us_tbr | us_tbr | us_tbr | scheduled_pull |
| tushare | us_tltr | us_tltr | us_tltr | scheduled_pull |
| tushare | us_tradecal | us_tradecal | — | scheduled_pull |
| tushare | us_trltr | us_trltr | us_trltr | scheduled_pull |
| tushare | us_trycr | us_trycr | us_trycr | scheduled_pull |
| tushare | us_tycr | us_tycr | us_tycr | scheduled_pull |
| tushare | weekly | stk_weekly_monthly | — | scheduled_pull |
| tushare | wz_index | wz_index | — | scheduled_pull |
| tushare | yc_cb | 无定时任务 | — | catalogued_unavailable |
| financial_data | /api/v1/altdata/hot-plate-rank | ant_hot_plate_rank | ant_hot_plate_rank | query_through |
| financial_data | /api/v1/altdata/hot-stock-rank | ant_hot_stock_rank | ant_hot_stock_rank | query_through |
| financial_data | /api/v1/common/entity_relationship | 无定时任务 | — | query_through |
| financial_data | /api/v1/common/industry-chain-tree | 无定时任务 | — | query_through |
| financial_data | /api/v1/common/stock-belong-industry-chain | 无定时任务 | — | query_through |
| financial_data | /api/v1/common/symbol-by-cond | 无定时任务 | — | query_through |
| financial_data | /api/v1/common/trading-day | 无定时任务 | — | query_through |
| financial_data | /api/v1/common/trading-state | 无定时任务 | — | query_through |
| financial_data | /api/v1/fund/asset-allocation | 无定时任务 | — | query_through |
| financial_data | /api/v1/fund/bond-portfolio | 无定时任务 | — | query_through |
| financial_data | /api/v1/fund/dividend | 无定时任务 | — | query_through |
| financial_data | /api/v1/fund/fund-archive | 无定时任务 | — | query_through |
| financial_data | /api/v1/fund/fund-charge-rate | 无定时任务 | — | query_through |
| financial_data | /api/v1/fund/fund-company-info | 无定时任务 | — | query_through |
| financial_data | /api/v1/fund/fund-manager | 无定时任务 | — | query_through |
| financial_data | /api/v1/fund/fund-portfolio | 无定时任务 | — | query_through |
| financial_data | /api/v1/fund/invest-industry | 无定时任务 | — | query_through |
| financial_data | /api/v1/fund/net-value | 无定时任务 | — | query_through |
| financial_data | /api/v1/fund/plate-fund-relevancy | 无定时任务 | — | query_through |
| financial_data | /api/v1/fund/share-split | 无定时任务 | — | query_through |
| financial_data | /api/v1/fund/stock-portfolio | 无定时任务 | — | query_through |
| financial_data | /api/v1/fund/trade-limit | 无定时任务 | — | query_through |
| financial_data | /api/v1/fund/yield-rank | 无定时任务 | — | query_through |
| financial_data | /api/v1/fund_derived/benchmark-excess | 无定时任务 | — | query_through |
| financial_data | /api/v1/fund_derived/risk-return | 无定时任务 | — | query_through |
| financial_data | /api/v1/hk_stock/adr-conversion-ratio | 无定时任务 | — | query_through |
| financial_data | /api/v1/hk_stock/equity-structure | 无定时任务 | — | query_through |
| financial_data | /api/v1/hk_stock/free-float | 无定时任务 | — | query_through |
| financial_data | /api/v1/hk_stock/high-shareholding-concentration | 无定时任务 | — | query_through |
| financial_data | /api/v1/hk_stock/ipo-key-indicators | 无定时任务 | — | query_through |
| financial_data | /api/v1/hk_stock/ratings | 无定时任务 | — | query_through |
| financial_data | /api/v1/hk_stock/restricted-share-unlock-schedule | 无定时任务 | — | query_through |
| financial_data | /api/v1/hk_stock/risk-list | 无定时任务 | — | query_through |
| financial_data | /api/v1/hk_stock/shareholding-changes | 无定时任务 | — | query_through |
| financial_data | /api/v1/hk_stock/short-position-statistics | 无定时任务 | — | query_through |
| financial_data | /api/v1/hk_stock/short-selling | 无定时任务 | — | query_through |
| financial_data | /api/v1/hk_stock/special-notices | 无定时任务 | — | query_through |
| financial_data | /api/v1/hk_stock/special-securities | 无定时任务 | — | query_through |
| financial_data | /api/v1/hk_stock/suspend-resumption | 无定时任务 | — | query_through |
| financial_data | /api/v1/hk_stock/target-price | 无定时任务 | — | query_through |
| financial_data | /api/v1/hk_stock/temporary-parallel-trading | 无定时任务 | — | query_through |
| financial_data | /api/v1/index_fnd/index-constituents-list-weight | 无定时任务 | — | query_through |
| financial_data | /api/v1/index_fnd/index-fnd-estimates-summary | 无定时任务 | — | query_through |
| financial_data | /api/v1/index_fnd/index-fnd-financial-ratios | 无定时任务 | — | query_through |
| financial_data | /api/v1/index_fnd/index-fnd-financial-ratios-single | 无定时任务 | — | query_through |
| financial_data | /api/v1/index_fnd/index-fnd-financial-statement | 无定时任务 | — | query_through |
| financial_data | /api/v1/index_fnd/index-profile-basic-info | 无定时任务 | — | query_through |
| financial_data | /api/v1/info/announcements | 无定时任务 | — | query_through |
| financial_data | /api/v1/info/news-global-search | 无定时任务 | — | query_through |
| financial_data | /api/v1/info/research-reports | 无定时任务 | — | query_through |
| financial_data | /api/v1/info/tag/category | 无定时任务 | — | query_through |
| financial_data | /api/v1/info/tag/query | 无定时任务 | — | query_through |
| financial_data | /api/v1/macro/data-query | 无定时任务 | — | query_through |
| financial_data | /api/v1/macro/meta-search | 无定时任务 | — | query_through |
| financial_data | /api/v1/onecode/query | 无定时任务 | — | query_through |
| financial_data | /api/v1/onecode/recall | 无定时任务 | — | query_through |
| financial_data | /api/v1/quote/auction-snapshot | 无定时任务 | — | query_through |
| financial_data | /api/v1/quote/basic-snapshot | 无定时任务 | — | query_through |
| financial_data | /api/v1/quote/capital-flow-range | 无定时任务 | — | query_through |
| financial_data | /api/v1/quote/derived-snapshot | 无定时任务 | — | query_through |
| financial_data | /api/v1/quote/kline-batch | 无定时任务 | — | query_through |
| financial_data | /api/v1/sector/plate-component | 无定时任务 | — | query_through |
| financial_data | /api/v1/sector/plate-fund-relevancy | 无定时任务 | — | query_through |
| financial_data | /api/v1/sector/plate-list | 无定时任务 | — | query_through |
| financial_data | /api/v1/sector/sector-capital-flow | 无定时任务 | — | query_through |
| financial_data | /api/v1/sector/sector-financial-cumulative | 无定时任务 | — | query_through |
| financial_data | /api/v1/sector/sector-financial-point | 无定时任务 | — | query_through |
| financial_data | /api/v1/sector/sector-financial-quarterly | 无定时任务 | — | query_through |
| financial_data | /api/v1/sector/sector-valuation | 无定时任务 | — | query_through |
| financial_data | /api/v1/stock/after-daily-quote | 无定时任务 | — | query_through |
| financial_data | /api/v1/stock/ashare-cdr-conversion-ratio | 无定时任务 | — | query_through |
| financial_data | /api/v1/stock/block-trading-details | 无定时任务 | — | query_through |
| financial_data | /api/v1/stock/change-plan | 无定时任务 | — | query_through |
| financial_data | /api/v1/stock/component-list-belonged | 无定时任务 | — | query_through |
| financial_data | /api/v1/stock/daily-valuation-indicators | 无定时任务 | — | query_through |
| financial_data | /api/v1/stock/market-detail | 无定时任务 | — | query_through |
| financial_data | /api/v1/stock/risk-alerts | 无定时任务 | — | query_through |
| financial_data | /api/v1/stock/sc-activitie | 无定时任务 | — | query_through |
| financial_data | /api/v1/stock/sc-trade | 无定时任务 | — | query_through |
| financial_data | /api/v1/stock/sh-hold-stat | 无定时任务 | — | query_through |
| financial_data | /api/v1/stock/stock-index-constituents-list | 无定时任务 | — | query_through |
| financial_data | /api/v1/stock/suspend-resumption | 无定时任务 | — | query_through |
| financial_data | /api/v1/stock/tech-indicators | 无定时任务 | — | query_through |
| financial_data | /api/v1/stock/tech-patterns | 无定时任务 | — | query_through |
| financial_data | /api/v1/stock/tra-variant | 无定时任务 | — | query_through |
| financial_data | /api/v1/stock_fnd/actual-controller | ant_actual_controller | ant_actual_controller | query_through |
| financial_data | /api/v1/stock_fnd/asset-restructuring | 无定时任务 | — | query_through |
| financial_data | /api/v1/stock_fnd/balance-sheet | 无定时任务 | — | query_through |
| financial_data | /api/v1/stock_fnd/broker-golden-stocks | 无定时任务 | — | query_through |
| financial_data | /api/v1/stock_fnd/buyback-plans | 无定时任务 | — | query_through |
| financial_data | /api/v1/stock_fnd/concert-parties | 无定时任务 | — | query_through |
| financial_data | /api/v1/stock_fnd/consensus-details | 无定时任务 | — | query_through |
| financial_data | /api/v1/stock_fnd/consensus-stats | 无定时任务 | — | query_through |
| financial_data | /api/v1/stock_fnd/controlling-shareholder | ant_controlling_shareholder | ant_controlling_shareholder | query_through |
| financial_data | /api/v1/stock_fnd/delisting-info | 无定时任务 | — | query_through |
| financial_data | /api/v1/stock_fnd/depository-receipt | 无定时任务 | — | query_through |
| financial_data | /api/v1/stock_fnd/dividend-details | 无定时任务 | — | query_through |
| financial_data | /api/v1/stock_fnd/dividend-record | 无定时任务 | — | query_through |
| financial_data | /api/v1/stock_fnd/employee-ownership-plan | 无定时任务 | — | query_through |
| financial_data | /api/v1/stock_fnd/equity-structure | ant_equity_structure | ant_equity_structure | query_through |
| financial_data | /api/v1/stock_fnd/executive-compensation | 无定时任务 | — | query_through |
| financial_data | /api/v1/stock_fnd/free-float | ant_free_float | ant_free_float | query_through |
| financial_data | /api/v1/stock_fnd/fund-raising-usage | 无定时任务 | — | query_through |
| financial_data | /api/v1/stock_fnd/growth-rates-acc | 无定时任务 | — | query_through |
| financial_data | /api/v1/stock_fnd/growth-rates-quarter | 无定时任务 | — | query_through |
| financial_data | /api/v1/stock_fnd/guarantee-events | 无定时任务 | — | query_through |
| financial_data | /api/v1/stock_fnd/guarantee-stats | 无定时任务 | — | query_through |
| financial_data | /api/v1/stock_fnd/hk-intermediary-holdings | 无定时任务 | — | query_through |
| financial_data | /api/v1/stock_fnd/holder-count | 无定时任务 | — | query_through |
| financial_data | /api/v1/stock_fnd/holding-stats | 无定时任务 | — | query_through |
| financial_data | /api/v1/stock_fnd/holding-subsidiaries | 无定时任务 | — | query_through |
| financial_data | /api/v1/stock_fnd/income-cashflow-acc | 无定时任务 | — | query_through |
| financial_data | /api/v1/stock_fnd/income-cashflow-single | 无定时任务 | — | query_through |
| financial_data | /api/v1/stock_fnd/industry-classification | 无定时任务 | — | query_through |
| financial_data | /api/v1/stock_fnd/investor-relations | 无定时任务 | — | query_through |
| financial_data | /api/v1/stock_fnd/ipo-primary | 无定时任务 | — | query_through |
| financial_data | /api/v1/stock_fnd/ipo-quote-details | 无定时任务 | — | query_through |
| financial_data | /api/v1/stock_fnd/ipo-winning-numbers | 无定时任务 | — | query_through |
| financial_data | /api/v1/stock_fnd/listing-rules | 无定时任务 | — | query_through |
| financial_data | /api/v1/stock_fnd/litigation-arbitration | 无定时任务 | — | query_through |
| financial_data | /api/v1/stock_fnd/main-business-business | 无定时任务 | — | query_through |
| financial_data | /api/v1/stock_fnd/main-business-industry | 无定时任务 | — | query_through |
| financial_data | /api/v1/stock_fnd/main-business-product | 无定时任务 | — | query_through |
| financial_data | /api/v1/stock_fnd/main-business-region | 无定时任务 | — | query_through |
| financial_data | /api/v1/stock_fnd/metrics-ttm | 无定时任务 | — | query_through |
| financial_data | /api/v1/stock_fnd/performance-forecast | 无定时任务 | — | query_through |
| financial_data | /api/v1/stock_fnd/prelim-acc | 无定时任务 | — | query_through |
| financial_data | /api/v1/stock_fnd/prelim-balance | 无定时任务 | — | query_through |
| financial_data | /api/v1/stock_fnd/prelim-quarter | 无定时任务 | — | query_through |
| financial_data | /api/v1/stock_fnd/rating-summary | 无定时任务 | — | query_through |
| financial_data | /api/v1/stock_fnd/regulatory-penalties | 无定时任务 | — | query_through |
| financial_data | /api/v1/stock_fnd/related-party-transactions | 无定时任务 | — | query_through |
| financial_data | /api/v1/stock_fnd/restricted-release-calendar | 无定时任务 | — | query_through |
| financial_data | /api/v1/stock_fnd/review-process | 无定时任务 | — | query_through |
| financial_data | /api/v1/stock_fnd/risk-factor-csi300 | 无定时任务 | — | query_through |
| financial_data | /api/v1/stock_fnd/risk-factor-csi500 | 无定时任务 | — | query_through |
| financial_data | /api/v1/stock_fnd/risk-factor-sh000001 | 无定时任务 | — | query_through |
| financial_data | /api/v1/stock_fnd/risk-factor-sw | 无定时任务 | — | query_through |
| financial_data | /api/v1/stock_fnd/seo-placement-details | 无定时任务 | — | query_through |
| financial_data | /api/v1/stock_fnd/shareholder-commitment | 无定时任务 | — | query_through |
| financial_data | /api/v1/stock_fnd/shareholder-list | 无定时任务 | — | query_through |
| financial_data | /api/v1/stock_fnd/shareholder-meeting | 无定时任务 | — | query_through |
| financial_data | /api/v1/stock_fnd/specialty-metrics-period | 无定时任务 | — | query_through |
| financial_data | /api/v1/stock_fnd/specialty-metrics-point | 无定时任务 | — | query_through |
| financial_data | /api/v1/stock_fnd/stock-basic-info | 无定时任务 | — | query_through |
| financial_data | /api/v1/stock_fnd/stock-rel-fund-holdings-top | 无定时任务 | — | query_through |
| financial_data | /api/v1/stock_fnd/style-classification | ant_style_classification | ant_style_classification | query_through |
| financial_data | /api/v1/stock_fnd/takeover-offers | 无定时任务 | — | query_through |
| financial_data | /api/v1/stock_fnd/target-price | 无定时任务 | — | query_through |
| financial_data | /api/v1/stock_fnd/tender-offers | 无定时任务 | — | query_through |
| financial_data | /api/v1/stock_fnd/yield-factor | 无定时任务 | — | query_through |
| financial_data | /api/v1/stock_sh_equity/freeze-pledge | 无定时任务 | — | query_through |
| financial_data | /api/v1/us_stock/adr-ratio-changes | 无定时任务 | — | query_through |
| financial_data | /api/v1/us_stock/capital-events | 无定时任务 | — | query_through |
| financial_data | /api/v1/us_stock/company-ownership | 无定时任务 | — | query_through |
| financial_data | /api/v1/us_stock/concept-components | 无定时任务 | — | query_through |
| financial_data | /api/v1/us_stock/dividends | 无定时任务 | — | query_through |
| financial_data | /api/v1/us_stock/equity-structure | 无定时任务 | — | query_through |
| financial_data | /api/v1/us_stock/ratings | 无定时任务 | — | query_through |
| financial_data | /api/v1/us_stock/security-markings | 无定时任务 | — | query_through |
| financial_data | /api/v1/us_stock/target-price | 无定时任务 | — | query_through |
| financial_data | /api/v2/info/news/article | 无定时任务 | — | query_through |
| financial_data | /api/v2/info/news/search_evidence | 无定时任务 | — | query_through |
| chinabond | yield_curve | 无定时任务 | — | query_through |
| chinabond | yield_curve_history | chinabond_yield_curve | chinabond_yield_curve | scheduled_pull |
| chinamoney | lpr_history | cn_lpr | cn_lpr | scheduled_pull |
| chinamoney | repo_fixing | 无定时任务 | — | query_through |
| cninfo | announcements | cninfo_announcements | cninfo_announcements | scheduled_pull |
| cninfo | investor_questions | 无定时任务 | — | query_through |
| pboc | social_financing | 无定时任务 | — | query_through |
| sina | option_contracts | 无定时任务 | — | query_through |
| sina | option_greeks | 无定时任务 | — | query_through |
| sina | option_quote | 无定时任务 | — | query_through |
| sse | investor_questions | 无定时任务 | — | query_through |
