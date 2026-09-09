# Tushare 无权限接口复核

- 复核时间：`2026-09-09T18:09:20.002198+08:00`
- Token：从运行环境读取，报告不保存 Token 或其派生值
- 双重探测：每个接口 `2` 次
- 契约标记无权限：`40`
- 仍明确返回无权限：`39`
- 权限变化（双次确认已开通）：`1`

| 接口 | 结论 | 返回码 | 官方文档 |
|---|---|---|---|
| `anns_d` | 确认无权限 | `40203, 40203` | [文档](https://tushare.pro/document/2?doc_id=176) |
| `cb_price_chg` | 确认无权限 | `40203, 40203` | [文档](https://tushare.pro/document/2?doc_id=246) |
| `cctv_news` | 确认无权限 | `40203, 40203` | [文档](https://tushare.pro/document/2?doc_id=154) |
| `etf_mins` | 确认无权限 | `40203, 40203` | [文档](https://tushare.pro/document/2?doc_id=387) |
| `factor_list` | 确认无权限 | `40203, 40203` | [文档](https://tushare.pro/document/2?doc_id=486) |
| `ft_mins` | 确认无权限 | `40203, 40203` | [文档](https://tushare.pro/document/2?doc_id=313) |
| `hk_adjfactor` | 确认无权限 | `40203, 40203` | [文档](https://tushare.pro/document/2?doc_id=401) |
| `hk_balancesheet` | 确认无权限 | `40203, 40203` | [文档](https://tushare.pro/document/2?doc_id=390) |
| `hk_cashflow` | 确认无权限 | `40203, 40203` | [文档](https://tushare.pro/document/2?doc_id=391) |
| `hk_daily_adj` | 确认无权限 | `40203, 40203` | [文档](https://tushare.pro/document/2?doc_id=339) |
| `hk_fina_indicator` | 确认无权限 | `40203, 40203` | [文档](https://tushare.pro/document/2?doc_id=388) |
| `hk_income` | 确认无权限 | `40203, 40203` | [文档](https://tushare.pro/document/2?doc_id=389) |
| `hk_mins` | 确认无权限 | `40203, 40203` | [文档](https://tushare.pro/document/2?doc_id=304) |
| `hm_detail` | 确认无权限 | `40203, 40203` | [文档](https://tushare.pro/document/2?doc_id=312) |
| `idx_mins` | 确认无权限 | `40203, 40203` | [文档](https://tushare.pro/document/2?doc_id=419) |
| `irm_qa_sh` | 确认无权限 | `40203, 40203` | [文档](https://tushare.pro/document/2?doc_id=366) |
| `irm_qa_sz` | 确认无权限 | `40203, 40203` | [文档](https://tushare.pro/document/2?doc_id=367) |
| `monetary_policy` | 确认无权限 | `40203, 40203` | [文档](https://tushare.pro/document/2?doc_id=465) |
| `news` | 确认无权限 | `40203, 40203` | [文档](https://tushare.pro/document/2?doc_id=143) |
| `npr` | 确认无权限 | `40203, 40203` | [文档](https://tushare.pro/document/2?doc_id=406) |
| `opt_mins` | 确认无权限 | `40203, 40203` | [文档](https://tushare.pro/document/2?doc_id=341) |
| `research_report` | 确认无权限 | `40203, 40203` | [文档](https://tushare.pro/document/2?doc_id=415) |
| `rt_etf_sz_iopv` | 确认无权限 | `40203, 40203` | [文档](https://tushare.pro/document/2?doc_id=454) |
| `rt_fut_min` | 确认无权限 | `40203, 40203` | [文档](https://tushare.pro/document/2?doc_id=340) |
| `rt_fut_min_daily` | 确认无权限 | `40203, 40203` | [文档](https://tushare.pro/document/2?doc_id=340) |
| `rt_hk_k` | 权限已开通，契约与采集器已同步启用 | `0, 0` | [文档](https://tushare.pro/document/2?doc_id=383) |
| `rt_idx_k` | 确认无权限 | `40203, 40203` | [文档](https://tushare.pro/document/2?doc_id=403) |
| `rt_idx_min` | 确认无权限 | `40203, 40203` | [文档](https://tushare.pro/document/2?doc_id=420) |
| `rt_idx_min_daily` | 确认无权限 | `40203, 40203` | [文档](https://tushare.pro/document/2?doc_id=420) |
| `rt_sw_k` | 确认无权限 | `40203, 40203` | [文档](https://tushare.pro/document/2?doc_id=417) |
| `stk_premarket` | 确认无权限 | `40203, 40203` | [文档](https://tushare.pro/document/2?doc_id=329) |
| `sw_mins` | 确认无权限 | `40203, 40203` | [文档](https://tushare.pro/document/2?doc_id=469) |
| `us_adjfactor` | 确认无权限 | `40203, 40203` | [文档](https://tushare.pro/document/2?doc_id=402) |
| `us_balancesheet` | 确认无权限 | `40203, 40203` | [文档](https://tushare.pro/document/2?doc_id=395) |
| `us_cashflow` | 确认无权限 | `40203, 40203` | [文档](https://tushare.pro/document/2?doc_id=396) |
| `us_daily` | 确认无权限 | `40203, 40203` | [文档](https://tushare.pro/document/2?doc_id=254) |
| `us_daily_adj` | 确认无权限 | `40203, 40203` | [文档](https://tushare.pro/document/2?doc_id=338) |
| `us_fina_indicator` | 确认无权限 | `40203, 40203` | [文档](https://tushare.pro/document/2?doc_id=393) |
| `us_income` | 确认无权限 | `40203, 40203` | [文档](https://tushare.pro/document/2?doc_id=394) |
| `yc_cb` | 确认无权限 | `40203, 40203` | [文档](https://tushare.pro/document/2?doc_id=201) |
