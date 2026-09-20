---
name: claw-quant-fundamental-research
description: Analyze an A-share company's financial quality, growth, valuation, business mix, and risks from Claw Quant's governed research APIs. Use for company fundamental analysis, financial trend review, valuation, or investment-thesis requests; do not use for technical-chart-only analysis.
---

# Claw Quant Fundamental Research

Use only the governed research commands:

```bash
./clawq research readiness
./clawq research fundamentals TS_CODE --periods 12
./clawq research valuation TS_CODE --lookback-days 730
./clawq stock research-pack TS_CODE --financial-periods 8
```

Stop and disclose the limitation when a required dataset is missing. Treat `unknown_empty`
as unknown, never as proof that an event did not happen.

Build the conclusion from four separate lenses:

1. Growth: compare like-for-like fiscal periods; distinguish quarterly, cumulative interim,
   and annual figures.
2. Quality: reconcile profit with operating cash flow, free cash flow, margins, accruals,
   working capital, leverage, and return on capital.
3. Valuation: prefer the company's own historical distribution; use peer medians only after
   checking comparability and outliers. Do not invent a fair value without explicit discount,
   growth, and forecast-horizon assumptions.
4. Risks and falsifiers: state what future evidence would weaken the thesis.

When several periods are available, visualize the decision-driving series—normally revenue
growth, net-income growth, gross/net margin, ROE/ROIC, and operating-cash conversion—instead
of replacing the whole analysis with tables. Always show the financial period, announcement
date, market-data date, quality status, and material data gaps.

Separate observed facts, derived metrics, and interpretation. Do not issue a buy/sell verdict
from valuation alone.
