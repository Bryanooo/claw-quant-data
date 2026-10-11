---
name: claw-quant-technical-screening
description: Screen the governed A-share universe for trend, breakout, oversold-reversal, or volume-breakout candidates, verify market coverage and audit evidence, and drill into shortlisted securities. Use for stock discovery or candidate-ranking requests; do not use it to issue trading recommendations or to bypass the research API with raw-table scans.
---

# Claw Quant Technical Screening

Check readiness, then run one or more disclosed server-side presets on the same cutoff:

```bash
./clawq research readiness
./clawq research technical-screen --preset trend --limit 30 --as-of YYYY-MM-DD
```

Available presets are `trend`, `breakout`, `oversold-reversal`, and `volume-breakout`. Treat them
as transparent candidate generators, not buy signals. Check `meta.actual_data_date`,
`meta.coverage`, `meta.audit_evidence`, and `meta.quality` before interpreting rankings. A
non-empty result is not ready when the market cross-section or underlying `stock_daily`
partition is not certified.

Explain each candidate from `matched_rules` and returned metrics; do not invent extra ranking
factors. Compare overlapping presets when useful, but keep each preset's rank separate. For a
shortlist, call `technicals` and, when relevant, `capital-flow` for each security on the same
`as_of`; use the price/trend, volume/flow, levels/risk, and wave/Chan Skills for deeper analysis.

Report the screened universe, eligible count, total matched count, returned limit, exclusions,
and data cutoff. Oversold is a state; require the preset's positive reversal day and subsequent
price/volume evidence before calling it a reversal. Never scan raw tables, weaken audit gates,
or present a candidate list as investment advice.
