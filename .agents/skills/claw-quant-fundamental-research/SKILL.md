---
name: claw-quant-fundamental-research
description: Synthesize a complete A-share fundamental thesis from macro, industry, company-quality, valuation, shareholder-return, disclosure, and event evidence. Use for full-company fundamental reports or investment-thesis requests; use the narrower component Skills for a single lens.
---

# Claw Quant Fundamental Research Synthesis

This is the Fundamental Research Agent's synthesis Skill. It does not replace the component
research Skills or bypass their evidence boundaries. Start with the shared data contract:

```bash
./clawq research readiness
./clawq research capabilities
./clawq stock research-pack TS_CODE --financial-periods 8 --as-of YYYY-MM-DD
```

Keep one `as_of` cutoff and preserve each component's quality, provenance, gaps, and
external-data requirements. Treat `unknown_empty` as unknown, never as proof that an event did
not happen.

Load only the Skills required by the question:

- macro environment and transmission: `$claw-quant-macro-research`;
- industry fundamentals and breadth: `$claw-quant-industry-research`;
- company growth, profitability, cash quality, and balance sheet:
  `$claw-quant-financial-quality-research`;
- valuation, repurchase, dividend, dilution, and shareholder return:
  `$claw-quant-valuation-shareholder-research`;
- official disclosures, ownership, governance, litigation, and regulatory evidence:
  `$claw-quant-disclosure-governance-research`;
- catalyst timing and abnormal returns: `$claw-quant-event-research`.
- decision-driving financial, valuation, contribution, and event charts:
  `$claw-quant-market-charting`.

Build the conclusion from five separate lenses:

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

For scenario construction, risk transmission, and falsifiers, read
[references/thesis-and-risks.md](references/thesis-and-risks.md). Always show the financial
period, announcement date, market-data date, quality status, and material gaps. Do not average
component confidence into a false precision score: name the evidence that limits the thesis.

Separate observed facts, derived metrics, and interpretation. Do not issue a buy/sell verdict
from valuation alone.

Use `$claw-quant-technical-research` only when the requested output also needs market-price
structure. Technical confirmation does not repair a weak or missing fundamental premise.
