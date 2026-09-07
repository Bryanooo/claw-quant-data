# Tushare 接口、Token 权限与 claw-quant 实现矩阵

生成日期：2026-08-29

- 官方叶子文档：231
- 官方接口记录：232
- 唯一 api_name：231
- claw-quant 扩展/历史接口：13
- Token 权限：{"依底层接口权限": 1, "接口无效/已下线": 1, "无权限": 40, "有权限": 188, "有权限（当前限频）": 1}
- claw-quant 实现：{"已实现": 86, "已实现（balancesheet_vip）": 1, "已实现（cashflow_vip）": 1, "已实现（express_vip）": 1, "已实现（fina_indicator_vip）": 1, "已实现（fina_mainbz_vip）": 1, "已实现（forecast_vip）": 1, "已实现（income_vip）": 1, "已实现（契约通用采集器：原始层+强类型标准表）": 94, "已封装（写接口，不进入采集调度）": 2, "未实现": 42}

判定规则：返回码 0 为有权限；40203 结合消息区分无权限与当前限频；
50101 表示权限层已通过、请求进入参数校验，因此判为有权限；40101 表示接口名已无效或接口已下线。
保存/删除类接口只发送空参数请求，避免产生账户写入。

## 分类汇总（按唯一 api_name）

| 一级分类 | 接口数 | Token可访问 | 无权限 | 条件/失效 | claw-quant已实现 | 未实现 |
|---|---:|---:|---:|---:|---:|---:|
| ETF专题 | 10 | 8 | 2 | 0 | 8 | 2 |
| 债券专题 | 17 | 15 | 2 | 0 | 15 | 2 |
| 公募基金 | 9 | 9 | 0 | 0 | 9 | 0 |
| 外汇数据 | 2 | 2 | 0 | 0 | 2 | 0 |
| 大模型语料 | 9 | 1 | 8 | 0 | 1 | 8 |
| 宏观经济 | 19 | 19 | 0 | 0 | 19 | 0 |
| 指数专题 | 21 | 15 | 6 | 0 | 15 | 6 |
| 期权数据 | 3 | 2 | 1 | 0 | 2 | 1 |
| 期货数据 | 14 | 11 | 3 | 0 | 11 | 3 |
| 港股数据 | 11 | 3 | 8 | 0 | 3 | 8 |
| 现货数据 | 2 | 2 | 0 | 0 | 2 | 0 |
| 美股数据 | 9 | 2 | 7 | 0 | 2 | 7 |
| 股票数据 | 99 | 95 | 2 | 2 | 95 | 4 |
| 自选组合 | 4 | 4 | 0 | 0 | 4 | 0 |
| 量化因子库 | 2 | 1 | 1 | 0 | 1 | 1 |

## 完整矩阵

