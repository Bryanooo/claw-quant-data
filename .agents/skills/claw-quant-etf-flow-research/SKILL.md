---
name: claw-quant-etf-flow-research
description: Analyze ETF share creations and redemptions, exposure rotation, stabilization patterns, and possible state-team activity through Claw Quant's governed research APIs. Use for ETF资金流、份额变化、宽基护盘、国家队ETF行为 or ETF间腾挪 questions; never infer investor identity from market flow alone.
---

# Claw Quant ETF Flow Research

Use only the governed research contract. Start with readiness and capabilities, then query at
least one short and one medium window when the question concerns persistence or rotation:

```bash
./clawq research readiness
./clawq research capabilities
./clawq research etf-flows --lookback-observations 5 --as-of YYYY-MM-DD
./clawq research etf-flows --lookback-observations 20 --as-of YYYY-MM-DD
./clawq research state-team-signals \
  --lookback-observations 5 --minimum-flow-yi 5 --as-of YYYY-MM-DD
```

Use `instrument-technicals etf` for a named ETF and `instrument-technicals index` for its
tracked exposure. Add `market-breadth` or `sector-rotation` only when the research question
needs broader market context. Keep every query on the same `--as-of` cutoff.

## Analysis workflow

1. Check `meta.quality`, `latest_data_date`, `baseline_data_date`, observations, warnings, and
   provenance before interpreting a non-empty result.
2. Compare 5/20 observations for tactical flow and 60/250 only when enough history is present.
   Separate one-off creations from persistent accumulation or redemption.
3. Analyze the tracked exposure first, then drill into the largest member ETFs. Distinguish
   exposure-level flow from product selection between managers or fee structures.
4. Cross flow direction with index return: inflow during a falling index is a stabilization
   pattern, not proof of a particular buyer; outflow during a rally can reflect profit-taking,
   arbitrage, or creation/redemption mechanics.
5. Treat every `rotation_pair` as cross-sectional coincidence. Never say the same capital moved
   from the source to the destination unless investor-level evidence traces it.
6. For state-team questions, build an evidence ledger from official exchange, regulator,
   government, fund-manager, or periodic holder disclosures. Record publication time, entity,
   product, reporting period, shares or amount, and source URL.
7. Preserve the service's evidence level. `market_flow_only` and `state_team_confirmed=false`
   cannot be upgraded by narrative confidence, price action, media repetition, or model inference.

## Output contract

Show:

- data cutoff, windows, coverage, and quality limitations;
- the largest exposure inflows/outflows and the ETFs contributing to them;
- price/flow regime and whether the pattern persists across windows;
- rotation candidates with an explicit “not a traced transfer” label;
- an evidence ledger separating official confirmation, market-flow evidence, media narrative,
  and unresolved hypotheses;
- charts when useful: exposure flow bars, multi-window flow heatmap, and aligned index return.

Do not recompute the flow proxy from raw tables or bypass `/api/v1/research/*`. The canonical
service calculation is share change multiplied by latest NAV, with its documented fallback and
unit conversion. Do not treat fund size change as cash flow because price movement also changes
fund size. Identity confirmation remains unavailable until an official announcement or holder
report names the investor.

For the full formula, evidence model, initialization boundary, and known limitations, read
[the canonical ETF research contract](../../../docs/ETF_STATE_TEAM_RESEARCH.md).
