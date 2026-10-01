---
name: claw-quant-industry-research
description: Analyze sector and industry fundamentals, valuation, member breadth, contributors, and market behavior through Claw Quant's governed research APIs. Use for 行业景气、板块基本面、行业估值、成分扩散 or industry comparison questions; do not infer industry demand from an index price alone.
---

# Claw Quant Industry Research

Resolve the provider and sector code first, then keep the same membership cutoff:

```bash
./clawq sector list --provider ths --query 半导体
./clawq research industry-fundamentals ths 884229.TI --as-of YYYY-MM-DD
./clawq research industry-breadth ths 884229.TI --as-of YYYY-MM-DD
./clawq sector research-pack ths 884229.TI --as-of YYYY-MM-DD
./clawq research instrument-technicals sector 884229.TI --provider ths --as-of YYYY-MM-DD
```

Read [references/methodology.md](references/methodology.md) before comparing periods or sectors.
Separate aggregated company financials, valuation, member participation, index price action, and
industry operating data. Never describe price strength as broad participation unless the breadth
endpoint confirms it. Never describe aggregated listed-company revenue as total industry demand.

Show provider/classification, membership effective date, report period, member and data coverage,
aggregate growth, median quality metrics, valuation, leading contributors, breadth, and material
gaps. Use charts for financial trends, valuation distributions, breadth, and contribution
concentration when they affect the conclusion.
