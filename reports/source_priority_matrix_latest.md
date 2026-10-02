# 数据源优先级矩阵

> 生成时间：`2026-10-02T11:06:19.905188+00:00`。机器可读版本见 [`source_priority_matrix_latest.json`](source_priority_matrix_latest.json)。

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

## 供应商语义能力四分类

这组数字回答供应商能否提供同一业务事实，与本地是否已经落表、当前 Token 是否有权限相互独立。只有覆盖完整 Financial Data 合同才算等价；局部市场或字段重叠仍归入 `financial_data_only`。

| Financial Data 路由 | Tushare 直接等价 | Tushare 确定性派生 | Tushare 公告解析 | Financial Data 必需 | 当前 Token 可完整执行 | 部分 Tushare 重叠 |
|---:|---:|---:|---:|---:|---:|---:|
| 163 | 26 | 34 | 22 | 81 | 51 | 52 |

## Financial Data ↔ Tushare 逐条映射

| Financial Data 路由 | 四类归属 | 完整等价所需 Tushare 接口 | 仅局部重叠接口 | 当前 Token 完整可用 | 判定依据 |
|---|---|---|---|---|---|
| `/api/v1/altdata/hot-plate-rank` | `financial_data_only` | — | `ths_hot`(有权限), `dc_hot`(有权限), `limit_cpt_list`(有权限) | 否 | Financial Data 是支付宝口径；Tushare 热榜的数据源和排名方法不同。 |
| `/api/v1/altdata/hot-stock-rank` | `financial_data_only` | — | `ths_hot`(有权限), `dc_hot`(有权限) | 否 | Financial Data 是支付宝散户关注度；Tushare 热榜不能复现该口径。 |
| `/api/v1/common/entity_relationship` | `financial_data_only` | — | `stk_ah_comparison`(有权限), `bse_mapping`(有权限), `namechange`(有权限) | 否 | Tushare 仅覆盖部分 AH、北交所代码及曾用名关系，缺少完整跨市场实体图谱。 |
| `/api/v1/common/industry-chain-tree` | `financial_data_only` | — | — | 否 | 在已审计的 Tushare 契约中没有覆盖完整合同的结构化、可确定性派生或公告来源。 |
| `/api/v1/common/stock-belong-industry-chain` | `financial_data_only` | — | — | 否 | 在已审计的 Tushare 契约中没有覆盖完整合同的结构化、可确定性派生或公告来源。 |
| `/api/v1/common/symbol-by-cond` | `tushare_direct` | `stock_basic`(有权限), `hk_basic`(有权限), `us_basic`(有权限), `fund_basic`(有权限), `index_basic`(有权限), `sge_basic`(有权限) | — | 是 | Tushare 有覆盖该完整业务事实的结构化接口；仍需统一字段、代码、日期和单位。 |
| `/api/v1/common/trading-day` | `financial_data_only` | — | `trade_cal`(有权限), `hk_tradecal`(有权限), `us_tradecal`(有权限), `fut_trade_cal`(有权限) | 否 | Tushare 有 A/H/US/期货日历，但没有覆盖该合同中现货等全部资产的统一交易日历。 |
| `/api/v1/common/trading-state` | `financial_data_only` | — | `trade_cal`(有权限), `hk_tradecal`(有权限), `us_tradecal`(有权限), `rt_hk_k`(有权限), `rt_idx_k`(无权限) | 否 | Tushare 没有覆盖多资产市场的统一实时交易状态接口。 |
| `/api/v1/fund/asset-allocation` | `financial_data_only` | — | `fund_portfolio`(有权限), `fund_nav`(有权限) | 否 | Tushare 基金持仓不提供股票、债券、现金等完整大类资产配置表。 |
| `/api/v1/fund/bond-portfolio` | `financial_data_only` | — | — | 否 | Tushare fund_portfolio 是公募股票持仓，不能替代重仓债券明细。 |
| `/api/v1/fund/dividend` | `tushare_direct` | `fund_div`(有权限) | — | 是 | Tushare 有覆盖该完整业务事实的结构化接口；仍需统一字段、代码、日期和单位。 |
| `/api/v1/fund/fund-archive` | `financial_data_only` | — | `fund_basic`(有权限) | 否 | fund_basic 有基础字段，但缺少完整投资策略、风险评估和申购确认等合同字段。 |
| `/api/v1/fund/fund-charge-rate` | `financial_data_only` | — | `fund_basic`(有权限) | 否 | fund_basic 的管理/托管费不能替代分档申购、赎回和认购费率。 |
| `/api/v1/fund/fund-company-info` | `tushare_derived` | `fund_company`(有权限), `fund_basic`(有权限), `fund_share`(有权限) | — | 是 | 可由所列 Tushare 结构化数据确定性计算；公式、权重与 as-of 规则必须版本化。 |
| `/api/v1/fund/fund-manager` | `tushare_direct` | `fund_manager`(有权限) | — | 是 | Tushare 有覆盖该完整业务事实的结构化接口；仍需统一字段、代码、日期和单位。 |
| `/api/v1/fund/fund-portfolio` | `financial_data_only` | — | — | 否 | Tushare 缺少 FOF 持有底层基金的结构化明细。 |
| `/api/v1/fund/invest-industry` | `tushare_derived` | `fund_portfolio`(有权限), `stock_basic`(有权限), `index_member_all`(有权限) | — | 是 | 可由所列 Tushare 结构化数据确定性计算；公式、权重与 as-of 规则必须版本化。 |
| `/api/v1/fund/net-value` | `financial_data_only` | — | `fund_nav`(有权限), `fund_daily`(有权限) | 否 | fund_nav/fund_daily 有普通基金净值行情，但缺少货币基金七日年化和万份收益字段。 |
| `/api/v1/fund/plate-fund-relevancy` | `tushare_derived` | `fund_portfolio`(有权限), `ths_member`(有权限), `dc_member`(有权限), `tdx_member`(有权限) | — | 是 | 可由所列 Tushare 结构化数据确定性计算；公式、权重与 as-of 规则必须版本化。 |
| `/api/v1/fund/share-split` | `financial_data_only` | — | `fund_adj`(有权限) | 否 | fund_adj 只能观察复权因子变化，不能确定拆分类型和登记变更日。 |
| `/api/v1/fund/stock-portfolio` | `tushare_direct` | `fund_portfolio`(有权限) | — | 是 | Tushare 有覆盖该完整业务事实的结构化接口；仍需统一字段、代码、日期和单位。 |
| `/api/v1/fund/trade-limit` | `financial_data_only` | — | `fund_basic`(有权限) | 否 | Tushare 缺少按业务类型、收费方式展开的场外基金交易限制。 |
| `/api/v1/fund/yield-rank` | `tushare_derived` | `fund_nav`(有权限), `fund_daily`(有权限), `fund_basic`(有权限) | — | 是 | 可由所列 Tushare 结构化数据确定性计算；公式、权重与 as-of 规则必须版本化。 |
| `/api/v1/fund_derived/benchmark-excess` | `tushare_derived` | `fund_nav`(有权限), `fund_daily`(有权限), `mkt_idx_bmk`(有权限), `index_daily`(有权限) | — | 是 | 可由所列 Tushare 结构化数据确定性计算；公式、权重与 as-of 规则必须版本化。 |
| `/api/v1/fund_derived/risk-return` | `tushare_derived` | `fund_nav`(有权限), `fund_daily`(有权限), `index_daily`(有权限) | — | 是 | 可由所列 Tushare 结构化数据确定性计算；公式、权重与 as-of 规则必须版本化。 |
| `/api/v1/hk_stock/adr-conversion-ratio` | `financial_data_only` | — | — | 否 | 在已审计的 Tushare 契约中没有覆盖完整合同的结构化、可确定性派生或公告来源。 |
| `/api/v1/hk_stock/equity-structure` | `financial_data_only` | — | `hk_daily_adj`(无权限) | 否 | 在已审计的 Tushare 契约中没有覆盖完整合同的结构化、可确定性派生或公告来源。 |
| `/api/v1/hk_stock/free-float` | `financial_data_only` | — | `hk_daily_adj`(无权限) | 否 | 在已审计的 Tushare 契约中没有覆盖完整合同的结构化、可确定性派生或公告来源。 |
| `/api/v1/hk_stock/high-shareholding-concentration` | `financial_data_only` | — | `ccass_hold`(有权限), `ccass_hold_detail`(有权限) | 否 | 在已审计的 Tushare 契约中没有覆盖完整合同的结构化、可确定性派生或公告来源。 |
| `/api/v1/hk_stock/ipo-key-indicators` | `financial_data_only` | — | — | 否 | 在已审计的 Tushare 契约中没有覆盖完整合同的结构化、可确定性派生或公告来源。 |
| `/api/v1/hk_stock/ratings` | `financial_data_only` | — | — | 否 | 在已审计的 Tushare 契约中没有覆盖完整合同的结构化、可确定性派生或公告来源。 |
| `/api/v1/hk_stock/restricted-share-unlock-schedule` | `financial_data_only` | — | — | 否 | 在已审计的 Tushare 契约中没有覆盖完整合同的结构化、可确定性派生或公告来源。 |
| `/api/v1/hk_stock/risk-list` | `financial_data_only` | — | — | 否 | 在已审计的 Tushare 契约中没有覆盖完整合同的结构化、可确定性派生或公告来源。 |
| `/api/v1/hk_stock/shareholding-changes` | `financial_data_only` | — | — | 否 | 在已审计的 Tushare 契约中没有覆盖完整合同的结构化、可确定性派生或公告来源。 |
| `/api/v1/hk_stock/short-position-statistics` | `financial_data_only` | — | — | 否 | 在已审计的 Tushare 契约中没有覆盖完整合同的结构化、可确定性派生或公告来源。 |
| `/api/v1/hk_stock/short-selling` | `financial_data_only` | — | — | 否 | 在已审计的 Tushare 契约中没有覆盖完整合同的结构化、可确定性派生或公告来源。 |
| `/api/v1/hk_stock/special-notices` | `financial_data_only` | — | — | 否 | 在已审计的 Tushare 契约中没有覆盖完整合同的结构化、可确定性派生或公告来源。 |
| `/api/v1/hk_stock/special-securities` | `financial_data_only` | — | — | 否 | 在已审计的 Tushare 契约中没有覆盖完整合同的结构化、可确定性派生或公告来源。 |
| `/api/v1/hk_stock/suspend-resumption` | `financial_data_only` | — | — | 否 | 在已审计的 Tushare 契约中没有覆盖完整合同的结构化、可确定性派生或公告来源。 |
| `/api/v1/hk_stock/target-price` | `financial_data_only` | — | — | 否 | 在已审计的 Tushare 契约中没有覆盖完整合同的结构化、可确定性派生或公告来源。 |
| `/api/v1/hk_stock/temporary-parallel-trading` | `financial_data_only` | — | — | 否 | 在已审计的 Tushare 契约中没有覆盖完整合同的结构化、可确定性派生或公告来源。 |
| `/api/v1/index_fnd/index-constituents-list-weight` | `financial_data_only` | — | `index_weight`(有权限), `index_member_all`(有权限) | 否 | Tushare 可覆盖 A 股主要指数，不能完整覆盖该合同声明的港股指数成分。 |
| `/api/v1/index_fnd/index-fnd-estimates-summary` | `tushare_derived` | `index_weight`(有权限), `index_member_all`(有权限), `report_rc`(有权限) | — | 是 | 可由所列 Tushare 结构化数据确定性计算；公式、权重与 as-of 规则必须版本化。 |
| `/api/v1/index_fnd/index-fnd-financial-ratios` | `tushare_derived` | `index_weight`(有权限), `index_member_all`(有权限), `fina_indicator`(有权限), `income`(有权限), `balancesheet`(有权限) | — | 是 | 可由所列 Tushare 结构化数据确定性计算；公式、权重与 as-of 规则必须版本化。 |
| `/api/v1/index_fnd/index-fnd-financial-ratios-single` | `tushare_derived` | `index_weight`(有权限), `index_member_all`(有权限), `fina_indicator`(有权限), `income`(有权限), `balancesheet`(有权限) | — | 是 | 可由所列 Tushare 结构化数据确定性计算；公式、权重与 as-of 规则必须版本化。 |
| `/api/v1/index_fnd/index-fnd-financial-statement` | `tushare_derived` | `index_weight`(有权限), `index_member_all`(有权限), `income`(有权限), `balancesheet`(有权限), `cashflow`(有权限) | — | 是 | 可由所列 Tushare 结构化数据确定性计算；公式、权重与 as-of 规则必须版本化。 |
| `/api/v1/index_fnd/index-profile-basic-info` | `tushare_direct` | `index_basic`(有权限) | — | 是 | Tushare 有覆盖该完整业务事实的结构化接口；仍需统一字段、代码、日期和单位。 |
| `/api/v1/info/announcements` | `financial_data_only` | — | `anns_d`(无权限) | 否 | anns_d 提供 A 股公告 PDF，不能完整覆盖 Financial Data 的 A 股与港股合同。 |
| `/api/v1/info/news-global-search` | `financial_data_only` | — | `news`(无权限), `major_news`(有权限) | 否 | Tushare 新闻源可做局部检索，但不是全网搜索与证据抽取服务。 |
| `/api/v1/info/research-reports` | `tushare_direct` | `research_report`(无权限) | — | 否 | Tushare 有覆盖该完整业务事实的结构化接口；仍需统一字段、代码、日期和单位。 |
| `/api/v1/info/tag/category` | `financial_data_only` | — | `news`(无权限), `major_news`(有权限) | 否 | 在已审计的 Tushare 契约中没有覆盖完整合同的结构化、可确定性派生或公告来源。 |
| `/api/v1/info/tag/query` | `financial_data_only` | — | `news`(无权限), `major_news`(有权限) | 否 | 在已审计的 Tushare 契约中没有覆盖完整合同的结构化、可确定性派生或公告来源。 |
| `/api/v1/macro/data-query` | `financial_data_only` | — | `cn_gdp`(有权限), `cn_cpi`(有权限), `cn_ppi`(有权限), `cn_pmi`(有权限), `cn_m`(有权限), `sf_month`(有权限), `shibor`(有权限), `shibor_lpr`(有权限), `us_tbr`(有权限), `us_tltr`(有权限), `us_trltr`(有权限), `us_trycr`(有权限), `us_tycr`(有权限) | 否 | Tushare 有核心宏观序列，但不覆盖地区、长尾国家和细分产业指标全集。 |
| `/api/v1/macro/meta-search` | `financial_data_only` | — | `cn_schedule`(有权限), `cn_gdp`(有权限), `cn_cpi`(有权限), `cn_ppi`(有权限), `cn_pmi`(有权限), `cn_m`(有权限) | 否 | Tushare 没有与 Financial Data 长尾宏观指标库等价的语义检索目录。 |
| `/api/v1/onecode/query` | `financial_data_only` | — | `factor_value`(有权限), `daily`(有权限), `daily_basic`(有权限), `fund_nav`(有权限), `index_daily`(有权限) | 否 | 部分指标可由 Tushare 计算，但 OneCode 动态指标全集及其口径不是公开等价物。 |
| `/api/v1/onecode/recall` | `financial_data_only` | — | `factor_list`(无权限) | 否 | factor_list 仅覆盖 Tushare 量化因子，不能替代 OneCode 全指标语义召回。 |
| `/api/v1/quote/auction-snapshot` | `financial_data_only` | — | `stk_auction`(有权限), `stk_auction_o`(有权限), `stk_auction_c`(有权限) | 否 | stk_auction 系列只给最终开/收盘竞价结果，不能提供指定时段内未撮合买卖量的快照序列。 |
| `/api/v1/quote/basic-snapshot` | `financial_data_only` | — | `stk_mins`(有权限（当前限频）), `hk_mins`(无权限), `etf_mins`(无权限), `idx_mins`(无权限), `rt_hk_k`(有权限), `rt_idx_k`(无权限), `rt_sw_k`(无权限), `rt_etf_sz_iopv`(无权限) | 否 | Tushare 只有若干品种实时接口，缺少统一 A/H/US/基金/板块/指数/现货快照。 |
| `/api/v1/quote/capital-flow-range` | `tushare_derived` | `moneyflow`(有权限), `moneyflow_dc`(有权限), `moneyflow_ths`(有权限), `moneyflow_ind_dc`(有权限), `moneyflow_ind_ths`(有权限), `moneyflow_mkt_dc`(有权限) | — | 是 | 可由所列 Tushare 结构化数据确定性计算；公式、权重与 as-of 规则必须版本化。 |
| `/api/v1/quote/derived-snapshot` | `financial_data_only` | — | `daily_basic`(有权限), `hk_daily_adj`(无权限), `us_daily_adj`(无权限) | 否 | 历史/日频估值不能替代跨市场实时衍生快照。 |
| `/api/v1/quote/kline-batch` | `tushare_derived` | `daily`(有权限), `weekly`(有权限), `monthly`(有权限), `stk_weekly_monthly`(有权限), `hk_daily_adj`(无权限), `us_daily_adj`(无权限), `fund_daily`(有权限), `index_daily`(有权限), `index_weekly`(有权限), `index_monthly`(有权限), `tdx_daily`(有权限), `sge_daily`(有权限) | — | 否 | 可由所列 Tushare 结构化数据确定性计算；公式、权重与 as-of 规则必须版本化。 |
| `/api/v1/sector/plate-component` | `tushare_direct` | `ths_member`(有权限), `dc_member`(有权限), `tdx_member`(有权限), `index_member_all`(有权限) | — | 是 | Tushare 有覆盖该完整业务事实的结构化接口；仍需统一字段、代码、日期和单位。 |
| `/api/v1/sector/plate-fund-relevancy` | `tushare_derived` | `fund_portfolio`(有权限), `ths_member`(有权限), `dc_member`(有权限), `tdx_member`(有权限) | — | 是 | 可由所列 Tushare 结构化数据确定性计算；公式、权重与 as-of 规则必须版本化。 |
| `/api/v1/sector/plate-list` | `tushare_direct` | `ths_index`(有权限), `dc_index`(有权限), `tdx_index`(有权限), `index_classify`(有权限) | — | 是 | Tushare 有覆盖该完整业务事实的结构化接口；仍需统一字段、代码、日期和单位。 |
| `/api/v1/sector/sector-capital-flow` | `tushare_derived` | `margin_detail`(有权限), `index_member_all`(有权限), `ths_member`(有权限), `dc_member`(有权限) | — | 是 | 可由所列 Tushare 结构化数据确定性计算；公式、权重与 as-of 规则必须版本化。 |
| `/api/v1/sector/sector-financial-cumulative` | `tushare_derived` | `index_member_all`(有权限), `ths_member`(有权限), `dc_member`(有权限), `income`(有权限), `balancesheet`(有权限), `cashflow`(有权限), `fina_indicator`(有权限) | — | 是 | 可由所列 Tushare 结构化数据确定性计算；公式、权重与 as-of 规则必须版本化。 |
| `/api/v1/sector/sector-financial-point` | `tushare_derived` | `index_member_all`(有权限), `ths_member`(有权限), `dc_member`(有权限), `balancesheet`(有权限), `fina_indicator`(有权限) | — | 是 | 可由所列 Tushare 结构化数据确定性计算；公式、权重与 as-of 规则必须版本化。 |
| `/api/v1/sector/sector-financial-quarterly` | `tushare_derived` | `index_member_all`(有权限), `ths_member`(有权限), `dc_member`(有权限), `income`(有权限), `cashflow`(有权限), `fina_indicator`(有权限) | — | 是 | 可由所列 Tushare 结构化数据确定性计算；公式、权重与 as-of 规则必须版本化。 |
| `/api/v1/sector/sector-valuation` | `tushare_derived` | `index_member_all`(有权限), `ths_member`(有权限), `dc_member`(有权限), `daily_basic`(有权限), `index_dailybasic`(有权限) | — | 是 | 可由所列 Tushare 结构化数据确定性计算；公式、权重与 as-of 规则必须版本化。 |
| `/api/v1/stock/after-daily-quote` | `financial_data_only` | — | — | 否 | Tushare 日行情不包含盘后固定价格成交及盘后买卖申报数量。 |
| `/api/v1/stock/ashare-cdr-conversion-ratio` | `financial_data_only` | — | — | 否 | Tushare 没有 A 股 CDR 与基础证券转换比例历史。 |
| `/api/v1/stock/block-trading-details` | `tushare_direct` | `block_trade`(有权限) | — | 是 | Tushare 有覆盖该完整业务事实的结构化接口；仍需统一字段、代码、日期和单位。 |
| `/api/v1/stock/change-plan` | `tushare_announcement_parse` | `anns_d`(无权限) | — | 否 | Tushare 没有等价结构化表，但可从 anns_d 官方公告 PDF 提取并保留证据链。 |
| `/api/v1/stock/component-list-belonged` | `tushare_direct` | `index_member_all`(有权限), `ths_member`(有权限), `dc_member`(有权限), `tdx_member`(有权限) | — | 是 | Tushare 有覆盖该完整业务事实的结构化接口；仍需统一字段、代码、日期和单位。 |
| `/api/v1/stock/daily-valuation-indicators` | `tushare_direct` | `daily_basic`(有权限) | — | 是 | Tushare 有覆盖该完整业务事实的结构化接口；仍需统一字段、代码、日期和单位。 |
| `/api/v1/stock/market-detail` | `financial_data_only` | — | `margin_detail`(有权限) | 否 | margin_detail 覆盖核心两融数据，但缺少担保券数量、市值及交易所占比等合同字段。 |
| `/api/v1/stock/risk-alerts` | `tushare_direct` | `stk_alert`(有权限), `stock_st`(有权限), `st`(有权限) | — | 是 | Tushare 有覆盖该完整业务事实的结构化接口；仍需统一字段、代码、日期和单位。 |
| `/api/v1/stock/sc-activitie` | `tushare_direct` | `hsgt_top10`(有权限), `ggt_top10`(有权限) | — | 是 | Tushare 有覆盖该完整业务事实的结构化接口；仍需统一字段、代码、日期和单位。 |
| `/api/v1/stock/sc-trade` | `tushare_derived` | `moneyflow_hsgt`(有权限), `ggt_daily`(有权限) | — | 是 | 可由所列 Tushare 结构化数据确定性计算；公式、权重与 as-of 规则必须版本化。 |
| `/api/v1/stock/sh-hold-stat` | `tushare_direct` | `hk_hold`(有权限), `stock_hsgt`(有权限) | — | 是 | Tushare 有覆盖该完整业务事实的结构化接口；仍需统一字段、代码、日期和单位。 |
| `/api/v1/stock/stock-index-constituents-list` | `financial_data_only` | — | `index_member_all`(有权限), `index_weight`(有权限) | 否 | Tushare 可反查部分 A 股指数归属，缺少该合同声明的港股指数归属全集。 |
| `/api/v1/stock/suspend-resumption` | `tushare_direct` | `suspend_d`(有权限) | — | 是 | Tushare 有覆盖该完整业务事实的结构化接口；仍需统一字段、代码、日期和单位。 |
| `/api/v1/stock/tech-indicators` | `tushare_derived` | `daily`(有权限), `adj_factor`(有权限), `hk_daily_adj`(无权限), `us_daily_adj`(无权限), `stk_factor`(有权限), `stk_factor_pro`(有权限) | — | 否 | 可由所列 Tushare 结构化数据确定性计算；公式、权重与 as-of 规则必须版本化。 |
| `/api/v1/stock/tech-patterns` | `tushare_derived` | `daily`(有权限), `adj_factor`(有权限), `stk_factor_pro`(有权限), `stk_nineturn`(有权限) | — | 是 | 可由所列 Tushare 结构化数据确定性计算；公式、权重与 as-of 规则必须版本化。 |
| `/api/v1/stock/tra-variant` | `tushare_direct` | `top_list`(有权限), `top_inst`(有权限), `stk_shock`(有权限), `stk_high_shock`(有权限) | — | 是 | Tushare 有覆盖该完整业务事实的结构化接口；仍需统一字段、代码、日期和单位。 |
| `/api/v1/stock_fnd/actual-controller` | `tushare_announcement_parse` | `anns_d`(无权限) | — | 否 | Tushare 没有等价结构化表，但可从 anns_d 官方公告 PDF 提取并保留证据链。 |
| `/api/v1/stock_fnd/asset-restructuring` | `tushare_announcement_parse` | `anns_d`(无权限) | — | 否 | Tushare 没有等价结构化表，但可从 anns_d 官方公告 PDF 提取并保留证据链。 |
| `/api/v1/stock_fnd/balance-sheet` | `tushare_direct` | `balancesheet`(有权限), `hk_balancesheet`(无权限), `us_balancesheet`(无权限) | — | 否 | Tushare 有覆盖该完整业务事实的结构化接口；仍需统一字段、代码、日期和单位。 |
| `/api/v1/stock_fnd/broker-golden-stocks` | `tushare_direct` | `broker_recommend`(有权限) | — | 是 | Tushare 有覆盖该完整业务事实的结构化接口；仍需统一字段、代码、日期和单位。 |
| `/api/v1/stock_fnd/buyback-plans` | `tushare_direct` | `repurchase`(有权限) | — | 是 | Tushare 有覆盖该完整业务事实的结构化接口；仍需统一字段、代码、日期和单位。 |
| `/api/v1/stock_fnd/concert-parties` | `tushare_announcement_parse` | `anns_d`(无权限) | — | 否 | Tushare 没有等价结构化表，但可从 anns_d 官方公告 PDF 提取并保留证据链。 |
| `/api/v1/stock_fnd/consensus-details` | `financial_data_only` | — | `report_rc`(有权限) | 否 | report_rc 覆盖 A 股卖方盈利预测，不覆盖该合同的港股、美股全集。 |
| `/api/v1/stock_fnd/consensus-stats` | `financial_data_only` | — | `report_rc`(有权限) | 否 | 可聚合 A 股 report_rc，但无法完整覆盖港股、美股一致预期统计。 |
| `/api/v1/stock_fnd/controlling-shareholder` | `tushare_announcement_parse` | `anns_d`(无权限) | — | 否 | Tushare 没有等价结构化表，但可从 anns_d 官方公告 PDF 提取并保留证据链。 |
| `/api/v1/stock_fnd/delisting-info` | `tushare_announcement_parse` | `anns_d`(无权限) | — | 否 | Tushare 没有等价结构化表，但可从 anns_d 官方公告 PDF 提取并保留证据链。 |
| `/api/v1/stock_fnd/depository-receipt` | `financial_data_only` | — | `us_basic`(有权限) | 否 | Tushare 基础证券表没有完整存托凭证转换关系与比例历史。 |
| `/api/v1/stock_fnd/dividend-details` | `financial_data_only` | — | `dividend`(有权限) | 否 | dividend 仅覆盖 A 股，缺少港股和美股合同范围。 |
| `/api/v1/stock_fnd/dividend-record` | `financial_data_only` | — | `dividend`(有权限) | 否 | dividend 仅覆盖 A 股，缺少港股和美股除权除息事件。 |
| `/api/v1/stock_fnd/employee-ownership-plan` | `tushare_announcement_parse` | `anns_d`(无权限) | — | 否 | Tushare 没有等价结构化表，但可从 anns_d 官方公告 PDF 提取并保留证据链。 |
| `/api/v1/stock_fnd/equity-structure` | `financial_data_only` | — | `daily_basic`(有权限), `hk_daily_adj`(无权限) | 否 | 在已审计的 Tushare 契约中没有覆盖完整合同的结构化、可确定性派生或公告来源。 |
| `/api/v1/stock_fnd/executive-compensation` | `financial_data_only` | — | `stk_rewards`(有权限) | 否 | stk_rewards 仅覆盖 A 股，缺少港股高管薪酬与持股。 |
| `/api/v1/stock_fnd/free-float` | `financial_data_only` | — | `daily_basic`(有权限), `hk_daily_adj`(无权限) | 否 | 在已审计的 Tushare 契约中没有覆盖完整合同的结构化、可确定性派生或公告来源。 |
| `/api/v1/stock_fnd/fund-raising-usage` | `tushare_announcement_parse` | `anns_d`(无权限) | — | 否 | Tushare 没有等价结构化表，但可从 anns_d 官方公告 PDF 提取并保留证据链。 |
| `/api/v1/stock_fnd/growth-rates-acc` | `tushare_direct` | `fina_indicator`(有权限), `hk_fina_indicator`(无权限), `us_fina_indicator`(无权限) | — | 否 | Tushare 有覆盖该完整业务事实的结构化接口；仍需统一字段、代码、日期和单位。 |
| `/api/v1/stock_fnd/growth-rates-quarter` | `tushare_derived` | `income`(有权限), `cashflow`(有权限), `fina_indicator`(有权限), `hk_income`(无权限), `hk_cashflow`(无权限), `hk_fina_indicator`(无权限), `us_income`(无权限), `us_cashflow`(无权限), `us_fina_indicator`(无权限) | — | 否 | 可由所列 Tushare 结构化数据确定性计算；公式、权重与 as-of 规则必须版本化。 |
| `/api/v1/stock_fnd/guarantee-events` | `tushare_announcement_parse` | `anns_d`(无权限) | — | 否 | Tushare 没有等价结构化表，但可从 anns_d 官方公告 PDF 提取并保留证据链。 |
| `/api/v1/stock_fnd/guarantee-stats` | `tushare_announcement_parse` | `anns_d`(无权限) | — | 否 | Tushare 没有等价结构化表，但可从 anns_d 官方公告 PDF 提取并保留证据链。 |
| `/api/v1/stock_fnd/hk-intermediary-holdings` | `tushare_direct` | `ccass_hold`(有权限), `ccass_hold_detail`(有权限) | — | 是 | Tushare 有覆盖该完整业务事实的结构化接口；仍需统一字段、代码、日期和单位。 |
| `/api/v1/stock_fnd/holder-count` | `financial_data_only` | — | `stk_holdernumber`(有权限) | 否 | stk_holdernumber 只有股东总户数，缺少 A/B/H/CDR 分类型户数。 |
| `/api/v1/stock_fnd/holding-stats` | `tushare_derived` | `top10_holders`(有权限), `top10_floatholders`(有权限), `fund_portfolio`(有权限) | — | 是 | 可由所列 Tushare 结构化数据确定性计算；公式、权重与 as-of 规则必须版本化。 |
| `/api/v1/stock_fnd/holding-subsidiaries` | `tushare_announcement_parse` | `anns_d`(无权限) | — | 否 | Tushare 没有等价结构化表，但可从 anns_d 官方公告 PDF 提取并保留证据链。 |
| `/api/v1/stock_fnd/income-cashflow-acc` | `tushare_direct` | `income`(有权限), `cashflow`(有权限), `hk_income`(无权限), `hk_cashflow`(无权限), `us_income`(无权限), `us_cashflow`(无权限) | — | 否 | Tushare 有覆盖该完整业务事实的结构化接口；仍需统一字段、代码、日期和单位。 |
| `/api/v1/stock_fnd/income-cashflow-single` | `tushare_derived` | `income`(有权限), `cashflow`(有权限), `hk_income`(无权限), `hk_cashflow`(无权限), `us_income`(无权限), `us_cashflow`(无权限) | — | 否 | 可由所列 Tushare 结构化数据确定性计算；公式、权重与 as-of 规则必须版本化。 |
| `/api/v1/stock_fnd/industry-classification` | `financial_data_only` | — | `stock_basic`(有权限), `hk_basic`(有权限), `us_basic`(有权限), `index_classify`(有权限) | 否 | Tushare 可给基础行业和 A 股申万层级，缺少 A/H/US 多标准一至四级分类全集。 |
| `/api/v1/stock_fnd/investor-relations` | `tushare_direct` | `stk_surv`(有权限) | — | 是 | Tushare 有覆盖该完整业务事实的结构化接口；仍需统一字段、代码、日期和单位。 |
| `/api/v1/stock_fnd/ipo-primary` | `financial_data_only` | — | `new_share`(有权限) | 否 | new_share 仅覆盖 A 股，缺少港股和美股 IPO 合同字段。 |
| `/api/v1/stock_fnd/ipo-quote-details` | `tushare_announcement_parse` | `anns_d`(无权限) | — | 否 | Tushare 没有等价结构化表，但可从 anns_d 官方公告 PDF 提取并保留证据链。 |
| `/api/v1/stock_fnd/ipo-winning-numbers` | `tushare_announcement_parse` | `anns_d`(无权限) | — | 否 | Tushare 没有等价结构化表，但可从 anns_d 官方公告 PDF 提取并保留证据链。 |
| `/api/v1/stock_fnd/listing-rules` | `financial_data_only` | — | — | 否 | Tushare 没有港股收市竞价、卖空、市调机制等规则快照。 |
| `/api/v1/stock_fnd/litigation-arbitration` | `tushare_announcement_parse` | `anns_d`(无权限) | — | 否 | Tushare 没有等价结构化表，但可从 anns_d 官方公告 PDF 提取并保留证据链。 |
| `/api/v1/stock_fnd/main-business-business` | `financial_data_only` | — | — | 否 | 在已审计的 Tushare 契约中没有覆盖完整合同的结构化、可确定性派生或公告来源。 |
| `/api/v1/stock_fnd/main-business-industry` | `tushare_derived` | `fina_mainbz`(有权限) | — | 是 | 可由所列 Tushare 结构化数据确定性计算；公式、权重与 as-of 规则必须版本化。 |
| `/api/v1/stock_fnd/main-business-product` | `financial_data_only` | — | `fina_mainbz`(有权限) | 否 | 在已审计的 Tushare 契约中没有覆盖完整合同的结构化、可确定性派生或公告来源。 |
| `/api/v1/stock_fnd/main-business-region` | `financial_data_only` | — | `fina_mainbz`(有权限) | 否 | 在已审计的 Tushare 契约中没有覆盖完整合同的结构化、可确定性派生或公告来源。 |
| `/api/v1/stock_fnd/metrics-ttm` | `tushare_derived` | `income`(有权限), `cashflow`(有权限), `daily_basic`(有权限), `us_income`(无权限), `us_cashflow`(无权限), `us_daily_adj`(无权限) | — | 否 | 可由所列 Tushare 结构化数据确定性计算；公式、权重与 as-of 规则必须版本化。 |
| `/api/v1/stock_fnd/performance-forecast` | `tushare_direct` | `forecast`(有权限) | — | 是 | Tushare 有覆盖该完整业务事实的结构化接口；仍需统一字段、代码、日期和单位。 |
| `/api/v1/stock_fnd/prelim-acc` | `tushare_direct` | `express`(有权限) | — | 是 | Tushare 有覆盖该完整业务事实的结构化接口；仍需统一字段、代码、日期和单位。 |
| `/api/v1/stock_fnd/prelim-balance` | `tushare_direct` | `express`(有权限) | — | 是 | Tushare 有覆盖该完整业务事实的结构化接口；仍需统一字段、代码、日期和单位。 |
| `/api/v1/stock_fnd/prelim-quarter` | `tushare_derived` | `express`(有权限) | — | 是 | 可由所列 Tushare 结构化数据确定性计算；公式、权重与 as-of 规则必须版本化。 |
| `/api/v1/stock_fnd/rating-summary` | `financial_data_only` | — | `report_rc`(有权限) | 否 | 在已审计的 Tushare 契约中没有覆盖完整合同的结构化、可确定性派生或公告来源。 |
| `/api/v1/stock_fnd/regulatory-penalties` | `tushare_announcement_parse` | `anns_d`(无权限) | — | 否 | Tushare 没有等价结构化表，但可从 anns_d 官方公告 PDF 提取并保留证据链。 |
| `/api/v1/stock_fnd/related-party-transactions` | `tushare_announcement_parse` | `anns_d`(无权限) | — | 否 | Tushare 没有等价结构化表，但可从 anns_d 官方公告 PDF 提取并保留证据链。 |
| `/api/v1/stock_fnd/restricted-release-calendar` | `financial_data_only` | — | `share_float`(有权限) | 否 | share_float 仅覆盖 A 股，缺少港股限售解禁。 |
| `/api/v1/stock_fnd/review-process` | `tushare_announcement_parse` | `anns_d`(无权限) | — | 否 | Tushare 没有等价结构化表，但可从 anns_d 官方公告 PDF 提取并保留证据链。 |
| `/api/v1/stock_fnd/risk-factor-csi300` | `tushare_derived` | `daily`(有权限), `index_daily`(有权限) | — | 是 | 可由所列 Tushare 结构化数据确定性计算；公式、权重与 as-of 规则必须版本化。 |
| `/api/v1/stock_fnd/risk-factor-csi500` | `tushare_derived` | `daily`(有权限), `index_daily`(有权限) | — | 是 | 可由所列 Tushare 结构化数据确定性计算；公式、权重与 as-of 规则必须版本化。 |
| `/api/v1/stock_fnd/risk-factor-sh000001` | `tushare_derived` | `daily`(有权限), `index_daily`(有权限) | — | 是 | 可由所列 Tushare 结构化数据确定性计算；公式、权重与 as-of 规则必须版本化。 |
| `/api/v1/stock_fnd/risk-factor-sw` | `tushare_derived` | `daily`(有权限), `sw_daily`(有权限), `index_member_all`(有权限) | — | 是 | 可由所列 Tushare 结构化数据确定性计算；公式、权重与 as-of 规则必须版本化。 |
| `/api/v1/stock_fnd/seo-placement-details` | `tushare_announcement_parse` | `anns_d`(无权限) | — | 否 | Tushare 没有等价结构化表，但可从 anns_d 官方公告 PDF 提取并保留证据链。 |
| `/api/v1/stock_fnd/shareholder-commitment` | `tushare_announcement_parse` | `anns_d`(无权限) | — | 否 | Tushare 没有等价结构化表，但可从 anns_d 官方公告 PDF 提取并保留证据链。 |
| `/api/v1/stock_fnd/shareholder-list` | `financial_data_only` | — | `top10_holders`(有权限), `top10_floatholders`(有权限) | 否 | Tushare 十大股东表仅覆盖 A 股，缺少港股和美股。 |
| `/api/v1/stock_fnd/shareholder-meeting` | `tushare_announcement_parse` | `anns_d`(无权限) | — | 否 | Tushare 没有等价结构化表，但可从 anns_d 官方公告 PDF 提取并保留证据链。 |
| `/api/v1/stock_fnd/specialty-metrics-period` | `financial_data_only` | — | `fina_indicator`(有权限), `hk_fina_indicator`(无权限), `us_fina_indicator`(无权限) | 否 | Tushare 财务指标不能完整覆盖 A/H/US 银行、保险、券商特色口径。 |
| `/api/v1/stock_fnd/specialty-metrics-point` | `financial_data_only` | — | — | 否 | Tushare 缺少内含价值、风险贴现率等跨市场保险特色时点指标。 |
| `/api/v1/stock_fnd/stock-basic-info` | `financial_data_only` | — | `stock_basic`(有权限), `stock_company`(有权限), `hk_basic`(有权限), `us_basic`(有权限) | 否 | Tushare 的港股/美股列表缺少成立日期、注册资本、法人等完整公司档案字段。 |
| `/api/v1/stock_fnd/stock-rel-fund-holdings-top` | `tushare_derived` | `fund_portfolio`(有权限) | — | 是 | 可由所列 Tushare 结构化数据确定性计算；公式、权重与 as-of 规则必须版本化。 |
| `/api/v1/stock_fnd/style-classification` | `tushare_derived` | `daily`(有权限), `daily_basic`(有权限), `fina_indicator`(有权限) | — | 是 | 可由所列 Tushare 结构化数据确定性计算；公式、权重与 as-of 规则必须版本化。 |
| `/api/v1/stock_fnd/takeover-offers` | `tushare_announcement_parse` | `anns_d`(无权限) | — | 否 | Tushare 没有等价结构化表，但可从 anns_d 官方公告 PDF 提取并保留证据链。 |
| `/api/v1/stock_fnd/target-price` | `financial_data_only` | — | `report_rc`(有权限) | 否 | report_rc 可提供部分 A 股研报价格信息，缺少统一 A/H/US 目标价统计。 |
| `/api/v1/stock_fnd/tender-offers` | `tushare_announcement_parse` | `anns_d`(无权限) | — | 否 | Tushare 没有等价结构化表，但可从 anns_d 官方公告 PDF 提取并保留证据链。 |
| `/api/v1/stock_fnd/yield-factor` | `tushare_derived` | `daily`(有权限), `adj_factor`(有权限) | — | 是 | 可由所列 Tushare 结构化数据确定性计算；公式、权重与 as-of 规则必须版本化。 |
| `/api/v1/stock_sh_equity/freeze-pledge` | `financial_data_only` | — | `pledge_detail`(有权限), `pledge_stat`(有权限) | 否 | pledge_detail/pledge_stat 覆盖质押，但没有完整股权冻结事件。 |
| `/api/v1/us_stock/adr-ratio-changes` | `financial_data_only` | — | — | 否 | 在已审计的 Tushare 契约中没有覆盖完整合同的结构化、可确定性派生或公告来源。 |
| `/api/v1/us_stock/capital-events` | `financial_data_only` | — | — | 否 | 在已审计的 Tushare 契约中没有覆盖完整合同的结构化、可确定性派生或公告来源。 |
| `/api/v1/us_stock/company-ownership` | `financial_data_only` | — | — | 否 | 在已审计的 Tushare 契约中没有覆盖完整合同的结构化、可确定性派生或公告来源。 |
| `/api/v1/us_stock/concept-components` | `financial_data_only` | — | — | 否 | 在已审计的 Tushare 契约中没有覆盖完整合同的结构化、可确定性派生或公告来源。 |
| `/api/v1/us_stock/dividends` | `financial_data_only` | — | — | 否 | 在已审计的 Tushare 契约中没有覆盖完整合同的结构化、可确定性派生或公告来源。 |
| `/api/v1/us_stock/equity-structure` | `financial_data_only` | — | `us_daily_adj`(无权限) | 否 | us_daily_adj 有总股本和流通股本，但缺少内部人持股及公司/证券双层股本。 |
| `/api/v1/us_stock/ratings` | `financial_data_only` | — | — | 否 | 在已审计的 Tushare 契约中没有覆盖完整合同的结构化、可确定性派生或公告来源。 |
| `/api/v1/us_stock/security-markings` | `financial_data_only` | — | `us_basic`(有权限) | 否 | us_basic 缺少完整 ADR 比例、首次发行和双重上市标识。 |
| `/api/v1/us_stock/target-price` | `financial_data_only` | — | — | 否 | 在已审计的 Tushare 契约中没有覆盖完整合同的结构化、可确定性派生或公告来源。 |
| `/api/v2/info/news/article` | `financial_data_only` | — | `news`(无权限), `major_news`(有权限) | 否 | Tushare 有正文，但不能用 Financial Data 的 feed_id 读取同一篇内容。 |
| `/api/v2/info/news/search_evidence` | `financial_data_only` | — | `news`(无权限), `major_news`(有权限), `anns_d`(无权限) | 否 | Tushare 有新闻/公告子集，缺少相同去重、标签和 feed_id 证据合同。 |

