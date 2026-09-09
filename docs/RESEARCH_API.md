# 股票与板块研究数据服务

本服务为个人和 Agent 提供带来源、历史时点和质量状态的结构化研究材料。它负责
数据访问和可信度表达，不在数据层生成评级、交易建议、因子或回测结果。

## 个股资料包

```http
GET /api/v1/stocks/{ts_code}/research-pack
    ?lookback_days=180
    &benchmark=399006.SZ
    &financial_periods=8
    &as_of=2026-09-08
```

`as_of` 同时约束：

- 行情、估值、资金和基准指数的观察日期；
- 财务、预告、快报、股东和公司行为的报告期；
- 有 `ann_date` 的数据在该日期前必须已经公开。

响应的 `meta.provenance` 逐数据集给出返回数量、观察范围、可获得日期字段和历史
时点状态。`meta.quality` 中：

- `missing`：研究包所需的周期性核心数据没有记录；
- `unknown_empty`：结果为空，但仅凭数据库不能证明该股票确实没有该事件；
- `point_in_time_safe`：所有要求历史时点过滤的组成部分均已执行可获得日期约束。

媒体新闻不是交易所公告，`external_data_needed` 会继续明确要求从官方公告源核验。

## 板块发现

```http
GET /api/v1/sectors?provider=ths&query=人工智能&category=概念指数&market=A&as_of=2026-09-08&limit=100
```

支持 `ths`、`dc`、`tdx`。板块代码属于供应方命名空间，调用者必须同时保存
`provider` 和 `sector_code`，不能只根据板块名称合并。

## 股票所属板块与可比股票

```http
GET /api/v1/stocks/{ts_code}/sectors?provider=ths&as_of=2026-09-08
GET /api/v1/stocks/{ts_code}/peers?provider=ths&as_of=2026-09-08&max_sectors=5&limit=50
```

`sectors` 按供应方的历史成分关系解析股票所属板块。`peers` 排除宽基指数，优先使用
行业和规模较小的概念板块，再按共同板块数量排序；响应同时返回产生该关系的板块，
不会把“同板块”伪装成估值或基本面相似度。

## 板块快照与成分

```http
GET /api/v1/sectors/{provider}/{sector_code}/snapshot?as_of=2026-09-08
GET /api/v1/sectors/{provider}/{sector_code}/members?as_of=2026-09-08&limit=500
```

同花顺成分按照 `in_date <= as_of < out_date` 判断；东财和通达信选择不晚于
`as_of` 的最近一个成分截面。响应返回实际采用的 `membership_effective_date`，
避免把旧截面伪装成目标日期截面。

## 板块资料包

```http
GET /api/v1/sectors/{provider}/{sector_code}/research-pack
    ?lookback_days=180
    &member_limit=500
    &as_of=2026-09-08
```

资料包包括板块资料、最新行情、历史行情、历史时点成分和供应方可用的板块资金流。
`meta.quality` 给出核心缺失、实际行情范围、资金流状态和成分是否可能因调用上限截断。

## 原始数据查询与历史时点

声明了 `availability_column` 的数据集支持：

```http
GET /api/v1/datasets/income/records
    ?ts_code=000001.SZ
    &end_date=2024-03-31
    &as_of=2024-04-30
```

服务会同时执行 `end_date <= 2024-03-31` 和 `ann_date <= 2024-04-30`。不具备
可靠可获得日期字段的数据集会拒绝 `as_of`，不会悄悄退化为不安全查询。
