---
name: etf-flow-research
description: Analyze ETF creation and redemption proxies, exposure rotation, stabilization patterns, and state-team evidence without inferring investor identity from market flow alone.
---

# ETF Flow Research

Use `/v1/research/etfs/flows` and `/v1/research/etfs/state-team-signals` after readiness and
capabilities checks. Keep all calls on the same `as_of`. Compare at least 5 and 20 observations
for persistence; use 60 or 250 only when the returned history is sufficient. Add the governed
instrument technical endpoint for a named ETF or tracked index when price context is required.

Check quality, provenance, baseline/latest data dates, warnings, and asset class. Analyze the
tracked exposure before individual products. Distinguish exposure flow from product selection,
and treat every returned rotation pair as cross-sectional coincidence rather than a traced
transfer.

Cross flow with index return. Inflow while the index falls is a stabilization pattern, not proof
of who bought. Preserve `evidence_level` and `state_team_confirmed`; never promote
`market_flow_only` using price behavior, media repetition, or model confidence. Confirmation
requires an official exchange, regulator, government, fund-manager, or periodic holder disclosure
that names the entity and product.

Return the data cutoff and windows, largest exposure inflows/outflows, contributing ETFs,
multi-window persistence, price/flow regime, and an evidence ledger separating official facts,
market-flow evidence, media narrative, and unresolved hypotheses. When visual output is available,
prefer exposure-flow bars, a multi-window heatmap, and aligned index returns over a dense table.

Never query lower data APIs or SQL and never recalculate the canonical flow proxy from raw records.
Do not treat fund size change as cash flow because price movement also changes fund size.