## Tushare 244 条契约反向映射

| Tushare 契约 | 作为完整等价输入 | 仅局部重叠 | 无 Financial Data 对应 |
|---:|---:|---:|---:|
| 244 | 88 | 48 | 108 |

| Tushare 接口 | 标题 | Token 权限 | 可安全采集 | 映射状态 | 完整等价 Financial 路由 | 局部重叠 Financial 路由 |
|---|---|---|---|---|---|---|
| `adj_factor` | 复权因子 | 有权限 | 是 | `full_equivalence_input` | `/api/v1/stock/tech-indicators`, `/api/v1/stock/tech-patterns`, `/api/v1/stock_fnd/yield-factor` | — |
| `anns_d` | 上市公司全量公告 | 无权限 | 否 | `full_equivalence_input` | `/api/v1/stock/change-plan`, `/api/v1/stock_fnd/actual-controller`, `/api/v1/stock_fnd/asset-restructuring`, `/api/v1/stock_fnd/concert-parties`, `/api/v1/stock_fnd/controlling-shareholder`, `/api/v1/stock_fnd/delisting-info`, `/api/v1/stock_fnd/employee-ownership-plan`, `/api/v1/stock_fnd/fund-raising-usage`, `/api/v1/stock_fnd/guarantee-events`, `/api/v1/stock_fnd/guarantee-stats`, `/api/v1/stock_fnd/holding-subsidiaries`, `/api/v1/stock_fnd/ipo-quote-details`, `/api/v1/stock_fnd/ipo-winning-numbers`, `/api/v1/stock_fnd/litigation-arbitration`, `/api/v1/stock_fnd/regulatory-penalties`, `/api/v1/stock_fnd/related-party-transactions`, `/api/v1/stock_fnd/review-process`, `/api/v1/stock_fnd/seo-placement-details`, `/api/v1/stock_fnd/shareholder-commitment`, `/api/v1/stock_fnd/shareholder-meeting`, `/api/v1/stock_fnd/takeover-offers`, `/api/v1/stock_fnd/tender-offers` | `/api/v1/info/announcements`, `/api/v2/info/news/search_evidence` |
| `bak_basic` | 股票历史列表（历史每天股票列表） | 有权限 | 是 | `no_financial_data_counterpart` | — | — |
| `bak_daily` | 备用行情 | 有权限 | 是 | `no_financial_data_counterpart` | — | — |
| `balancesheet` | 资产负债表 | 有权限 | 是 | `full_equivalence_input` | `/api/v1/index_fnd/index-fnd-financial-ratios`, `/api/v1/index_fnd/index-fnd-financial-ratios-single`, `/api/v1/index_fnd/index-fnd-financial-statement`, `/api/v1/sector/sector-financial-cumulative`, `/api/v1/sector/sector-financial-point`, `/api/v1/stock_fnd/balance-sheet` | — |
| `balancesheet_vip` | 当前官方目录未列出 | 有权限 | 是 | `no_financial_data_counterpart` | — | — |
| `bc_bestotcqt` | 柜台流通式债券最优报价 | 有权限 | 是 | `no_financial_data_counterpart` | — | — |
| `bc_otcqt` | 柜台流通式债券报价 | 有权限 | 是 | `no_financial_data_counterpart` | — | — |
| `block_trade` | 大宗交易 | 有权限 | 是 | `full_equivalence_input` | `/api/v1/stock/block-trading-details` | — |
| `bond_blk` | 债券大宗交易 | 有权限 | 是 | `no_financial_data_counterpart` | — | — |
| `bond_blk_detail` | 大宗交易明细 | 有权限 | 是 | `no_financial_data_counterpart` | — | — |
| `broker_recommend` | 券商每月荐股 | 有权限 | 是 | `full_equivalence_input` | `/api/v1/stock_fnd/broker-golden-stocks` | — |
| `bse_mapping` | 北交所新旧代码对照表 | 有权限 | 是 | `partial_overlap_only` | — | `/api/v1/common/entity_relationship` |
| `cashflow` | 现金流量表 | 有权限 | 是 | `full_equivalence_input` | `/api/v1/index_fnd/index-fnd-financial-statement`, `/api/v1/sector/sector-financial-cumulative`, `/api/v1/sector/sector-financial-quarterly`, `/api/v1/stock_fnd/growth-rates-quarter`, `/api/v1/stock_fnd/income-cashflow-acc`, `/api/v1/stock_fnd/income-cashflow-single`, `/api/v1/stock_fnd/metrics-ttm` | — |
| `cashflow_vip` | 当前官方目录未列出 | 有权限 | 是 | `no_financial_data_counterpart` | — | — |
| `cb_basic` | 可转债基本信息 | 有权限 | 是 | `no_financial_data_counterpart` | — | — |
| `cb_call` | 可转债赎回信息 | 有权限 | 是 | `no_financial_data_counterpart` | — | — |
| `cb_daily` | 可转债行情 | 有权限 | 是 | `no_financial_data_counterpart` | — | — |
| `cb_factor_pro` | 可转债技术因子(专业版) | 有权限 | 是 | `no_financial_data_counterpart` | — | — |
| `cb_issue` | 可转债发行 | 有权限 | 是 | `no_financial_data_counterpart` | — | — |
| `cb_price_chg` | 可转债转股价变动 | 无权限 | 否 | `no_financial_data_counterpart` | — | — |
| `cb_rate` | 可转债票面利率 | 有权限 | 是 | `no_financial_data_counterpart` | — | — |
| `cb_rating` | 获取可转债评级历史记录 | 有权限 | 是 | `no_financial_data_counterpart` | — | — |
| `cb_share` | 可转债转股结果 | 有权限 | 是 | `no_financial_data_counterpart` | — | — |
| `ccass_hold` | 当前官方目录未列出 | 有权限 | 是 | `full_equivalence_input` | `/api/v1/stock_fnd/hk-intermediary-holdings` | `/api/v1/hk_stock/high-shareholding-concentration` |
| `ccass_hold_detail` | 当前官方目录未列出 | 有权限 | 是 | `full_equivalence_input` | `/api/v1/stock_fnd/hk-intermediary-holdings` | `/api/v1/hk_stock/high-shareholding-concentration` |
| `cctv_news` | 新闻联播 | 无权限 | 否 | `no_financial_data_counterpart` | — | — |
| `ci_daily` | 中信行业指数行情 | 有权限 | 是 | `no_financial_data_counterpart` | — | — |
| `ci_index_member` | 中信行业成分 | 有权限 | 是 | `no_financial_data_counterpart` | — | — |
| `cn_cpi` | 居民消费价格指数 | 有权限 | 是 | `partial_overlap_only` | — | `/api/v1/macro/data-query`, `/api/v1/macro/meta-search` |
| `cn_gdp` | GDP数据 | 有权限 | 是 | `partial_overlap_only` | — | `/api/v1/macro/data-query`, `/api/v1/macro/meta-search` |
| `cn_m` | 货币供应量 | 有权限 | 是 | `partial_overlap_only` | — | `/api/v1/macro/data-query`, `/api/v1/macro/meta-search` |
| `cn_pmi` | 采购经理人指数 | 有权限 | 是 | `partial_overlap_only` | — | `/api/v1/macro/data-query`, `/api/v1/macro/meta-search` |
| `cn_ppi` | 工业生产者出厂价格指数 | 有权限 | 是 | `partial_overlap_only` | — | `/api/v1/macro/data-query`, `/api/v1/macro/meta-search` |
| `cn_schedule` | 中国经济数据发布日程 | 有权限 | 是 | `partial_overlap_only` | — | `/api/v1/macro/meta-search` |
| `cyq_chips` | 每日筹码分布 | 有权限 | 是 | `no_financial_data_counterpart` | — | — |
| `cyq_perf` | 每日筹码及胜率 | 有权限 | 是 | `no_financial_data_counterpart` | — | — |
| `daily` | A股日线行情 | 有权限 | 是 | `full_equivalence_input` | `/api/v1/quote/kline-batch`, `/api/v1/stock/tech-indicators`, `/api/v1/stock/tech-patterns`, `/api/v1/stock_fnd/risk-factor-csi300`, `/api/v1/stock_fnd/risk-factor-csi500`, `/api/v1/stock_fnd/risk-factor-sh000001`, `/api/v1/stock_fnd/risk-factor-sw`, `/api/v1/stock_fnd/style-classification`, `/api/v1/stock_fnd/yield-factor` | `/api/v1/onecode/query` |
| `daily_basic` | 每日指标 | 有权限 | 是 | `full_equivalence_input` | `/api/v1/sector/sector-valuation`, `/api/v1/stock/daily-valuation-indicators`, `/api/v1/stock_fnd/metrics-ttm`, `/api/v1/stock_fnd/style-classification` | `/api/v1/onecode/query`, `/api/v1/quote/derived-snapshot`, `/api/v1/stock_fnd/equity-structure`, `/api/v1/stock_fnd/free-float` |
| `daily_info` | 市场交易统计 | 有权限 | 是 | `no_financial_data_counterpart` | — | — |
| `dc_concept` | 题材库 | 有权限 | 是 | `no_financial_data_counterpart` | — | — |
| `dc_concept_cons` | 题材成分 | 有权限 | 是 | `no_financial_data_counterpart` | — | — |
| `dc_daily` | 概念板块行情 | 有权限 | 是 | `no_financial_data_counterpart` | — | — |
| `dc_hot` | DC热榜 | 有权限 | 是 | `partial_overlap_only` | — | `/api/v1/altdata/hot-plate-rank`, `/api/v1/altdata/hot-stock-rank` |
| `dc_index` | 概念板块 | 有权限 | 是 | `full_equivalence_input` | `/api/v1/sector/plate-list` | — |
| `dc_member` | 板块成分 | 有权限 | 是 | `full_equivalence_input` | `/api/v1/fund/plate-fund-relevancy`, `/api/v1/sector/plate-component`, `/api/v1/sector/plate-fund-relevancy`, `/api/v1/sector/sector-capital-flow`, `/api/v1/sector/sector-financial-cumulative`, `/api/v1/sector/sector-financial-point`, `/api/v1/sector/sector-financial-quarterly`, `/api/v1/sector/sector-valuation`, `/api/v1/stock/component-list-belonged` | — |
| `disclosure_date` | 财报披露计划 | 有权限 | 是 | `no_financial_data_counterpart` | — | — |
| `dividend` | 分红送股 | 有权限 | 是 | `partial_overlap_only` | — | `/api/v1/stock_fnd/dividend-details`, `/api/v1/stock_fnd/dividend-record` |
| `eco_cal` | 财经日历 | 有权限 | 是 | `no_financial_data_counterpart` | — | — |
| `etf_basic` | ETF基础信息 | 有权限 | 是 | `no_financial_data_counterpart` | — | — |
| `etf_index` | ETF基准指数列表 | 有权限 | 是 | `no_financial_data_counterpart` | — | — |
| `etf_mins` | ETF历史分钟行情 | 无权限 | 否 | `partial_overlap_only` | — | `/api/v1/quote/basic-snapshot` |
| `etf_sh_cons` | ETF每日持仓组合(沪市） | 有权限 | 是 | `no_financial_data_counterpart` | — | — |
| `etf_share_size` | ETF份额规模 | 有权限 | 是 | `no_financial_data_counterpart` | — | — |
| `etf_sz_cons` | ETF每日持仓组合(深市） | 有权限 | 是 | `no_financial_data_counterpart` | — | — |
| `express` | 业绩快报 | 有权限 | 是 | `full_equivalence_input` | `/api/v1/stock_fnd/prelim-acc`, `/api/v1/stock_fnd/prelim-balance`, `/api/v1/stock_fnd/prelim-quarter` | — |
| `express_vip` | 当前官方目录未列出 | 有权限 | 是 | `no_financial_data_counterpart` | — | — |
| `factor_list` | 因子列表 | 无权限 | 否 | `partial_overlap_only` | — | `/api/v1/onecode/recall` |
| `factor_value` | 因子值 | 有权限 | 是 | `partial_overlap_only` | — | `/api/v1/onecode/query` |
| `fina_audit` | 财务审计意见 | 有权限 | 是 | `no_financial_data_counterpart` | — | — |
| `fina_indicator` | 财务指标数据 | 有权限 | 是 | `full_equivalence_input` | `/api/v1/index_fnd/index-fnd-financial-ratios`, `/api/v1/index_fnd/index-fnd-financial-ratios-single`, `/api/v1/sector/sector-financial-cumulative`, `/api/v1/sector/sector-financial-point`, `/api/v1/sector/sector-financial-quarterly`, `/api/v1/stock_fnd/growth-rates-acc`, `/api/v1/stock_fnd/growth-rates-quarter`, `/api/v1/stock_fnd/style-classification` | `/api/v1/stock_fnd/specialty-metrics-period` |
| `fina_indicator_vip` | 当前官方目录未列出 | 有权限 | 是 | `no_financial_data_counterpart` | — | — |
| `fina_mainbz` | 主营业务构成 | 有权限 | 是 | `full_equivalence_input` | `/api/v1/stock_fnd/main-business-industry` | `/api/v1/stock_fnd/main-business-product`, `/api/v1/stock_fnd/main-business-region` |
| `fina_mainbz_vip` | 当前官方目录未列出 | 有权限 | 是 | `no_financial_data_counterpart` | — | — |
| `forecast` | 业绩预告 | 有权限 | 是 | `full_equivalence_input` | `/api/v1/stock_fnd/performance-forecast` | — |
| `forecast_vip` | 当前官方目录未列出 | 有权限 | 是 | `no_financial_data_counterpart` | — | — |
| `ft_limit` | 期货合约涨跌停价格（盘前） | 有权限 | 是 | `no_financial_data_counterpart` | — | — |
| `ft_mins` | 期货历史分钟行情 | 无权限 | 否 | `no_financial_data_counterpart` | — | — |
| `fund_adj` | 基金复权因子 | 有权限 | 是 | `partial_overlap_only` | — | `/api/v1/fund/share-split` |
| `fund_basic` | 公募基金列表 | 有权限 | 是 | `full_equivalence_input` | `/api/v1/common/symbol-by-cond`, `/api/v1/fund/fund-company-info`, `/api/v1/fund/yield-rank` | `/api/v1/fund/fund-archive`, `/api/v1/fund/fund-charge-rate`, `/api/v1/fund/trade-limit` |
| `fund_company` | 公募基金公司 | 有权限 | 是 | `full_equivalence_input` | `/api/v1/fund/fund-company-info` | — |
| `fund_daily` | ETF日线行情 | 有权限 | 是 | `full_equivalence_input` | `/api/v1/fund/yield-rank`, `/api/v1/fund_derived/benchmark-excess`, `/api/v1/fund_derived/risk-return`, `/api/v1/quote/kline-batch` | `/api/v1/fund/net-value` |
| `fund_div` | 公募基金分红 | 有权限 | 是 | `full_equivalence_input` | `/api/v1/fund/dividend` | — |
| `fund_factor_pro` | 场内基金技术因子(专业版) | 有权限 | 是 | `no_financial_data_counterpart` | — | — |
| `fund_manager` | 基金经理 | 有权限 | 是 | `full_equivalence_input` | `/api/v1/fund/fund-manager` | — |
| `fund_nav` | 公募基金净值 | 有权限 | 是 | `full_equivalence_input` | `/api/v1/fund/yield-rank`, `/api/v1/fund_derived/benchmark-excess`, `/api/v1/fund_derived/risk-return` | `/api/v1/fund/asset-allocation`, `/api/v1/fund/net-value`, `/api/v1/onecode/query` |
| `fund_portfolio` | 公募基金持仓数据 | 有权限 | 是 | `full_equivalence_input` | `/api/v1/fund/invest-industry`, `/api/v1/fund/plate-fund-relevancy`, `/api/v1/fund/stock-portfolio`, `/api/v1/sector/plate-fund-relevancy`, `/api/v1/stock_fnd/holding-stats`, `/api/v1/stock_fnd/stock-rel-fund-holdings-top` | `/api/v1/fund/asset-allocation` |
| `fund_share` | 基金规模数据 | 有权限 | 是 | `full_equivalence_input` | `/api/v1/fund/fund-company-info` | — |
| `fut_basic` | 期货合约信息表 | 有权限 | 是 | `no_financial_data_counterpart` | — | — |
| `fut_daily` | 期货日线行情 | 有权限 | 是 | `no_financial_data_counterpart` | — | — |
| `fut_holding` | 每日成交持仓排名 | 有权限 | 是 | `no_financial_data_counterpart` | — | — |
| `fut_index_daily` | 南华期货指数日线行情 | 有权限 | 是 | `no_financial_data_counterpart` | — | — |
| `fut_mapping` | 期货主力与连续合约 | 有权限 | 是 | `no_financial_data_counterpart` | — | — |
| `fut_settle` | 结算参数 | 有权限 | 是 | `no_financial_data_counterpart` | — | — |
| `fut_trade_cal` | 交易日历 | 有权限 | 是 | `partial_overlap_only` | — | `/api/v1/common/trading-day` |
| `fut_weekly_detail` | 期货主要品种交易周报 | 有权限 | 是 | `no_financial_data_counterpart` | — | — |
| `fut_weekly_monthly` | 期货周/月线行情(每日更新) | 有权限 | 是 | `no_financial_data_counterpart` | — | — |
| `fut_wsr` | 仓单日报 | 有权限 | 是 | `no_financial_data_counterpart` | — | — |
| `fx_daily` | 外汇日线行情 | 有权限 | 是 | `no_financial_data_counterpart` | — | — |
| `fx_obasic` | 外汇基础信息（海外） | 有权限 | 是 | `no_financial_data_counterpart` | — | — |
| `ggt_daily` | 当前官方目录未列出 | 有权限 | 是 | `full_equivalence_input` | `/api/v1/stock/sc-trade` | — |
| `ggt_top10` | 当前官方目录未列出 | 有权限 | 是 | `full_equivalence_input` | `/api/v1/stock/sc-activitie` | — |
| `gz_index` | 广州民间借贷利率 | 有权限 | 是 | `no_financial_data_counterpart` | — | — |
| `hibor` | Hibor利率 | 有权限 | 是 | `no_financial_data_counterpart` | — | — |
| `hk_adjfactor` | 港股复权因子 | 无权限 | 否 | `no_financial_data_counterpart` | — | — |
| `hk_balancesheet` | 港股资产负债表 | 无权限 | 否 | `full_equivalence_input` | `/api/v1/stock_fnd/balance-sheet` | — |
| `hk_basic` | 港股列表 | 有权限 | 是 | `full_equivalence_input` | `/api/v1/common/symbol-by-cond` | `/api/v1/stock_fnd/industry-classification`, `/api/v1/stock_fnd/stock-basic-info` |
| `hk_cashflow` | 港股现金流量表 | 无权限 | 否 | `full_equivalence_input` | `/api/v1/stock_fnd/growth-rates-quarter`, `/api/v1/stock_fnd/income-cashflow-acc`, `/api/v1/stock_fnd/income-cashflow-single` | — |
| `hk_daily` | 港股行情 | 有权限 | 是 | `no_financial_data_counterpart` | — | — |
| `hk_daily_adj` | 港股复权行情 | 无权限 | 否 | `full_equivalence_input` | `/api/v1/quote/kline-batch`, `/api/v1/stock/tech-indicators` | `/api/v1/hk_stock/equity-structure`, `/api/v1/hk_stock/free-float`, `/api/v1/quote/derived-snapshot`, `/api/v1/stock_fnd/equity-structure`, `/api/v1/stock_fnd/free-float` |
| `hk_fina_indicator` | 港股财务指标数据 | 无权限 | 否 | `full_equivalence_input` | `/api/v1/stock_fnd/growth-rates-acc`, `/api/v1/stock_fnd/growth-rates-quarter` | `/api/v1/stock_fnd/specialty-metrics-period` |
| `hk_hold` | 当前官方目录未列出 | 有权限 | 是 | `full_equivalence_input` | `/api/v1/stock/sh-hold-stat` | — |
| `hk_income` | 港股利润表 | 无权限 | 否 | `full_equivalence_input` | `/api/v1/stock_fnd/growth-rates-quarter`, `/api/v1/stock_fnd/income-cashflow-acc`, `/api/v1/stock_fnd/income-cashflow-single` | — |
| `hk_mins` | 港股分钟行情 | 无权限 | 否 | `partial_overlap_only` | — | `/api/v1/quote/basic-snapshot` |
| `hk_tradecal` | 港股交易日历 | 有权限 | 是 | `partial_overlap_only` | — | `/api/v1/common/trading-day`, `/api/v1/common/trading-state` |
| `hm_detail` | 游资每日明细 | 无权限 | 否 | `no_financial_data_counterpart` | — | — |
| `hm_list` | 游资名录 | 有权限 | 是 | `no_financial_data_counterpart` | — | — |
| `hsgt_top10` | 沪深股通十大成交股 | 有权限 | 是 | `full_equivalence_input` | `/api/v1/stock/sc-activitie` | — |
| `idx_anns` | 指数公告 | 有权限 | 是 | `no_financial_data_counterpart` | — | — |
| `idx_factor_pro` | 指数技术因子(专业版) | 有权限 | 是 | `no_financial_data_counterpart` | — | — |
| `idx_mins` | 指数历史分钟行情 | 无权限 | 否 | `partial_overlap_only` | — | `/api/v1/quote/basic-snapshot` |
| `income` | 利润表 | 有权限 | 是 | `full_equivalence_input` | `/api/v1/index_fnd/index-fnd-financial-ratios`, `/api/v1/index_fnd/index-fnd-financial-ratios-single`, `/api/v1/index_fnd/index-fnd-financial-statement`, `/api/v1/sector/sector-financial-cumulative`, `/api/v1/sector/sector-financial-quarterly`, `/api/v1/stock_fnd/growth-rates-quarter`, `/api/v1/stock_fnd/income-cashflow-acc`, `/api/v1/stock_fnd/income-cashflow-single`, `/api/v1/stock_fnd/metrics-ttm` | — |
| `income_vip` | 当前官方目录未列出 | 有权限 | 是 | `no_financial_data_counterpart` | — | — |
| `index_basic` | 指数基本信息 | 有权限 | 是 | `full_equivalence_input` | `/api/v1/common/symbol-by-cond`, `/api/v1/index_fnd/index-profile-basic-info` | — |
| `index_classify` | 申万行业分类 | 有权限 | 是 | `full_equivalence_input` | `/api/v1/sector/plate-list` | `/api/v1/stock_fnd/industry-classification` |
| `index_daily` | 指数日线行情 | 有权限 | 是 | `full_equivalence_input` | `/api/v1/fund_derived/benchmark-excess`, `/api/v1/fund_derived/risk-return`, `/api/v1/quote/kline-batch`, `/api/v1/stock_fnd/risk-factor-csi300`, `/api/v1/stock_fnd/risk-factor-csi500`, `/api/v1/stock_fnd/risk-factor-sh000001` | `/api/v1/onecode/query` |
| `index_dailybasic` | 大盘指数每日指标 | 有权限 | 是 | `full_equivalence_input` | `/api/v1/sector/sector-valuation` | — |
| `index_global` | 国际指数 | 有权限 | 是 | `no_financial_data_counterpart` | — | — |
| `index_member_all` | 申万行业成分构成(分级) | 有权限 | 是 | `full_equivalence_input` | `/api/v1/fund/invest-industry`, `/api/v1/index_fnd/index-fnd-estimates-summary`, `/api/v1/index_fnd/index-fnd-financial-ratios`, `/api/v1/index_fnd/index-fnd-financial-ratios-single`, `/api/v1/index_fnd/index-fnd-financial-statement`, `/api/v1/sector/plate-component`, `/api/v1/sector/sector-capital-flow`, `/api/v1/sector/sector-financial-cumulative`, `/api/v1/sector/sector-financial-point`, `/api/v1/sector/sector-financial-quarterly`, `/api/v1/sector/sector-valuation`, `/api/v1/stock/component-list-belonged`, `/api/v1/stock_fnd/risk-factor-sw` | `/api/v1/index_fnd/index-constituents-list-weight`, `/api/v1/stock/stock-index-constituents-list` |
| `index_monthly` | 指数月线行情 | 有权限 | 是 | `full_equivalence_input` | `/api/v1/quote/kline-batch` | — |
| `index_weekly` | 指数周线行情 | 有权限 | 是 | `full_equivalence_input` | `/api/v1/quote/kline-batch` | — |
| `index_weight` | 指数成分和权重 | 有权限 | 是 | `full_equivalence_input` | `/api/v1/index_fnd/index-fnd-estimates-summary`, `/api/v1/index_fnd/index-fnd-financial-ratios`, `/api/v1/index_fnd/index-fnd-financial-ratios-single`, `/api/v1/index_fnd/index-fnd-financial-statement` | `/api/v1/index_fnd/index-constituents-list-weight`, `/api/v1/stock/stock-index-constituents-list` |
| `irm_qa_sh` | 上证E互动 | 无权限 | 否 | `no_financial_data_counterpart` | — | — |
| `irm_qa_sz` | 深证互动易 | 无权限 | 否 | `no_financial_data_counterpart` | — | — |
| `kpl_concept_cons` | 开盘啦题材成分 | 有权限 | 是 | `no_financial_data_counterpart` | — | — |
| `kpl_list` | 开盘啦榜单数据 | 有权限 | 是 | `no_financial_data_counterpart` | — | — |
| `libor` | Libor拆借利率 | 有权限 | 是 | `no_financial_data_counterpart` | — | — |
| `limit_cpt_list` | 最强板块统计 | 有权限 | 是 | `partial_overlap_only` | — | `/api/v1/altdata/hot-plate-rank` |
| `limit_list_d` | 涨跌停列表（新） | 有权限 | 是 | `no_financial_data_counterpart` | — | — |
| `limit_list_ths` | 涨跌停榜单（同花顺） | 有权限 | 是 | `no_financial_data_counterpart` | — | — |
| `limit_step` | 连板天梯 | 有权限 | 是 | `no_financial_data_counterpart` | — | — |
| `major_news` | 新闻通讯 | 有权限 | 是 | `partial_overlap_only` | — | `/api/v1/info/news-global-search`, `/api/v1/info/tag/category`, `/api/v1/info/tag/query`, `/api/v2/info/news/article`, `/api/v2/info/news/search_evidence` |
| `margin` | 融资融券交易汇总 | 有权限 | 是 | `no_financial_data_counterpart` | — | — |
| `margin_detail` | 融资融券交易明细 | 有权限 | 是 | `full_equivalence_input` | `/api/v1/sector/sector-capital-flow` | `/api/v1/stock/market-detail` |
| `margin_secs` | 融资融券标的（盘前更新） | 有权限 | 是 | `no_financial_data_counterpart` | — | — |
| `mkt_idx_bmk` | 公募基金业绩基准库 | 有权限 | 是 | `full_equivalence_input` | `/api/v1/fund_derived/benchmark-excess` | — |
| `monetary_policy` | 央行货币政策执行报告 | 无权限 | 否 | `no_financial_data_counterpart` | — | — |
| `moneyflow` | 个股资金流向 | 有权限 | 是 | `full_equivalence_input` | `/api/v1/quote/capital-flow-range` | — |
| `moneyflow_cnt_ths` | 同花顺概念板块资金流向（THS） | 有权限 | 是 | `no_financial_data_counterpart` | — | — |
| `moneyflow_dc` | 个股资金流向（DC） | 有权限 | 是 | `full_equivalence_input` | `/api/v1/quote/capital-flow-range` | — |
| `moneyflow_hsgt` | 当前官方目录未列出 | 有权限 | 是 | `full_equivalence_input` | `/api/v1/stock/sc-trade` | — |
| `moneyflow_ind_dc` | 东财概念及行业板块资金流向（DC） | 有权限 | 是 | `full_equivalence_input` | `/api/v1/quote/capital-flow-range` | — |
| `moneyflow_ind_ths` | 同花顺行业资金流向（THS） | 有权限 | 是 | `full_equivalence_input` | `/api/v1/quote/capital-flow-range` | — |
| `moneyflow_mkt_dc` | 大盘资金流向（DC） | 有权限 | 是 | `full_equivalence_input` | `/api/v1/quote/capital-flow-range` | — |
| `moneyflow_ths` | 个股资金流向（THS） | 有权限 | 是 | `full_equivalence_input` | `/api/v1/quote/capital-flow-range` | — |
| `monthly` | 月线行情 | 有权限 | 是 | `full_equivalence_input` | `/api/v1/quote/kline-batch` | — |
| `namechange` | 股票曾用名 | 有权限 | 是 | `partial_overlap_only` | — | `/api/v1/common/entity_relationship` |
| `new_share` | IPO新股列表 | 有权限 | 是 | `partial_overlap_only` | — | `/api/v1/stock_fnd/ipo-primary` |
| `news` | 新闻快讯 | 无权限 | 否 | `partial_overlap_only` | — | `/api/v1/info/news-global-search`, `/api/v1/info/tag/category`, `/api/v1/info/tag/query`, `/api/v2/info/news/article`, `/api/v2/info/news/search_evidence` |
| `npr` | 国家政策法规库 | 无权限 | 否 | `no_financial_data_counterpart` | — | — |
| `opt_basic` | 期权合约信息 | 有权限 | 是 | `no_financial_data_counterpart` | — | — |
| `opt_daily` | 期权日线行情 | 有权限 | 是 | `no_financial_data_counterpart` | — | — |
| `opt_mins` | 期权历史分钟行情 | 无权限 | 否 | `no_financial_data_counterpart` | — | — |
| `p_delete` | 自选股组合删除 | 有权限 | 否 | `no_financial_data_counterpart` | — | — |
| `p_get` | 自选股组合查询 | 有权限 | 是 | `no_financial_data_counterpart` | — | — |
| `p_list` | 自选股组合查询 | 有权限 | 是 | `no_financial_data_counterpart` | — | — |
| `p_save` | 自选股组合保存 | 有权限 | 否 | `no_financial_data_counterpart` | — | — |
| `pledge_detail` | 股权质押明细 | 有权限 | 是 | `partial_overlap_only` | — | `/api/v1/stock_sh_equity/freeze-pledge` |
| `pledge_stat` | 股权质押统计数据 | 有权限 | 是 | `partial_overlap_only` | — | `/api/v1/stock_sh_equity/freeze-pledge` |
| `pro_bar` | A股复权行情 | 依底层接口权限 | 否 | `no_financial_data_counterpart` | — | — |
| `repo_daily` | 债券回购日行情 | 有权限 | 是 | `no_financial_data_counterpart` | — | — |
| `report_rc` | 卖方盈利预测数据 | 有权限 | 是 | `full_equivalence_input` | `/api/v1/index_fnd/index-fnd-estimates-summary` | `/api/v1/stock_fnd/consensus-details`, `/api/v1/stock_fnd/consensus-stats`, `/api/v1/stock_fnd/rating-summary`, `/api/v1/stock_fnd/target-price` |
| `repurchase` | 股票回购 | 有权限 | 是 | `full_equivalence_input` | `/api/v1/stock_fnd/buyback-plans` | — |
| `research_report` | 券商研究报告 | 无权限 | 否 | `full_equivalence_input` | `/api/v1/info/research-reports` | — |
| `rt_etf_sz_iopv` | ETF实时参考 | 无权限 | 否 | `partial_overlap_only` | — | `/api/v1/quote/basic-snapshot` |
| `rt_fut_min` | 期货实时分钟行情 | 无权限 | 否 | `no_financial_data_counterpart` | — | — |
| `rt_fut_min_daily` | 期货实时分钟行情 | 无权限 | 否 | `no_financial_data_counterpart` | — | — |
| `rt_hk_k` | 港股实时日线 | 有权限 | 是 | `partial_overlap_only` | — | `/api/v1/common/trading-state`, `/api/v1/quote/basic-snapshot` |
| `rt_idx_k` | 交易所指数实时日线 | 无权限 | 否 | `partial_overlap_only` | — | `/api/v1/common/trading-state`, `/api/v1/quote/basic-snapshot` |
| `rt_idx_min` | A股实时分钟 | 无权限 | 否 | `no_financial_data_counterpart` | — | — |
| `rt_idx_min_daily` | A股实时分钟 | 无权限 | 否 | `no_financial_data_counterpart` | — | — |
| `rt_sw_k` | 申万实时行情 | 无权限 | 否 | `partial_overlap_only` | — | `/api/v1/quote/basic-snapshot` |
| `sf_month` | 社融数据（月度） | 有权限 | 是 | `partial_overlap_only` | — | `/api/v1/macro/data-query` |
| `sge_basic` | 黄金现货基础信息 | 有权限 | 是 | `full_equivalence_input` | `/api/v1/common/symbol-by-cond` | — |
| `sge_daily` | 现货黄金日行情 | 有权限 | 是 | `full_equivalence_input` | `/api/v1/quote/kline-batch` | — |
| `share_float` | 限售股解禁 | 有权限 | 是 | `partial_overlap_only` | — | `/api/v1/stock_fnd/restricted-release-calendar` |
| `shibor` | Shibor利率数据 | 有权限 | 是 | `partial_overlap_only` | — | `/api/v1/macro/data-query` |
| `shibor_lpr` | LPR贷款基础利率 | 有权限 | 是 | `partial_overlap_only` | — | `/api/v1/macro/data-query` |
| `shibor_quote` | Shibor报价数据 | 有权限 | 是 | `no_financial_data_counterpart` | — | — |
| `slb_len` | 转融资交易汇总 | 有权限 | 是 | `no_financial_data_counterpart` | — | — |
| `slb_len_mm` | 做市借券交易汇总 | 有权限 | 是 | `no_financial_data_counterpart` | — | — |
| `slb_sec` | 转融券交易汇总 | 有权限 | 是 | `no_financial_data_counterpart` | — | — |
| `slb_sec_detail` | 转融券交易明细 | 有权限 | 是 | `no_financial_data_counterpart` | — | — |
| `st` | ST风险警示板股票 | 有权限 | 是 | `full_equivalence_input` | `/api/v1/stock/risk-alerts` | — |
| `stk_account` | 股票账户开户数据 | 有权限 | 是 | `no_financial_data_counterpart` | — | — |
| `stk_account_old` | 股票账户开户数据（旧） | 接口无效/已下线 | 否 | `no_financial_data_counterpart` | — | — |
| `stk_ah_comparison` | AH股比价 | 有权限 | 是 | `partial_overlap_only` | — | `/api/v1/common/entity_relationship` |
| `stk_alert` | 交易所重点提示证券 | 有权限 | 是 | `full_equivalence_input` | `/api/v1/stock/risk-alerts` | — |
| `stk_auction` | 当日集合竞价 | 有权限 | 是 | `partial_overlap_only` | — | `/api/v1/quote/auction-snapshot` |
| `stk_auction_c` | 股票收盘集合竞价数据 | 有权限 | 是 | `partial_overlap_only` | — | `/api/v1/quote/auction-snapshot` |
| `stk_auction_o` | 股票开盘集合竞价数据 | 有权限 | 是 | `partial_overlap_only` | — | `/api/v1/quote/auction-snapshot` |
| `stk_factor` | 股票技术因子（量化因子） | 有权限 | 是 | `full_equivalence_input` | `/api/v1/stock/tech-indicators` | — |
| `stk_factor_pro` | 股票技术面因子(专业版) | 有权限 | 是 | `full_equivalence_input` | `/api/v1/stock/tech-indicators`, `/api/v1/stock/tech-patterns` | — |
| `stk_high_shock` | 个股严重异常波动 | 有权限 | 是 | `full_equivalence_input` | `/api/v1/stock/tra-variant` | — |
| `stk_holdernumber` | 股东人数 | 有权限 | 是 | `partial_overlap_only` | — | `/api/v1/stock_fnd/holder-count` |
| `stk_holdertrade` | 股东增减持 | 有权限 | 是 | `no_financial_data_counterpart` | — | — |
| `stk_limit` | 每日涨跌停价格 | 有权限 | 是 | `no_financial_data_counterpart` | — | — |
| `stk_managers` | 上市公司管理层 | 有权限 | 是 | `no_financial_data_counterpart` | — | — |
| `stk_mins` | 股票历史分钟行情 | 有权限（当前限频） | 是 | `partial_overlap_only` | — | `/api/v1/quote/basic-snapshot` |
| `stk_nineturn` | 神奇九转指标 | 有权限 | 是 | `full_equivalence_input` | `/api/v1/stock/tech-patterns` | — |
| `stk_premarket` | 股本情况（盘前） | 无权限 | 否 | `no_financial_data_counterpart` | — | — |
| `stk_rewards` | 管理层薪酬和持股 | 有权限 | 是 | `partial_overlap_only` | — | `/api/v1/stock_fnd/executive-compensation` |
| `stk_shock` | 个股异常波动 | 有权限 | 是 | `full_equivalence_input` | `/api/v1/stock/tra-variant` | — |
| `stk_surv` | 机构调研表 | 有权限 | 是 | `full_equivalence_input` | `/api/v1/stock_fnd/investor-relations` | — |
| `stk_week_month_adj` | 股票周/月线行情(复权--每日更新) | 有权限 | 是 | `no_financial_data_counterpart` | — | — |
| `stk_weekly_monthly` | 股票周/月线行情(每日更新) | 有权限 | 是 | `full_equivalence_input` | `/api/v1/quote/kline-batch` | — |
| `stock_basic` | 股票基础信息 | 有权限 | 是 | `full_equivalence_input` | `/api/v1/common/symbol-by-cond`, `/api/v1/fund/invest-industry` | `/api/v1/stock_fnd/industry-classification`, `/api/v1/stock_fnd/stock-basic-info` |
| `stock_company` | 上市公司基本信息 | 有权限 | 是 | `partial_overlap_only` | — | `/api/v1/stock_fnd/stock-basic-info` |
| `stock_hsgt` | 沪深港通股票列表 | 有权限 | 是 | `full_equivalence_input` | `/api/v1/stock/sh-hold-stat` | — |
| `stock_st` | ST股票列表 | 有权限 | 是 | `full_equivalence_input` | `/api/v1/stock/risk-alerts` | — |
| `suspend_d` | 每日停复牌信息 | 有权限 | 是 | `full_equivalence_input` | `/api/v1/stock/suspend-resumption` | — |
| `sw_daily` | 申万行业日线行情 | 有权限 | 是 | `full_equivalence_input` | `/api/v1/stock_fnd/risk-factor-sw` | — |
| `sw_mins` | SW指数历史分钟 | 无权限 | 否 | `no_financial_data_counterpart` | — | — |
| `sz_daily_info` | 深圳市场每日交易概况 | 有权限 | 是 | `no_financial_data_counterpart` | — | — |
| `tdx_daily` | TDX板块行情 | 有权限 | 是 | `full_equivalence_input` | `/api/v1/quote/kline-batch` | — |
| `tdx_index` | TDX板块信息 | 有权限 | 是 | `full_equivalence_input` | `/api/v1/sector/plate-list` | — |
| `tdx_member` | TDX板块成分 | 有权限 | 是 | `full_equivalence_input` | `/api/v1/fund/plate-fund-relevancy`, `/api/v1/sector/plate-component`, `/api/v1/sector/plate-fund-relevancy`, `/api/v1/stock/component-list-belonged` | — |
| `ths_daily` | 板块指数行情 | 有权限 | 是 | `no_financial_data_counterpart` | — | — |
| `ths_hot` | THS热榜 | 有权限 | 是 | `partial_overlap_only` | — | `/api/v1/altdata/hot-plate-rank`, `/api/v1/altdata/hot-stock-rank` |
| `ths_index` | 概念和行业指数 | 有权限 | 是 | `full_equivalence_input` | `/api/v1/sector/plate-list` | — |
| `ths_member` | 概念板块成分 | 有权限 | 是 | `full_equivalence_input` | `/api/v1/fund/plate-fund-relevancy`, `/api/v1/sector/plate-component`, `/api/v1/sector/plate-fund-relevancy`, `/api/v1/sector/sector-capital-flow`, `/api/v1/sector/sector-financial-cumulative`, `/api/v1/sector/sector-financial-point`, `/api/v1/sector/sector-financial-quarterly`, `/api/v1/sector/sector-valuation`, `/api/v1/stock/component-list-belonged` | — |
| `top10_cb_holders` | 可转债十大持有人 | 有权限 | 是 | `no_financial_data_counterpart` | — | — |
| `top10_floatholders` | 前十大流通股东 | 有权限 | 是 | `full_equivalence_input` | `/api/v1/stock_fnd/holding-stats` | `/api/v1/stock_fnd/shareholder-list` |
| `top10_holders` | 前十大股东 | 有权限 | 是 | `full_equivalence_input` | `/api/v1/stock_fnd/holding-stats` | `/api/v1/stock_fnd/shareholder-list` |
| `top_inst` | 龙虎榜机构明细 | 有权限 | 是 | `full_equivalence_input` | `/api/v1/stock/tra-variant` | — |
| `top_list` | 龙虎榜每日明细 | 有权限 | 是 | `full_equivalence_input` | `/api/v1/stock/tra-variant` | — |
| `trade_cal` | 交易日历 | 有权限 | 是 | `partial_overlap_only` | — | `/api/v1/common/trading-day`, `/api/v1/common/trading-state` |
| `us_adjfactor` | 美股复权因子 | 无权限 | 否 | `no_financial_data_counterpart` | — | — |
| `us_balancesheet` | 美股资产负债表 | 无权限 | 否 | `full_equivalence_input` | `/api/v1/stock_fnd/balance-sheet` | — |
| `us_basic` | 美股列表 | 有权限 | 是 | `full_equivalence_input` | `/api/v1/common/symbol-by-cond` | `/api/v1/stock_fnd/depository-receipt`, `/api/v1/stock_fnd/industry-classification`, `/api/v1/stock_fnd/stock-basic-info`, `/api/v1/us_stock/security-markings` |
| `us_cashflow` | 美股现金流量表 | 无权限 | 否 | `full_equivalence_input` | `/api/v1/stock_fnd/growth-rates-quarter`, `/api/v1/stock_fnd/income-cashflow-acc`, `/api/v1/stock_fnd/income-cashflow-single`, `/api/v1/stock_fnd/metrics-ttm` | — |
| `us_daily` | 美股行情 | 无权限 | 否 | `no_financial_data_counterpart` | — | — |
| `us_daily_adj` | 美股复权行情 | 无权限 | 否 | `full_equivalence_input` | `/api/v1/quote/kline-batch`, `/api/v1/stock/tech-indicators`, `/api/v1/stock_fnd/metrics-ttm` | `/api/v1/quote/derived-snapshot`, `/api/v1/us_stock/equity-structure` |
| `us_fina_indicator` | 美股财务指标数据 | 无权限 | 否 | `full_equivalence_input` | `/api/v1/stock_fnd/growth-rates-acc`, `/api/v1/stock_fnd/growth-rates-quarter` | `/api/v1/stock_fnd/specialty-metrics-period` |
| `us_income` | 美股利润表 | 无权限 | 否 | `full_equivalence_input` | `/api/v1/stock_fnd/growth-rates-quarter`, `/api/v1/stock_fnd/income-cashflow-acc`, `/api/v1/stock_fnd/income-cashflow-single`, `/api/v1/stock_fnd/metrics-ttm` | — |
| `us_tbr` | 短期国债利率 | 有权限 | 是 | `partial_overlap_only` | — | `/api/v1/macro/data-query` |
| `us_tltr` | 国债长期利率 | 有权限 | 是 | `partial_overlap_only` | — | `/api/v1/macro/data-query` |
| `us_tradecal` | 美股交易日历 | 有权限 | 是 | `partial_overlap_only` | — | `/api/v1/common/trading-day`, `/api/v1/common/trading-state` |
| `us_trltr` | 国债实际长期利率平均值 | 有权限 | 是 | `partial_overlap_only` | — | `/api/v1/macro/data-query` |
| `us_trycr` | 国债实际收益率曲线利率 | 有权限 | 是 | `partial_overlap_only` | — | `/api/v1/macro/data-query` |
| `us_tycr` | 国债收益率曲线利率（日频） | 有权限 | 是 | `partial_overlap_only` | — | `/api/v1/macro/data-query` |
| `weekly` | 周线行情 | 有权限 | 是 | `full_equivalence_input` | `/api/v1/quote/kline-batch` | — |
| `wz_index` | 温州民间借贷利率 | 有权限 | 是 | `no_financial_data_counterpart` | — | — |
| `yc_cb` | 国债收益率曲线 | 无权限 | 否 | `no_financial_data_counterpart` | — | — |

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
| `/api/v1/macro/data-query` | `local_overlap_adapter_pending` | 否 | `local_dataset_or_explicit_provider_gateway` | `cn_cpi`, `cn_gdp`, `cn_m`, `cn_pmi`, `cn_ppi`, `sf_month`, `shibor`, `cn_lpr`, `libor`, `hibor`, `us_tbr`, `us_tltr`, `us_trltr`, `us_trycr`, `us_tycr` | `adapter_required` |
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
