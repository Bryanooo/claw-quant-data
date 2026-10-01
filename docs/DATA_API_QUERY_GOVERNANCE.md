# 数据查询 API 性能治理

本文描述 `/api/v1/data` 原始/标准数据查询层的安全边界。研究 Agent 应优先使用
`/api/v1/research/*`；数据查询层用于可审计的明细读取，而不是任意 SQL 代理。

## 过滤分级

数据集详情返回三个字段：

- `allowed_filters`：接口能够识别的全部精确过滤字段；
- `standard_filters`：业务键、来源键等默认允许的过滤字段；
- `advanced_filters`：可能没有选择性索引的指标字段。

默认 `filter_mode=standard`。使用高级字段时必须显式传
`filter_mode=advanced`，并同时满足以下至少一个条件：

1. 提供 `date`、`start_date` 或 `end_date`；
2. 同时提供一个标准业务键过滤条件。

例如，按股票和估值指标查询每日基本面：

```http
GET /api/v1/data/datasets/stock_daily_basic/records
    ?ts_code=300750.SZ
    &pe=20
    &filter_mode=advanced
    &start_date=2026-01-01
    &end_date=2026-09-24
```

没有边界的指标过滤会返回 `422 invalid_query`，避免在千万行版本表上触发不可控
的全表扫描。

## 分页

浅分页继续支持 `offset`，但每个数据集默认最多为 `10000`。更深的顺序读取使用
响应中的不透明 `next_cursor`：

```http
GET /api/v1/data/datasets/stock_daily/records?limit=500
GET /api/v1/data/datasets/stock_daily/records?limit=500&cursor=<next_cursor>
```

cursor 绑定数据集及其稳定排序列，不能跨数据集复用，也不能与非零 `offset` 或
`include_total=true` 组合。服务通过多取一行准确计算 `has_more`，不需要执行总数
扫描。当前态的 point-in-time 版本投影暂不支持 cursor；应使用有日期边界的浅分页。

## 业务索引上线

`072_business_query_indexes.sql` 只包含
`CREATE INDEX CONCURRENTLY IF NOT EXISTS`。迁移器用显式
`-- migrate: no-transaction` 标志逐条在 autocommit 模式执行，并拒绝任何其他 SQL，
从而避免大型热表在普通 `CREATE INDEX` 期间阻塞采集写入。每条语句执行后还会检查
`pg_index.indisvalid`；并发建索引中断留下的无效索引不会被错误登记为已完成。

索引分为两类：

- 审核后的当前态视图身份索引：`factor_value`、`fund_portfolio`、
  `index_weight`、`slb_sec_detail`、`eco_cal`、`major_news`、`fund_nav`、
  `fina_audit`；
- 已有真实查询模板的实体优先索引：基金净值单基金历史、股票估值历史、指数成分历史。

该迁移必须在容量检查后由发布流程执行。本次代码变更不会自动在正在采集的生产库
上建索引。执行后需用 `pg_stat_progress_create_index` 观察进度，并用研究查询与覆盖审计
的 `EXPLAIN (ANALYZE, BUFFERS)` 验证索引命中；不得仅凭索引存在即判定治理完成。
