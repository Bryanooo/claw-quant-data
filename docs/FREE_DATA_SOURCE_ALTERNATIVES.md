# Tushare 无权限接口的免费替代源评估

更新时间：2026-09-20。当前 Token 对契约中原标记无权限的 39 个接口做了真实复核：
38 个仍明确拒绝；`us_daily` 已可访问，但限频为 1 次/分钟，应从“无权限”迁移为
“有权限（限频）”。Tushare 官方把新闻、公告、分钟行情等列为独立权限，并不存在
可用于生产全量采集的免费档。

“有免费候选”不等于可以直接替换。下表同时评估字段等价性、历史深度、稳定 API、
自动化许可与可验收性。项目只会把通过样本校验、限频、断点续传和来源条款审查的来源
接入正式初始化。

| Tushare 接口 | 免费候选 | 覆盖结论 | 建议 |
|---|---|---|---|
| `anns_d` | 上交所、深交所、北交所公开公告页；AKShare `stock_notice_report` / `stock_individual_notice_report` | **可部分替代**。元数据和链接可取，PDF 正文、历史分页与站点变更需自行治理；没有发现交易所统一、稳定、公开承诺的全市场 REST 契约 | 做第二数据源 PoC，先覆盖公告元数据/PDF 哈希，不宣称与 Tushare 全量公告完全等价 |
| `cctv_news` | 央视公开节目页；AKShare `news_cctv` | **可替代主要字段**，但属于网页适配而非有 SLA 的官方数据 API | 可接入，必须保留来源 URL、页面哈希和解析失败告警 |
| `news` | 当前已有 `major_news`；AKShare `stock_news_em`；GDELT | **不能等价替代**。AKShare 个股新闻只有近期/最多 100 条；GDELT 免费开放但偏全球新闻、正文和 A 股实体绑定不完整 | `major_news` 做历史底座；GDELT/东财只作增量补充，快讯全量仍需商业源 |
| `research_report` | AKShare `stock_research_report_em`（东财研报和 PDF 链接） | **可部分替代**，覆盖自 2017 年左右的个股研报，但字段、去重和版权需核查 | 可以优先 PoC；正式入库只保存许可范围内的元数据、链接与可审计摘要 |
| `factor_list` | 基于本系统行情、财务和资金数据本地计算 | **无需购买等价接口**。能自行定义并版本化公开公式因子，但不能复制供应商专有因子 | 放到未来因子/回测系统，保存公式版本、输入快照、去极值和中性化口径 |
| `irm_qa_sh`, `irm_qa_sz` | 上证 e 互动、深交所互动易/巨潮；AKShare `stock_sns_sseinfo`、`stock_irm_cninfo` | **可部分替代**，公开问答可获取，历史上限和网页契约稳定性需实测 | 适合新增免费采集器，按问题 ID 去重并日常增量复核 |
| `monetary_policy` | 中国人民银行公开的货币政策执行报告 PDF | **内容可替代，结构化接口不可替代** | 下载官方原文、文档哈希和发布日期；结构化摘要作为派生层并保留引用页码 |
| `npr` | 国家法律法规数据库、国家行政法规库、中国政府网政策文件 | **内容可替代，统一 API 不可替代** | 仅采官方公开页面/下载，按文号、效力状态和修订链去重；先做待办 |
| `yc_cb` | 中国债券信息网/财政部国债收益率曲线公开查询与年度下载 | **研究用途可替代**，但衍生产品、商业再分发需另行申请 | 可新增官方来源采集器，优先年度下载+每日增量，保留曲线名称和使用限制 |
| `stk_mins`（当前仅 2 次/日）, `idx_mins`, `etf_mins` | BaoStock 5/15/30/60 分钟 A 股；AKShare 新浪/东财分钟接口 | **部分替代**。BaoStock 不含指数分钟且仅近年；AKShare 1 分钟历史窗口较短、无 SLA | 适合个人研究的受限股票池，不可据此宣称全市场 1 分钟全历史完成 |
| `ft_mins`, `opt_mins`, `sw_mins`, `hk_mins` | AKShare 对应公开网页行情适配 | **只有非等价候选**，历史深度、字段和稳定性不统一 | 保持待办；确有研究需求再逐品种验收，不能混成一个“免费分钟源” |
| `rt_fut_min`, `rt_fut_min_daily`, `rt_idx_k`, `rt_idx_min`, `rt_idx_min_daily`, `rt_sw_k`, `rt_etf_sz_iopv` | AKShare/新浪/东财公开行情页 | **只适合展示或降级查询**，无稳定性与再分发保证，通常缺少完整盘口和纠错 | 不进入核心历史恢复；实时研究需要正规授权数据源 |
| `hm_detail` | AKShare 东财龙虎榜 `stock_lhb_detail_em` 等 | **部分替代**。龙虎榜事实可取，“游资席位标签”属于供应商加工数据，无法免费等价恢复 | 采龙虎榜原始席位，自建透明标签；不复制供应商主观标签 |
| `cb_price_chg` | 公司公告、交易所公告、AKShare 可转债资料 | **可派生但成本高**，需要从历次转股价调整公告建立事件链 | 依赖公告源完成后派生；当前没有发现稳定免费等价 API |
| `stk_premarket` | 公告、股本变动和前一交易日标准数据 | **只能部分推导**，无法免费稳定获得官方“盘前当日股本”全量快照 | 若盘前估值是刚需则购买；否则使用带滞后标记的最近已确认股本 |
| `hk_adjfactor`, `hk_daily_adj`, `hk_income`, `hk_balancesheet`, `hk_cashflow`, `hk_fina_indicator` | 港交所公开披露；AKShare 等聚合 | **部分替代**，公告公开但跨公司标准化财务和可靠复权因子不是免费统一 API | 当前 A 股优先，港股研究立项时单独验证或购买正规源 |
| `us_adjfactor`, `us_daily_adj`, `us_income`, `us_balancesheet`, `us_cashflow`, `us_fina_indicator` | SEC EDGAR submissions/companyfacts 免费 REST 与 bulk ZIP；免费行情聚合 | **财务可高质量替代，价格/复权不能由 SEC 替代** | 财务优先接 SEC 官方 API；美股复权行情另选有明确许可的数据源 |

