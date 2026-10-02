---
name: claw-quant-financial-quality-research
description: Analyze an A-share company's growth, profitability, cash conversion, balance sheet, operating efficiency, capital intensity, and business mix. Use for financial-statement quality or operating-performance questions; do not use valuation multiples as a substitute for business quality.
---

# Claw Quant Financial Quality Research

Use `$claw-quant-data`, then query the governed company facts on one cutoff:

```bash
./clawq research readiness
./clawq research capabilities
./clawq research fundamentals TS_CODE --periods 12 --as-of YYYY-MM-DD
./clawq stock research-pack TS_CODE --financial-periods 8 --as-of YYYY-MM-DD
```

Compare like-for-like fiscal periods and use announcement dates to determine when information
became available. Analyze growth with margins, receivables, inventory, operating cash flow, free
cash flow, and capital expenditure. Interpret ROE through margin, turnover, and leverage; use
ROIC for operating-capital efficiency. Separate recurring operations from one-off gains, policy
changes, acquisitions, and disposals.

Do not apply industrial-company cash-flow or leverage rules mechanically to banks, insurers, or
brokers. Show the periods, coverage, and next evidence that could weaken the conclusion. When
`fina_mainbz` or another optional dependency is unverified, label business-mix conclusions as
provisional rather than silently dropping the warning.