| 来源 | 分类 | 文档 | api_name | Token权限 | claw-quant | 返回码 | 官方链接 |
|---|---|---|---|---|---|---:|---|
| Tushare官方目录 | ETF专题 | ETF份额规模 | `etf_share_size` | 有权限 | 已实现（契约通用采集器：原始层+强类型标准表） | 0 | [doc 408](https://tushare.pro/document/2?doc_id=408) |
| Tushare官方目录 | ETF专题 | ETF历史分钟行情 | `etf_mins` | 无权限 | 未实现 | 40203 | [doc 387](https://tushare.pro/document/2?doc_id=387) |
| Tushare官方目录 | ETF专题 | ETF基础信息 | `etf_basic` | 有权限 | 已实现（契约通用采集器：原始层+强类型标准表） | 0 | [doc 385](https://tushare.pro/document/2?doc_id=385) |
| Tushare官方目录 | ETF专题 | 基金复权因子 | `fund_adj` | 有权限 | 已实现（契约通用采集器：原始层+强类型标准表） | 0 | [doc 199](https://tushare.pro/document/2?doc_id=199) |
| Tushare官方目录 | ETF专题 | ETF实时参考 | `rt_etf_sz_iopv` | 无权限 | 未实现 | 40203 | [doc 454](https://tushare.pro/document/2?doc_id=454) |
| Tushare官方目录 | ETF专题 | ETF日线行情 | `fund_daily` | 有权限 | 已实现（契约通用采集器：原始层+强类型标准表） | 0 | [doc 127](https://tushare.pro/document/2?doc_id=127) |
| Tushare官方目录 | ETF专题 | ETF基准指数列表 | `etf_index` | 有权限 | 已实现（契约通用采集器：原始层+强类型标准表） | 0 | [doc 386](https://tushare.pro/document/2?doc_id=386) |
| Tushare官方目录 | ETF专题 | 指数公告 | `idx_anns` | 有权限 | 已实现（契约通用采集器：原始层+强类型标准表） | 0 | [doc 460](https://tushare.pro/document/2?doc_id=460) |
| Tushare官方目录 | ETF专题 | ETF每日持仓组合(沪市） | `etf_sh_cons` | 有权限 | 已实现（契约通用采集器：原始层+强类型标准表） | 0 | [doc 471](https://tushare.pro/document/2?doc_id=471) |
| Tushare官方目录 | ETF专题 | ETF每日持仓组合(深市） | `etf_sz_cons` | 有权限 | 已实现（契约通用采集器：原始层+强类型标准表） | 0 | [doc 472](https://tushare.pro/document/2?doc_id=472) |
| Tushare官方目录 | 债券专题 | 债券回购日行情 | `repo_daily` | 有权限 | 已实现（契约通用采集器：原始层+强类型标准表） | 0 | [doc 256](https://tushare.pro/document/2?doc_id=256) |
| Tushare官方目录 | 债券专题 | 财经日历 | `eco_cal` | 有权限 | 已实现（契约通用采集器：原始层+强类型标准表） | 0 | [doc 233](https://tushare.pro/document/2?doc_id=233) |
| Tushare官方目录 | 债券专题 | 获取可转债评级历史记录 | `cb_rating` | 有权限 | 已实现（契约通用采集器：原始层+强类型标准表） | 0 | [doc 458](https://tushare.pro/document/2?doc_id=458) |
| Tushare官方目录 | 债券专题 | 可转债十大持有人 | `top10_cb_holders` | 有权限 | 已实现（契约通用采集器：原始层+强类型标准表） | 0 | [doc 459](https://tushare.pro/document/2?doc_id=459) |
| Tushare官方目录 | 债券专题 | 可转债发行 | `cb_issue` | 有权限 | 已实现（契约通用采集器：原始层+强类型标准表） | 0 | [doc 186](https://tushare.pro/document/2?doc_id=186) |
| Tushare官方目录 | 债券专题 | 可转债基本信息 | `cb_basic` | 有权限 | 已实现（契约通用采集器：原始层+强类型标准表） | 0 | [doc 185](https://tushare.pro/document/2?doc_id=185) |
| Tushare官方目录 | 债券专题 | 可转债技术因子(专业版) | `cb_factor_pro` | 有权限 | 已实现（契约通用采集器：原始层+强类型标准表） | 0 | [doc 392](https://tushare.pro/document/2?doc_id=392) |
| Tushare官方目录 | 债券专题 | 可转债票面利率 | `cb_rate` | 有权限 | 已实现（契约通用采集器：原始层+强类型标准表） | 0 | [doc 305](https://tushare.pro/document/2?doc_id=305) |
| Tushare官方目录 | 债券专题 | 可转债行情 | `cb_daily` | 有权限 | 已实现（契约通用采集器：原始层+强类型标准表） | 0 | [doc 187](https://tushare.pro/document/2?doc_id=187) |
| Tushare官方目录 | 债券专题 | 可转债赎回信息 | `cb_call` | 有权限 | 已实现（契约通用采集器：原始层+强类型标准表） | 0 | [doc 269](https://tushare.pro/document/2?doc_id=269) |
| Tushare官方目录 | 债券专题 | 可转债转股价变动 | `cb_price_chg` | 无权限 | 未实现 | 40203 | [doc 246](https://tushare.pro/document/2?doc_id=246) |
| Tushare官方目录 | 债券专题 | 可转债转股结果 | `cb_share` | 有权限 | 已实现（契约通用采集器：原始层+强类型标准表） | 0 | [doc 247](https://tushare.pro/document/2?doc_id=247) |
| Tushare官方目录 | 债券专题 | 国债收益率曲线 | `yc_cb` | 无权限 | 未实现 | 40203 | [doc 201](https://tushare.pro/document/2?doc_id=201) |
| Tushare官方目录 | 债券专题 | 债券大宗交易 | `bond_blk` | 有权限 | 已实现（契约通用采集器：原始层+强类型标准表） | 0 | [doc 271](https://tushare.pro/document/2?doc_id=271) |
| Tushare官方目录 | 债券专题 | 大宗交易明细 | `bond_blk_detail` | 有权限 | 已实现（契约通用采集器：原始层+强类型标准表） | 0 | [doc 272](https://tushare.pro/document/2?doc_id=272) |
| Tushare官方目录 | 债券专题 | 柜台流通式债券报价 | `bc_otcqt` | 有权限 | 已实现（契约通用采集器：原始层+强类型标准表） | 0 | [doc 322](https://tushare.pro/document/2?doc_id=322) |
| Tushare官方目录 | 债券专题 | 柜台流通式债券最优报价 | `bc_bestotcqt` | 有权限 | 已实现（契约通用采集器：原始层+强类型标准表） | 0 | [doc 323](https://tushare.pro/document/2?doc_id=323) |
| Tushare官方目录 | 公募基金 | 公募基金业绩基准库 | `mkt_idx_bmk` | 有权限 | 已实现（契约通用采集器：原始层+强类型标准表） | 0 | [doc 462](https://tushare.pro/document/2?doc_id=462) |
| Tushare官方目录 | 公募基金 | 公募基金净值 | `fund_nav` | 有权限 | 已实现（契约通用采集器：原始层+强类型标准表） | 0 | [doc 119](https://tushare.pro/document/2?doc_id=119) |
| Tushare官方目录 | 公募基金 | 公募基金分红 | `fund_div` | 有权限 | 已实现（契约通用采集器：原始层+强类型标准表） | 0 | [doc 120](https://tushare.pro/document/2?doc_id=120) |
| Tushare官方目录 | 公募基金 | 公募基金列表 | `fund_basic` | 有权限 | 已实现（契约通用采集器：原始层+强类型标准表） | 0 | [doc 19](https://tushare.pro/document/2?doc_id=19) |
| Tushare官方目录 | 公募基金 | 场内基金技术因子(专业版) | `fund_factor_pro` | 有权限 | 已实现（契约通用采集器：原始层+强类型标准表） | 0 | [doc 359](https://tushare.pro/document/2?doc_id=359) |
| Tushare官方目录 | 公募基金 | 公募基金持仓数据 | `fund_portfolio` | 有权限 | 已实现（契约通用采集器：原始层+强类型标准表） | 0 | [doc 121](https://tushare.pro/document/2?doc_id=121) |
| Tushare官方目录 | 公募基金 | 公募基金公司 | `fund_company` | 有权限 | 已实现（契约通用采集器：原始层+强类型标准表） | 0 | [doc 118](https://tushare.pro/document/2?doc_id=118) |
| Tushare官方目录 | 公募基金 | 基金经理 | `fund_manager` | 有权限 | 已实现（契约通用采集器：原始层+强类型标准表） | 0 | [doc 208](https://tushare.pro/document/2?doc_id=208) |
| Tushare官方目录 | 公募基金 | 基金规模数据 | `fund_share` | 有权限 | 已实现（契约通用采集器：原始层+强类型标准表） | 0 | [doc 207](https://tushare.pro/document/2?doc_id=207) |
| Tushare官方目录 | 外汇数据 | 外汇基础信息（海外） | `fx_obasic` | 有权限 | 已实现 | 0 | [doc 178](https://tushare.pro/document/2?doc_id=178) |
| Tushare官方目录 | 外汇数据 | 外汇日线行情 | `fx_daily` | 有权限 | 已实现 | 0 | [doc 179](https://tushare.pro/document/2?doc_id=179) |
| Tushare官方目录 | 大模型语料 | 上市公司全量公告 | `anns_d` | 无权限 | 未实现 | 40203 | [doc 176](https://tushare.pro/document/2?doc_id=176) |
| Tushare官方目录 | 大模型语料 | 上证E互动 | `irm_qa_sh` | 无权限 | 未实现 | 40203 | [doc 366](https://tushare.pro/document/2?doc_id=366) |
| Tushare官方目录 | 大模型语料 | 券商研究报告 | `research_report` | 无权限 | 未实现 | 40203 | [doc 415](https://tushare.pro/document/2?doc_id=415) |
| Tushare官方目录 | 大模型语料 | 国家政策法规库 | `npr` | 无权限 | 未实现 | 40203 | [doc 406](https://tushare.pro/document/2?doc_id=406) |
| Tushare官方目录 | 大模型语料 | 央行货币政策执行报告 | `monetary_policy` | 无权限 | 未实现 | 40203 | [doc 465](https://tushare.pro/document/2?doc_id=465) |
| Tushare官方目录 | 大模型语料 | 新闻快讯 | `news` | 无权限 | 未实现 | 40203 | [doc 143](https://tushare.pro/document/2?doc_id=143) |
| Tushare官方目录 | 大模型语料 | 新闻联播 | `cctv_news` | 无权限 | 未实现 | 40203 | [doc 154](https://tushare.pro/document/2?doc_id=154) |
| Tushare官方目录 | 大模型语料 | 新闻通讯 | `major_news` | 有权限 | 已实现（契约通用采集器：原始层+强类型标准表） | 0 | [doc 195](https://tushare.pro/document/2?doc_id=195) |
| Tushare官方目录 | 大模型语料 | 深证互动易 | `irm_qa_sz` | 无权限 | 未实现 | 40203 | [doc 367](https://tushare.pro/document/2?doc_id=367) |
| Tushare官方目录 | 宏观经济/国内宏观 | 中国经济数据发布日程 | `cn_schedule` | 有权限 | 已实现（契约通用采集器：原始层+强类型标准表） | 0 | [doc 461](https://tushare.pro/document/2?doc_id=461) |
| Tushare官方目录 | 宏观经济/国内宏观/价格指数 | 居民消费价格指数 | `cn_cpi` | 有权限 | 已实现（契约通用采集器：原始层+强类型标准表） | 0 | [doc 228](https://tushare.pro/document/2?doc_id=228) |
| Tushare官方目录 | 宏观经济/国内宏观/价格指数 | 工业生产者出厂价格指数 | `cn_ppi` | 有权限 | 已实现（契约通用采集器：原始层+强类型标准表） | 0 | [doc 245](https://tushare.pro/document/2?doc_id=245) |
| Tushare官方目录 | 宏观经济/国内宏观/利率数据 | Hibor利率 | `hibor` | 有权限 | 已实现（契约通用采集器：原始层+强类型标准表） | 0 | [doc 153](https://tushare.pro/document/2?doc_id=153) |
| Tushare官方目录 | 宏观经济/国内宏观/利率数据 | LPR贷款基础利率 | `shibor_lpr` | 有权限 | 已实现（契约通用采集器：原始层+强类型标准表） | 0 | [doc 151](https://tushare.pro/document/2?doc_id=151) |
| Tushare官方目录 | 宏观经济/国内宏观/利率数据 | Libor拆借利率 | `libor` | 有权限 | 已实现（契约通用采集器：原始层+强类型标准表） | 0 | [doc 152](https://tushare.pro/document/2?doc_id=152) |
| Tushare官方目录 | 宏观经济/国内宏观/利率数据 | Shibor利率数据 | `shibor` | 有权限 | 已实现（契约通用采集器：原始层+强类型标准表） | 0 | [doc 149](https://tushare.pro/document/2?doc_id=149) |
| Tushare官方目录 | 宏观经济/国内宏观/利率数据 | Shibor报价数据 | `shibor_quote` | 有权限 | 已实现（契约通用采集器：原始层+强类型标准表） | 0 | [doc 150](https://tushare.pro/document/2?doc_id=150) |
| Tushare官方目录 | 宏观经济/国内宏观/利率数据 | 广州民间借贷利率 | `gz_index` | 有权限 | 已实现（契约通用采集器：原始层+强类型标准表） | 0 | [doc 174](https://tushare.pro/document/2?doc_id=174) |
| Tushare官方目录 | 宏观经济/国内宏观/利率数据 | 温州民间借贷利率 | `wz_index` | 有权限 | 已实现（契约通用采集器：原始层+强类型标准表） | 0 | [doc 173](https://tushare.pro/document/2?doc_id=173) |
| Tushare官方目录 | 宏观经济/国内宏观/国民经济 | GDP数据 | `cn_gdp` | 有权限 | 已实现（契约通用采集器：原始层+强类型标准表） | 0 | [doc 227](https://tushare.pro/document/2?doc_id=227) |
| Tushare官方目录 | 宏观经济/国内宏观/景气度 | 采购经理人指数 | `cn_pmi` | 有权限 | 已实现（契约通用采集器：原始层+强类型标准表） | 0 | [doc 325](https://tushare.pro/document/2?doc_id=325) |
| Tushare官方目录 | 宏观经济/国内宏观/金融/社会融资 | 社融数据（月度） | `sf_month` | 有权限 | 已实现（契约通用采集器：原始层+强类型标准表） | 0 | [doc 310](https://tushare.pro/document/2?doc_id=310) |
| Tushare官方目录 | 宏观经济/国内宏观/金融/货币供应量 | 货币供应量 | `cn_m` | 有权限 | 已实现（契约通用采集器：原始层+强类型标准表） | 0 | [doc 242](https://tushare.pro/document/2?doc_id=242) |
| Tushare官方目录 | 宏观经济/国际宏观/美国利率 | 国债实际收益率曲线利率 | `us_trycr` | 有权限 | 已实现（契约通用采集器：原始层+强类型标准表） | 0 | [doc 220](https://tushare.pro/document/2?doc_id=220) |
| Tushare官方目录 | 宏观经济/国际宏观/美国利率 | 国债收益率曲线利率（日频） | `us_tycr` | 有权限 | 已实现（契约通用采集器：原始层+强类型标准表） | 0 | [doc 219](https://tushare.pro/document/2?doc_id=219) |
| Tushare官方目录 | 宏观经济/国际宏观/美国利率 | 国债长期利率 | `us_tltr` | 有权限 | 已实现（契约通用采集器：原始层+强类型标准表） | 0 | [doc 222](https://tushare.pro/document/2?doc_id=222) |
| Tushare官方目录 | 宏观经济/国际宏观/美国利率 | 国债实际长期利率平均值 | `us_trltr` | 有权限 | 已实现（契约通用采集器：原始层+强类型标准表） | 0 | [doc 223](https://tushare.pro/document/2?doc_id=223) |
| Tushare官方目录 | 宏观经济/国际宏观/美国利率 | 短期国债利率 | `us_tbr` | 有权限 | 已实现（契约通用采集器：原始层+强类型标准表） | 0 | [doc 221](https://tushare.pro/document/2?doc_id=221) |
| Tushare官方目录 | 指数专题 | SW指数历史分钟 | `sw_mins` | 无权限 | 未实现 | 40203 | [doc 469](https://tushare.pro/document/2?doc_id=469) |
| Tushare官方目录 | 指数专题 | 中信行业成分 | `ci_index_member` | 有权限 | 已实现（契约通用采集器：原始层+强类型标准表） | 0 | [doc 373](https://tushare.pro/document/2?doc_id=373) |
| Tushare官方目录 | 指数专题 | 中信行业指数行情 | `ci_daily` | 有权限 | 已实现（契约通用采集器：原始层+强类型标准表） | 0 | [doc 308](https://tushare.pro/document/2?doc_id=308) |
| Tushare官方目录 | 指数专题 | 国际指数 | `index_global` | 有权限 | 已实现 | 0 | [doc 211](https://tushare.pro/document/2?doc_id=211) |
| Tushare官方目录 | 指数专题 | 大盘指数每日指标 | `index_dailybasic` | 有权限 | 已实现 | 0 | [doc 128](https://tushare.pro/document/2?doc_id=128) |
| Tushare官方目录 | 指数专题 | 指数历史分钟行情 | `idx_mins` | 无权限 | 未实现 | 40203 | [doc 419](https://tushare.pro/document/2?doc_id=419) |
| Tushare官方目录 | 指数专题 | 指数周线行情 | `index_weekly` | 有权限 | 已实现 | 0 | [doc 171](https://tushare.pro/document/2?doc_id=171) |
| Tushare官方目录 | 指数专题 | 指数基本信息 | `index_basic` | 有权限 | 已实现 | 0 | [doc 94](https://tushare.pro/document/2?doc_id=94) |
| Tushare官方目录 | 指数专题 | A股实时分钟 | `rt_idx_min` | 无权限 | 未实现 | 40203 | [doc 420](https://tushare.pro/document/2?doc_id=420) |
| Tushare官方目录 | 指数专题 | A股实时分钟 | `rt_idx_min_daily` | 无权限 | 未实现 | 40203 | [doc 420](https://tushare.pro/document/2?doc_id=420) |
| Tushare官方目录 | 指数专题 | 交易所指数实时日线 | `rt_idx_k` | 无权限 | 未实现 | 40203 | [doc 403](https://tushare.pro/document/2?doc_id=403) |
| Tushare官方目录 | 指数专题 | 指数成分和权重 | `index_weight` | 有权限 | 已实现（契约通用采集器：原始层+强类型标准表） | 0 | [doc 96](https://tushare.pro/document/2?doc_id=96) |
| Tushare官方目录 | 指数专题 | 指数技术因子(专业版) | `idx_factor_pro` | 有权限 | 已实现（契约通用采集器：原始层+强类型标准表） | 0 | [doc 358](https://tushare.pro/document/2?doc_id=358) |
| Tushare官方目录 | 指数专题 | 指数日线行情 | `index_daily` | 有权限 | 已实现 | 0 | [doc 95](https://tushare.pro/document/2?doc_id=95) |
| Tushare官方目录 | 指数专题 | 指数月线行情 | `index_monthly` | 有权限 | 已实现 | 0 | [doc 172](https://tushare.pro/document/2?doc_id=172) |
| Tushare官方目录 | 指数专题 | 市场交易统计 | `daily_info` | 有权限 | 已实现（契约通用采集器：原始层+强类型标准表） | 0 | [doc 215](https://tushare.pro/document/2?doc_id=215) |
| Tushare官方目录 | 指数专题 | 深圳市场每日交易概况 | `sz_daily_info` | 有权限 | 已实现（契约通用采集器：原始层+强类型标准表） | 0 | [doc 268](https://tushare.pro/document/2?doc_id=268) |
| Tushare官方目录 | 指数专题 | 申万实时行情 | `rt_sw_k` | 无权限 | 未实现 | 40203 | [doc 417](https://tushare.pro/document/2?doc_id=417) |
| Tushare官方目录 | 指数专题 | 申万行业日线行情 | `sw_daily` | 有权限 | 已实现（契约通用采集器：原始层+强类型标准表） | 0 | [doc 327](https://tushare.pro/document/2?doc_id=327) |
| Tushare官方目录 | 指数专题 | 申万行业分类 | `index_classify` | 有权限 | 已实现（契约通用采集器：原始层+强类型标准表） | 0 | [doc 181](https://tushare.pro/document/2?doc_id=181) |
| Tushare官方目录 | 指数专题 | 申万行业成分构成(分级) | `index_member_all` | 有权限 | 已实现（契约通用采集器：原始层+强类型标准表） | 0 | [doc 335](https://tushare.pro/document/2?doc_id=335) |
| Tushare官方目录 | 期权数据 | 期权历史分钟行情 | `opt_mins` | 无权限 | 未实现 | 40203 | [doc 341](https://tushare.pro/document/2?doc_id=341) |
| Tushare官方目录 | 期权数据 | 期权合约信息 | `opt_basic` | 有权限 | 已实现（契约通用采集器：原始层+强类型标准表） | 0 | [doc 158](https://tushare.pro/document/2?doc_id=158) |
| Tushare官方目录 | 期权数据 | 期权日线行情 | `opt_daily` | 有权限 | 已实现（契约通用采集器：原始层+强类型标准表） | 0 | [doc 159](https://tushare.pro/document/2?doc_id=159) |
| Tushare官方目录 | 期货数据 | 仓单日报 | `fut_wsr` | 有权限 | 已实现（契约通用采集器：原始层+强类型标准表） | 0 | [doc 140](https://tushare.pro/document/2?doc_id=140) |
| Tushare官方目录 | 期货数据 | 南华期货指数日线行情 | `fut_index_daily` | 有权限 | 已实现（契约通用采集器：原始层+强类型标准表） | 50101 | [doc 468](https://tushare.pro/document/2?doc_id=468) |
| Tushare官方目录 | 期货数据 | 期货Tick行情数据 | `` | 非API数据服务 | 未实现 | not_documented | [doc 314](https://tushare.pro/document/2?doc_id=314) |
| Tushare官方目录 | 期货数据 | 期货历史分钟行情 | `ft_mins` | 无权限 | 未实现 | 40203 | [doc 313](https://tushare.pro/document/2?doc_id=313) |
| Tushare官方目录 | 期货数据 | 期货合约信息表 | `fut_basic` | 有权限 | 已实现（契约通用采集器：原始层+强类型标准表） | 0 | [doc 135](https://tushare.pro/document/2?doc_id=135) |
| Tushare官方目录 | 期货数据 | 期货实时分钟行情 | `rt_fut_min` | 无权限 | 未实现 | 40203 | [doc 340](https://tushare.pro/document/2?doc_id=340) |
| Tushare官方目录 | 期货数据 | 期货实时分钟行情 | `rt_fut_min_daily` | 无权限 | 未实现 | 40203 | [doc 340](https://tushare.pro/document/2?doc_id=340) |
| Tushare官方目录 | 期货数据 | 期货日线行情 | `fut_daily` | 有权限 | 已实现（契约通用采集器：原始层+强类型标准表） | 0 | [doc 138](https://tushare.pro/document/2?doc_id=138) |
| Tushare官方目录 | 期货数据 | 期货主力与连续合约 | `fut_mapping` | 有权限 | 已实现（契约通用采集器：原始层+强类型标准表） | 0 | [doc 189](https://tushare.pro/document/2?doc_id=189) |
| Tushare官方目录 | 期货数据 | 期货主要品种交易周报 | `fut_weekly_detail` | 有权限 | 已实现（契约通用采集器：原始层+强类型标准表） | 0 | [doc 216](https://tushare.pro/document/2?doc_id=216) |
| Tushare官方目录 | 期货数据 | 交易日历 | `fut_trade_cal` | 有权限 | 已实现（契约通用采集器：原始层+强类型标准表） | 0 | [doc 467](https://tushare.pro/document/2?doc_id=467) |
| Tushare官方目录 | 期货数据 | 期货合约涨跌停价格（盘前） | `ft_limit` | 有权限 | 已实现（契约通用采集器：原始层+强类型标准表） | 0 | [doc 368](https://tushare.pro/document/2?doc_id=368) |
| Tushare官方目录 | 期货数据 | 期货周/月线行情(每日更新) | `fut_weekly_monthly` | 有权限 | 已实现（契约通用采集器：原始层+强类型标准表） | 0 | [doc 337](https://tushare.pro/document/2?doc_id=337) |
| Tushare官方目录 | 期货数据 | 每日成交持仓排名 | `fut_holding` | 有权限 | 已实现（契约通用采集器：原始层+强类型标准表） | 0 | [doc 139](https://tushare.pro/document/2?doc_id=139) |
| Tushare官方目录 | 期货数据 | 结算参数 | `fut_settle` | 有权限 | 已实现（契约通用采集器：原始层+强类型标准表） | 0 | [doc 141](https://tushare.pro/document/2?doc_id=141) |
| Tushare官方目录 | 港股数据 | 港股交易日历 | `hk_tradecal` | 有权限 | 已实现（契约通用采集器：原始层+强类型标准表） | 0 | [doc 250](https://tushare.pro/document/2?doc_id=250) |
| Tushare官方目录 | 港股数据 | 港股分钟行情 | `hk_mins` | 无权限 | 未实现 | 40203 | [doc 304](https://tushare.pro/document/2?doc_id=304) |
| Tushare官方目录 | 港股数据 | 港股利润表 | `hk_income` | 无权限 | 未实现 | 40203 | [doc 389](https://tushare.pro/document/2?doc_id=389) |
| Tushare官方目录 | 港股数据 | 港股列表 | `hk_basic` | 有权限 | 已实现（契约通用采集器：原始层+强类型标准表） | 0 | [doc 191](https://tushare.pro/document/2?doc_id=191) |
| Tushare官方目录 | 港股数据 | 港股复权因子 | `hk_adjfactor` | 无权限 | 未实现 | 40203 | [doc 401](https://tushare.pro/document/2?doc_id=401) |
| Tushare官方目录 | 港股数据 | 港股复权行情 | `hk_daily_adj` | 无权限 | 未实现 | 40203 | [doc 339](https://tushare.pro/document/2?doc_id=339) |
| Tushare官方目录 | 港股数据 | 港股实时日线 | `rt_hk_k` | 无权限 | 未实现 | 40203 | [doc 383](https://tushare.pro/document/2?doc_id=383) |
| Tushare官方目录 | 港股数据 | 港股行情 | `hk_daily` | 有权限 | 已实现（契约通用采集器：原始层+强类型标准表） | 0 | [doc 192](https://tushare.pro/document/2?doc_id=192) |
| Tushare官方目录 | 港股数据 | 港股现金流量表 | `hk_cashflow` | 无权限 | 未实现 | 40203 | [doc 391](https://tushare.pro/document/2?doc_id=391) |
| Tushare官方目录 | 港股数据 | 港股财务指标数据 | `hk_fina_indicator` | 无权限 | 未实现 | 40203 | [doc 388](https://tushare.pro/document/2?doc_id=388) |
| Tushare官方目录 | 港股数据 | 港股资产负债表 | `hk_balancesheet` | 无权限 | 未实现 | 40203 | [doc 390](https://tushare.pro/document/2?doc_id=390) |
| Tushare官方目录 | 现货数据 | 黄金现货基础信息 | `sge_basic` | 有权限 | 已实现 | 0 | [doc 284](https://tushare.pro/document/2?doc_id=284) |
| Tushare官方目录 | 现货数据 | 现货黄金日行情 | `sge_daily` | 有权限 | 已实现 | 0 | [doc 285](https://tushare.pro/document/2?doc_id=285) |
| Tushare官方目录 | 美股数据 | 美股交易日历 | `us_tradecal` | 有权限 | 已实现（契约通用采集器：原始层+强类型标准表） | 0 | [doc 253](https://tushare.pro/document/2?doc_id=253) |
| Tushare官方目录 | 美股数据 | 美股利润表 | `us_income` | 无权限 | 未实现 | 40203 | [doc 394](https://tushare.pro/document/2?doc_id=394) |
| Tushare官方目录 | 美股数据 | 美股列表 | `us_basic` | 有权限 | 已实现（契约通用采集器：原始层+强类型标准表） | 0 | [doc 252](https://tushare.pro/document/2?doc_id=252) |
| Tushare官方目录 | 美股数据 | 美股复权因子 | `us_adjfactor` | 无权限 | 未实现 | 40203 | [doc 402](https://tushare.pro/document/2?doc_id=402) |
| Tushare官方目录 | 美股数据 | 美股复权行情 | `us_daily_adj` | 无权限 | 未实现 | 40203 | [doc 338](https://tushare.pro/document/2?doc_id=338) |
| Tushare官方目录 | 美股数据 | 美股行情 | `us_daily` | 无权限 | 未实现 | 40203 | [doc 254](https://tushare.pro/document/2?doc_id=254) |
| Tushare官方目录 | 美股数据 | 美股现金流量表 | `us_cashflow` | 无权限 | 未实现 | 40203 | [doc 396](https://tushare.pro/document/2?doc_id=396) |
| Tushare官方目录 | 美股数据 | 美股财务指标数据 | `us_fina_indicator` | 无权限 | 未实现 | 40203 | [doc 393](https://tushare.pro/document/2?doc_id=393) |
| Tushare官方目录 | 美股数据 | 美股资产负债表 | `us_balancesheet` | 无权限 | 未实现 | 40203 | [doc 395](https://tushare.pro/document/2?doc_id=395) |
| Tushare官方目录 | 股票数据/两融及转融通 | 做市借券交易汇总 | `slb_len_mm` | 有权限 | 已实现（契约通用采集器：原始层+强类型标准表） | 0 | [doc 334](https://tushare.pro/document/2?doc_id=334) |
| Tushare官方目录 | 股票数据/两融及转融通 | 融资融券交易明细 | `margin_detail` | 有权限 | 已实现 | 0 | [doc 59](https://tushare.pro/document/2?doc_id=59) |
| Tushare官方目录 | 股票数据/两融及转融通 | 融资融券交易汇总 | `margin` | 有权限 | 已实现 | 0 | [doc 58](https://tushare.pro/document/2?doc_id=58) |
| Tushare官方目录 | 股票数据/两融及转融通 | 融资融券标的（盘前更新） | `margin_secs` | 有权限 | 已实现 | 0 | [doc 326](https://tushare.pro/document/2?doc_id=326) |
| Tushare官方目录 | 股票数据/两融及转融通 | 转融券交易明细 | `slb_sec_detail` | 有权限 | 已实现（契约通用采集器：原始层+强类型标准表） | 0 | [doc 333](https://tushare.pro/document/2?doc_id=333) |
| Tushare官方目录 | 股票数据/两融及转融通 | 转融券交易汇总 | `slb_sec` | 有权限 | 已实现（契约通用采集器：原始层+强类型标准表） | 0 | [doc 332](https://tushare.pro/document/2?doc_id=332) |
| Tushare官方目录 | 股票数据/两融及转融通 | 转融资交易汇总 | `slb_len` | 有权限 | 已实现 | 0 | [doc 331](https://tushare.pro/document/2?doc_id=331) |
| Tushare官方目录 | 股票数据/参考数据 | 个股严重异常波动 | `stk_high_shock` | 有权限 | 已实现 | 0 | [doc 452](https://tushare.pro/document/2?doc_id=452) |
| Tushare官方目录 | 股票数据/参考数据 | 个股异常波动 | `stk_shock` | 有权限 | 已实现 | 0 | [doc 451](https://tushare.pro/document/2?doc_id=451) |
| Tushare官方目录 | 股票数据/参考数据 | 交易所重点提示证券 | `stk_alert` | 有权限 | 已实现 | 0 | [doc 453](https://tushare.pro/document/2?doc_id=453) |
| Tushare官方目录 | 股票数据/参考数据 | 前十大流通股东 | `top10_floatholders` | 有权限 | 已实现 | 0 | [doc 62](https://tushare.pro/document/2?doc_id=62) |
| Tushare官方目录 | 股票数据/参考数据 | 前十大股东 | `top10_holders` | 有权限 | 已实现 | 0 | [doc 61](https://tushare.pro/document/2?doc_id=61) |
| Tushare官方目录 | 股票数据/参考数据 | 大宗交易 | `block_trade` | 有权限 | 已实现 | 0 | [doc 161](https://tushare.pro/document/2?doc_id=161) |
| Tushare官方目录 | 股票数据/参考数据 | 股东人数 | `stk_holdernumber` | 有权限 | 已实现 | 0 | [doc 166](https://tushare.pro/document/2?doc_id=166) |
| Tushare官方目录 | 股票数据/参考数据 | 股东增减持 | `stk_holdertrade` | 有权限 | 已实现 | 0 | [doc 175](https://tushare.pro/document/2?doc_id=175) |
| Tushare官方目录 | 股票数据/参考数据 | 股权质押明细 | `pledge_detail` | 有权限 | 已实现 | 0 | [doc 111](https://tushare.pro/document/2?doc_id=111) |
| Tushare官方目录 | 股票数据/参考数据 | 股权质押统计数据 | `pledge_stat` | 有权限 | 已实现 | 0 | [doc 110](https://tushare.pro/document/2?doc_id=110) |
| Tushare官方目录 | 股票数据/参考数据 | 股票回购 | `repurchase` | 有权限 | 已实现 | 0 | [doc 124](https://tushare.pro/document/2?doc_id=124) |
| Tushare官方目录 | 股票数据/参考数据 | 股票账户开户数据 | `stk_account` | 有权限 | 已实现（契约通用采集器：原始层+强类型标准表） | 0 | [doc 164](https://tushare.pro/document/2?doc_id=164) |
| Tushare官方目录 | 股票数据/参考数据 | 股票账户开户数据（旧） | `stk_account_old` | 接口无效/已下线 | 未实现 | 40101 | [doc 165](https://tushare.pro/document/2?doc_id=165) |
| Tushare官方目录 | 股票数据/参考数据 | 限售股解禁 | `share_float` | 有权限 | 已实现 | 0 | [doc 160](https://tushare.pro/document/2?doc_id=160) |
| Tushare官方目录 | 股票数据/基础数据 | IPO新股列表 | `new_share` | 有权限 | 已实现 | 0 | [doc 123](https://tushare.pro/document/2?doc_id=123) |
| Tushare官方目录 | 股票数据/基础数据 | ST股票列表 | `stock_st` | 有权限 | 已实现 | 0 | [doc 397](https://tushare.pro/document/2?doc_id=397) |
| Tushare官方目录 | 股票数据/基础数据 | ST风险警示板股票 | `st` | 有权限 | 已实现 | 0 | [doc 423](https://tushare.pro/document/2?doc_id=423) |
| Tushare官方目录 | 股票数据/基础数据 | 上市公司基本信息 | `stock_company` | 有权限 | 已实现 | 0 | [doc 112](https://tushare.pro/document/2?doc_id=112) |
| Tushare官方目录 | 股票数据/基础数据 | 上市公司管理层 | `stk_managers` | 有权限 | 已实现 | 0 | [doc 193](https://tushare.pro/document/2?doc_id=193) |
| Tushare官方目录 | 股票数据/基础数据 | 交易日历 | `trade_cal` | 有权限 | 已实现 | 0 | [doc 26](https://tushare.pro/document/2?doc_id=26) |
| Tushare官方目录 | 股票数据/基础数据 | 北交所新旧代码对照表 | `bse_mapping` | 有权限 | 已实现 | 0 | [doc 375](https://tushare.pro/document/2?doc_id=375) |
| Tushare官方目录 | 股票数据/基础数据 | 股本情况（盘前） | `stk_premarket` | 无权限 | 未实现 | 40203 | [doc 329](https://tushare.pro/document/2?doc_id=329) |
| Tushare官方目录 | 股票数据/基础数据 | 沪深港通股票列表 | `stock_hsgt` | 有权限 | 已实现 | 0 | [doc 398](https://tushare.pro/document/2?doc_id=398) |
| Tushare官方目录 | 股票数据/基础数据 | 管理层薪酬和持股 | `stk_rewards` | 有权限 | 已实现 | 0 | [doc 194](https://tushare.pro/document/2?doc_id=194) |
| Tushare官方目录 | 股票数据/基础数据 | 股票基础信息 | `stock_basic` | 有权限 | 已实现 | 0 | [doc 25](https://tushare.pro/document/2?doc_id=25) |
| Tushare官方目录 | 股票数据/基础数据 | 股票历史列表（历史每天股票列表） | `bak_basic` | 有权限 | 已实现 | 0 | [doc 262](https://tushare.pro/document/2?doc_id=262) |
| Tushare官方目录 | 股票数据/基础数据 | 股票曾用名 | `namechange` | 有权限 | 已实现 | 0 | [doc 100](https://tushare.pro/document/2?doc_id=100) |
| Tushare官方目录 | 股票数据/打板专题数据 | 概念板块 | `dc_index` | 有权限 | 已实现 | 0 | [doc 362](https://tushare.pro/document/2?doc_id=362) |
| Tushare官方目录 | 股票数据/打板专题数据 | 板块成分 | `dc_member` | 有权限 | 已实现 | 0 | [doc 363](https://tushare.pro/document/2?doc_id=363) |
| Tushare官方目录 | 股票数据/打板专题数据 | 概念板块行情 | `dc_daily` | 有权限 | 已实现 | 0 | [doc 382](https://tushare.pro/document/2?doc_id=382) |
| Tushare官方目录 | 股票数据/打板专题数据 | DC热榜 | `dc_hot` | 有权限 | 已实现 | 0 | [doc 321](https://tushare.pro/document/2?doc_id=321) |
| Tushare官方目录 | 股票数据/打板专题数据 | TDX板块信息 | `tdx_index` | 有权限 | 已实现 | 0 | [doc 376](https://tushare.pro/document/2?doc_id=376) |
| Tushare官方目录 | 股票数据/打板专题数据 | TDX板块成分 | `tdx_member` | 有权限 | 已实现 | 0 | [doc 377](https://tushare.pro/document/2?doc_id=377) |
| Tushare官方目录 | 股票数据/打板专题数据 | TDX板块行情 | `tdx_daily` | 有权限 | 已实现 | 0 | [doc 378](https://tushare.pro/document/2?doc_id=378) |
| Tushare官方目录 | 股票数据/打板专题数据 | 概念和行业指数 | `ths_index` | 有权限 | 已实现 | 0 | [doc 259](https://tushare.pro/document/2?doc_id=259) |
| Tushare官方目录 | 股票数据/打板专题数据 | 概念板块成分 | `ths_member` | 有权限 | 已实现 | 0 | [doc 261](https://tushare.pro/document/2?doc_id=261) |
| Tushare官方目录 | 股票数据/打板专题数据 | 板块指数行情 | `ths_daily` | 有权限 | 已实现 | 0 | [doc 260](https://tushare.pro/document/2?doc_id=260) |
| Tushare官方目录 | 股票数据/打板专题数据 | 涨跌停榜单（同花顺） | `limit_list_ths` | 有权限 | 已实现（契约通用采集器：原始层+强类型标准表） | 0 | [doc 355](https://tushare.pro/document/2?doc_id=355) |
| Tushare官方目录 | 股票数据/打板专题数据 | THS热榜 | `ths_hot` | 有权限 | 已实现 | 0 | [doc 320](https://tushare.pro/document/2?doc_id=320) |
| Tushare官方目录 | 股票数据/打板专题数据 | 游资名录 | `hm_list` | 有权限 | 已实现 | 0 | [doc 311](https://tushare.pro/document/2?doc_id=311) |
| Tushare官方目录 | 股票数据/打板专题数据 | 当日集合竞价 | `stk_auction` | 有权限 | 已实现 | 0 | [doc 369](https://tushare.pro/document/2?doc_id=369) |
| Tushare官方目录 | 股票数据/打板专题数据 | 开盘啦榜单数据 | `kpl_list` | 有权限 | 已实现 | 0 | [doc 347](https://tushare.pro/document/2?doc_id=347) |
| Tushare官方目录 | 股票数据/打板专题数据 | 最强板块统计 | `limit_cpt_list` | 有权限 | 已实现 | 0 | [doc 357](https://tushare.pro/document/2?doc_id=357) |
| Tushare官方目录 | 股票数据/打板专题数据 | 连板天梯 | `limit_step` | 有权限 | 已实现 | 0 | [doc 356](https://tushare.pro/document/2?doc_id=356) |
| Tushare官方目录 | 股票数据/打板专题数据 | 涨跌停列表（新） | `limit_list_d` | 有权限 | 已实现 | 0 | [doc 298](https://tushare.pro/document/2?doc_id=298) |
| Tushare官方目录 | 股票数据/打板专题数据 | 游资每日明细 | `hm_detail` | 无权限 | 未实现 | 40203 | [doc 312](https://tushare.pro/document/2?doc_id=312) |
| Tushare官方目录 | 股票数据/打板专题数据 | 题材成分 | `dc_concept_cons` | 有权限 | 已实现 | 0 | [doc 422](https://tushare.pro/document/2?doc_id=422) |
| Tushare官方目录 | 股票数据/打板专题数据 | 开盘啦题材成分 | `kpl_concept_cons` | 有权限 | 已实现 | 0 | [doc 351](https://tushare.pro/document/2?doc_id=351) |
| Tushare官方目录 | 股票数据/打板专题数据 | 题材库 | `dc_concept` | 有权限 | 已实现 | 0 | [doc 421](https://tushare.pro/document/2?doc_id=421) |
| Tushare官方目录 | 股票数据/打板专题数据 | 龙虎榜机构明细 | `top_inst` | 有权限 | 已实现 | 0 | [doc 107](https://tushare.pro/document/2?doc_id=107) |
| Tushare官方目录 | 股票数据/打板专题数据 | 龙虎榜每日明细 | `top_list` | 有权限 | 已实现 | 0 | [doc 106](https://tushare.pro/document/2?doc_id=106) |
| Tushare官方目录 | 股票数据/特色数据 | AH股比价 | `stk_ah_comparison` | 有权限 | 已实现 | 0 | [doc 399](https://tushare.pro/document/2?doc_id=399) |
| Tushare官方目录 | 股票数据/特色数据 | 券商每月荐股 | `broker_recommend` | 有权限 | 已实现 | 0 | [doc 267](https://tushare.pro/document/2?doc_id=267) |
| Tushare官方目录 | 股票数据/特色数据 | 卖方盈利预测数据 | `report_rc` | 有权限 | 已实现 | 0 | [doc 292](https://tushare.pro/document/2?doc_id=292) |
| Tushare官方目录 | 股票数据/特色数据 | 机构调研表 | `stk_surv` | 有权限 | 已实现 | 0 | [doc 275](https://tushare.pro/document/2?doc_id=275) |
| Tushare官方目录 | 股票数据/特色数据 | 每日筹码分布 | `cyq_chips` | 有权限 | 已实现 | 0 | [doc 294](https://tushare.pro/document/2?doc_id=294) |
| Tushare官方目录 | 股票数据/特色数据 | 每日筹码及胜率 | `cyq_perf` | 有权限 | 已实现 | 0 | [doc 293](https://tushare.pro/document/2?doc_id=293) |
| Tushare官方目录 | 股票数据/特色数据 | 神奇九转指标 | `stk_nineturn` | 有权限 | 已实现 | 0 | [doc 364](https://tushare.pro/document/2?doc_id=364) |
| Tushare官方目录 | 股票数据/特色数据 | 股票开盘集合竞价数据 | `stk_auction_o` | 有权限 | 已实现 | 0 | [doc 353](https://tushare.pro/document/2?doc_id=353) |
| Tushare官方目录 | 股票数据/特色数据 | 股票技术因子（量化因子） | `stk_factor` | 有权限 | 已实现（契约通用采集器：原始层+强类型标准表） | 0 | [doc 296](https://tushare.pro/document/2?doc_id=296) |
| Tushare官方目录 | 股票数据/特色数据 | 股票技术面因子(专业版) | `stk_factor_pro` | 有权限 | 已实现 | 0 | [doc 328](https://tushare.pro/document/2?doc_id=328) |
| Tushare官方目录 | 股票数据/特色数据 | 股票收盘集合竞价数据 | `stk_auction_c` | 有权限 | 已实现 | 0 | [doc 354](https://tushare.pro/document/2?doc_id=354) |
| Tushare官方目录 | 股票数据/行情数据 | 股票历史分钟行情 | `stk_mins` | 有权限（当前限频） | 已实现（契约通用采集器：原始层+强类型标准表） | 40203 | [doc 370](https://tushare.pro/document/2?doc_id=370) |
| Tushare官方目录 | 股票数据/行情数据 | A股日线行情 | `daily` | 有权限 | 已实现 | 0 | [doc 27](https://tushare.pro/document/2?doc_id=27) |
| Tushare官方目录 | 股票数据/行情数据 | 股票周/月线行情(复权--每日更新) | `stk_week_month_adj` | 有权限 | 已实现（契约通用采集器：原始层+强类型标准表） | 0 | [doc 365](https://tushare.pro/document/2?doc_id=365) |
| Tushare官方目录 | 股票数据/行情数据 | 股票周/月线行情(每日更新) | `stk_weekly_monthly` | 有权限 | 已实现 | 0 | [doc 336](https://tushare.pro/document/2?doc_id=336) |
| Tushare官方目录 | 股票数据/行情数据 | 周线行情 | `weekly` | 有权限 | 已实现 | 0 | [doc 144](https://tushare.pro/document/2?doc_id=144) |
| Tushare官方目录 | 股票数据/行情数据 | 备用行情 | `bak_daily` | 有权限 | 已实现（契约通用采集器：原始层+强类型标准表） | 0 | [doc 255](https://tushare.pro/document/2?doc_id=255) |
| Tushare官方目录 | 股票数据/行情数据 | 复权因子 | `adj_factor` | 有权限 | 已实现（契约通用采集器：原始层+强类型标准表） | 0 | [doc 28](https://tushare.pro/document/2?doc_id=28) |
| Tushare官方目录 | 股票数据/行情数据 | A股复权行情 | `pro_bar` | 依底层接口权限 | 未实现 | sdk_only | [doc 146](https://tushare.pro/document/2?doc_id=146) |
| Tushare官方目录 | 股票数据/行情数据 | 月线行情 | `monthly` | 有权限 | 已实现 | 0 | [doc 145](https://tushare.pro/document/2?doc_id=145) |
| Tushare官方目录 | 股票数据/行情数据 | 每日停复牌信息 | `suspend_d` | 有权限 | 已实现 | 0 | [doc 214](https://tushare.pro/document/2?doc_id=214) |
| Tushare官方目录 | 股票数据/行情数据 | 每日指标 | `daily_basic` | 有权限 | 已实现（契约通用采集器：原始层+强类型标准表） | 0 | [doc 32](https://tushare.pro/document/2?doc_id=32) |
| Tushare官方目录 | 股票数据/行情数据 | 每日涨跌停价格 | `stk_limit` | 有权限 | 已实现 | 0 | [doc 183](https://tushare.pro/document/2?doc_id=183) |
| Tushare官方目录 | 股票数据/行情数据 | 沪深股通十大成交股 | `hsgt_top10` | 有权限 | 已实现 | 0 | [doc 48](https://tushare.pro/document/2?doc_id=48) |
| Tushare官方目录 | 股票数据/行情数据 | 通用行情接口 | `pro_bar` | 依底层接口权限 | 未实现 | sdk_only | [doc 109](https://tushare.pro/document/2?doc_id=109) |
| Tushare官方目录 | 股票数据/财务数据 | 业绩快报 | `express` | 有权限 | 已实现（express_vip） | 0 | [doc 46](https://tushare.pro/document/2?doc_id=46) |
| Tushare官方目录 | 股票数据/财务数据 | 业绩预告 | `forecast` | 有权限 | 已实现（forecast_vip） | 0 | [doc 45](https://tushare.pro/document/2?doc_id=45) |
| Tushare官方目录 | 股票数据/财务数据 | 主营业务构成 | `fina_mainbz` | 有权限 | 已实现（fina_mainbz_vip） | 0 | [doc 81](https://tushare.pro/document/2?doc_id=81) |
| Tushare官方目录 | 股票数据/财务数据 | 分红送股 | `dividend` | 有权限 | 已实现 | 0 | [doc 103](https://tushare.pro/document/2?doc_id=103) |
| Tushare官方目录 | 股票数据/财务数据 | 利润表 | `income` | 有权限 | 已实现（income_vip） | 0 | [doc 33](https://tushare.pro/document/2?doc_id=33) |
| Tushare官方目录 | 股票数据/财务数据 | 现金流量表 | `cashflow` | 有权限 | 已实现（cashflow_vip） | 0 | [doc 44](https://tushare.pro/document/2?doc_id=44) |
| Tushare官方目录 | 股票数据/财务数据 | 财务审计意见 | `fina_audit` | 有权限 | 已实现（契约通用采集器：原始层+强类型标准表） | 0 | [doc 80](https://tushare.pro/document/2?doc_id=80) |
| Tushare官方目录 | 股票数据/财务数据 | 财务指标数据 | `fina_indicator` | 有权限 | 已实现（fina_indicator_vip） | 0 | [doc 79](https://tushare.pro/document/2?doc_id=79) |
| Tushare官方目录 | 股票数据/财务数据 | 财报披露计划 | `disclosure_date` | 有权限 | 已实现 | 0 | [doc 162](https://tushare.pro/document/2?doc_id=162) |
| Tushare官方目录 | 股票数据/财务数据 | 资产负债表 | `balancesheet` | 有权限 | 已实现（balancesheet_vip） | 0 | [doc 36](https://tushare.pro/document/2?doc_id=36) |
| Tushare官方目录 | 股票数据/资金流向数据 | 个股资金流向 | `moneyflow` | 有权限 | 已实现 | 0 | [doc 170](https://tushare.pro/document/2?doc_id=170) |
| Tushare官方目录 | 股票数据/资金流向数据 | 个股资金流向（DC） | `moneyflow_dc` | 有权限 | 已实现 | 0 | [doc 349](https://tushare.pro/document/2?doc_id=349) |
| Tushare官方目录 | 股票数据/资金流向数据 | 个股资金流向（THS） | `moneyflow_ths` | 有权限 | 已实现 | 0 | [doc 348](https://tushare.pro/document/2?doc_id=348) |
| Tushare官方目录 | 股票数据/资金流向数据 | 大盘资金流向（DC） | `moneyflow_mkt_dc` | 有权限 | 已实现 | 0 | [doc 345](https://tushare.pro/document/2?doc_id=345) |
| Tushare官方目录 | 股票数据/资金流向数据 | 东财概念及行业板块资金流向（DC） | `moneyflow_ind_dc` | 有权限 | 已实现 | 0 | [doc 344](https://tushare.pro/document/2?doc_id=344) |
| Tushare官方目录 | 股票数据/资金流向数据 | 同花顺概念板块资金流向（THS） | `moneyflow_cnt_ths` | 有权限 | 已实现 | 0 | [doc 371](https://tushare.pro/document/2?doc_id=371) |
| Tushare官方目录 | 股票数据/资金流向数据 | 同花顺行业资金流向（THS） | `moneyflow_ind_ths` | 有权限 | 已实现 | 0 | [doc 343](https://tushare.pro/document/2?doc_id=343) |
| Tushare官方目录 | 自选组合 | 自选股组合查询 | `p_get` | 有权限 | 已实现（契约通用采集器：原始层+强类型标准表） | 0 | [doc 449](https://tushare.pro/document/2?doc_id=449) |
| Tushare官方目录 | 自选组合 | 自选股组合保存 | `p_save` | 有权限 | 已封装（写接口，不进入采集调度） | 50101 | [doc 445](https://tushare.pro/document/2?doc_id=445) |
| Tushare官方目录 | 自选组合 | 自选股组合查询 | `p_list` | 有权限 | 已实现（契约通用采集器：原始层+强类型标准表） | 0 | [doc 446](https://tushare.pro/document/2?doc_id=446) |
| Tushare官方目录 | 自选组合 | 自选股组合删除 | `p_delete` | 有权限 | 已封装（写接口，不进入采集调度） | 50101 | [doc 447](https://tushare.pro/document/2?doc_id=447) |
| Tushare官方目录 | 量化因子库 | 因子列表 | `factor_list` | 无权限 | 未实现 | 40203 | [doc 486](https://tushare.pro/document/2?doc_id=486) |
| Tushare官方目录 | 量化因子库 | 因子值 | `factor_value` | 有权限 | 已实现（契约通用采集器：原始层+强类型标准表） | 50101 | [doc 490](https://tushare.pro/document/2?doc_id=490) |
| claw-quant扩展/历史接口 | 项目扩展接口 | 当前官方目录未列出 | `balancesheet_vip` | 有权限 | 已实现 | 0 |  |
| claw-quant扩展/历史接口 | 项目扩展接口 | 当前官方目录未列出 | `cashflow_vip` | 有权限 | 已实现 | 0 |  |
| claw-quant扩展/历史接口 | 项目扩展接口 | 当前官方目录未列出 | `ccass_hold` | 有权限 | 已实现 | 0 |  |
| claw-quant扩展/历史接口 | 项目扩展接口 | 当前官方目录未列出 | `ccass_hold_detail` | 有权限 | 已实现 | 50101 |  |
| claw-quant扩展/历史接口 | 项目扩展接口 | 当前官方目录未列出 | `express_vip` | 有权限 | 已实现 | 0 |  |
| claw-quant扩展/历史接口 | 项目扩展接口 | 当前官方目录未列出 | `fina_indicator_vip` | 有权限 | 已实现 | 0 |  |
| claw-quant扩展/历史接口 | 项目扩展接口 | 当前官方目录未列出 | `fina_mainbz_vip` | 有权限 | 已实现 | 0 |  |
| claw-quant扩展/历史接口 | 项目扩展接口 | 当前官方目录未列出 | `forecast_vip` | 有权限 | 已实现 | 0 |  |
| claw-quant扩展/历史接口 | 项目扩展接口 | 当前官方目录未列出 | `ggt_daily` | 有权限 | 已实现 | 0 |  |
| claw-quant扩展/历史接口 | 项目扩展接口 | 当前官方目录未列出 | `ggt_top10` | 有权限 | 已实现 | 50101 |  |
| claw-quant扩展/历史接口 | 项目扩展接口 | 当前官方目录未列出 | `hk_hold` | 有权限 | 已实现 | 0 |  |
| claw-quant扩展/历史接口 | 项目扩展接口 | 当前官方目录未列出 | `income_vip` | 有权限 | 已实现 | 0 |  |
| claw-quant扩展/历史接口 | 项目扩展接口 | 当前官方目录未列出 | `moneyflow_hsgt` | 有权限 | 已实现 | 50101 |  |