## 已确认不应寻找“免费等价物”的范围

- 真正的 Level-2 盘口、逐笔身份、订单失衡和冲击成本：交易所将其作为授权行情产品；
  面向个人显示的免费行情不等于允许批量落库、回放和再分发的数据接口。
- 全市场、多年、低延迟的新闻快讯全文：公开网页或 GDELT 可以补充事件发现，但不能
  同时保证国内财经覆盖、完整正文、历史深度、低延迟和稳定授权。
- 港美股统一复权因子和标准化财务：可以拼接公开来源，但若要与当前 A 股服务同等
  完整、可审计和可恢复，工程与口径成本通常高于购买一个合规数据源。

## 推荐实施顺序

1. 先完成已有权限的 `major_news` 全历史和现有 Tushare 数据补采；
2. 免费源第一批：公告元数据/PDF、互动平台、央行报告、中债收益率、SEC 财务；
3. 第二批：东财研报、央视新闻、龙虎榜，并对网页变化建立契约测试；
4. 分钟与实时行情只服务明确的小范围研究需求；Level-2 和完整快讯没有免费等价方案，
   需要时再选择商业授权。

## 依据

- [Tushare 积分与独立权限说明](https://tushare.pro/document/1?doc_id=290)
- [Tushare `major_news` 契约与 400 行上限](https://tushare.pro/document/2?doc_id=195)
- [AKShare 股票数据接口文档](https://akshare.akfamily.xyz/data/stock/stock.html)
- [BaoStock 官方网站](https://www.baostock.com/)
- [GDELT 免费开放数据说明](https://www.gdeltproject.org/data.html)
- [上交所信息网络 Level-2 产品说明](https://www.sseinfo.com/services/assortment/market/hqywwd/wdcpsms/c/10782128/)
- [中国债券信息网收益率曲线](https://yield.chinabond.com.cn/)
- [SEC EDGAR 免费数据 API](https://www.sec.gov/search-filings/edgar-application-programming-interfaces)
- [国家法律法规数据库](https://flk.npc.gov.cn/search)
- [国家行政法规库](https://xzfg.moj.gov.cn/)
