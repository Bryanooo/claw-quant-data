# 宏观与行业研究契约

宏观和行业能力属于只读研究层 `/api/v1/research/*`。它们提供可复现事实、透明规则、
来源与质量边界，不输出预测或买卖建议。Agent 调用前仍应先检查 `readiness` 与
`capabilities`。

## 宏观环境

### 状态接口

```http
GET /api/v1/research/macro/regime?as_of=2026-09-18
```

`as_of` 可选，表示允许使用的经济观察期上限。响应包含：

- `growth`：GDP 同比变化和制造业 PMI 变化；
- `inflation`：CPI/PPI 同比及变化；
- `liquidity`：M1/M2、社融、Shibor 3M 和 LPR；
- `quadrant`：由增长与通胀方向按公开规则组合的描述性状态；
- `meta.quality`：缺失序列、修订版本和未覆盖数据源告警。

### 主题序列

```http
GET /api/v1/research/macro/growth?periods=24&as_of=2026-09-18
GET /api/v1/research/macro/inflation?periods=24&as_of=2026-09-18
GET /api/v1/research/macro/liquidity?periods=24&as_of=2026-09-18
```

`periods` 为 2–120。所有序列按经济观察期去重并返回 `observation_date`。当前标准表
没有完整保存每次首次发布值、发布日期和后续修订版本，因此历史 `as_of` 不是严格的
publication-vintage 快照；分析“当时市场已知什么”时必须补充官方发布档案。

CLI 对应命令：

```bash
./clawq research macro-regime --as-of 2026-09-18
./clawq research macro-theme growth --periods 24 --as-of 2026-09-18
```

## 行业研究

行业身份必须同时包含 `provider` 和 `sector_code`。不同供应方的同名板块不会被自动
合并。

### 行业基本面

```http
GET /api/v1/research/sectors/ths/884229.TI/fundamentals?as_of=2026-09-18&contributor_limit=10
```

接口以 `as_of` 时有效的成分为边界，选择覆盖至少半数成员的最新已披露报告期，并与
上年同期比较。响应包含：

- 成员生效日期、成员数量和财务/估值覆盖率；
- 收入、归母净利润、经营现金流、自由现金流和同比；
- 毛利率、净利率、ROE、ROIC、资产负债率的成分中位数；
- PE/PB/PS/股息率中位数和总市值；
- 收入和利润主要贡献公司。

聚合收入代表当前上市成分的财务合计，不代表整个行业需求。历史截止使用公告时间，
但财务表保存的是当前已存报表版本，不是每次更正前后的完整快照。

### 行业内部宽度

```http
GET /api/v1/research/sectors/ths/884229.TI/breadth?as_of=2026-09-18
```

响应按同一时点成分返回上涨/下跌/平盘数量、平均与中位收益、站上 MA20/MA60 的数量
和比例、成交额及行情覆盖率。指数上涨不能替代内部宽度证据。

CLI 对应命令：

```bash
./clawq research industry-fundamentals ths 884229.TI \
  --contributor-limit 10 --as-of 2026-09-18
./clawq research industry-breadth ths 884229.TI --as-of 2026-09-18
```

## 已知缺口

- 宏观：严格首次发布版本、财政脉冲、外部平衡、海外政策和商品库存；
- 行业：分行业产能、库存、产品价格、订单与供需高频数据；
- 分类：成员历史准确度受上游纳入/剔除日期质量约束。

上述缺口已经进入 `capabilities.new_source_todos`，不能由 Skill 静默猜测或用板块价格
替代。
