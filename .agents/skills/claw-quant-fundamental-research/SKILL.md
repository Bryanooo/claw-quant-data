---
name: claw-quant-fundamental-research
description: Analyze an A-share company's financial quality, growth, valuation, business mix, and risks from Claw Quant's governed research APIs. Use for company fundamental analysis, financial trend review, valuation, or investment-thesis requests; do not use for technical-chart-only analysis.
---

# Claw Quant Company Fundamental Research

Use only the governed research commands:

```bash
./clawq research readiness
./clawq research capabilities
./clawq research fundamentals TS_CODE --periods 12 --as-of YYYY-MM-DD
./clawq research valuation TS_CODE --lookback-days 730 --as-of YYYY-MM-DD
./clawq research repurchase-progress TS_CODE --as-of YYYY-MM-DD
./clawq stock research-pack TS_CODE --financial-periods 8 --as-of YYYY-MM-DD
```

Stop and disclose the limitation when a required dataset is missing. Treat `unknown_empty`
as unknown, never as proof that an event did not happen. Keep every call on the same `as_of`
cutoff and inspect `meta.quality`, `meta.provenance`, `meta.gaps`, and
`external_data_needed` before interpreting a non-empty response.

Load only the guidance required by the question:

- financial performance and accounting quality: read
  [references/financial-quality.md](references/financial-quality.md);
- valuation, dividends, repurchases, or shareholder return: read
  [references/valuation-and-allocation.md](references/valuation-and-allocation.md);
- full investment thesis, scenarios, risks, and falsifiers: read
  [references/thesis-and-risks.md](references/thesis-and-risks.md).

Build a full-company conclusion from five separate lenses:

1. Growth: compare like-for-like fiscal periods; distinguish quarterly, cumulative interim,
   and annual figures.
2. Quality: reconcile profit with operating cash flow, free cash flow, margins, accruals,
   working capital, leverage, and return on capital.
3. Valuation: prefer the company's own historical distribution; use peer medians only after
   checking comparability and outliers. Do not invent a fair value without explicit discount,
   growth, and forecast-horizon assumptions.
4. Capital allocation and shareholder return: separate announced plans from executed cash
   return. Use repurchase progress, dividends, dilution, and financing events only when their
   coverage and announcement dates are explicit. Never infer repurchase execution from price.
5. Risks and falsifiers: state what future evidence would weaken the thesis.

When several periods are available, visualize the decision-driving series—normally revenue
growth, net-income growth, gross/net margin, ROE/ROIC, and operating-cash conversion—instead
of replacing the whole analysis with tables. Always show the financial period, announcement
date, market-data date, quality status, and material data gaps.

Separate observed facts, derived metrics, and interpretation. Do not issue a buy/sell verdict
from valuation alone.

For the market response to a repurchase, earnings release, or other corporate action, combine
this Skill with `$claw-quant-event-research`; use `$claw-quant-technical-research` only for the
price and volume structure. Event attribution and chart behavior do not replace the underlying
capital-allocation facts.

This Skill covers companies, not macro regimes or industry aggregates. Route macro questions to
`$claw-quant-macro-research` and industry questions to `$claw-quant-industry-research`.
