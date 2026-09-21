---
name: cross-asset-research
description: Compare Chinese indices, ETFs, THS sectors, and SGE spot contracts through one governed multi-timeframe research contract with asset-specific caveats.
---

# Cross-Asset Research

Use `/v1/research/instruments/{asset_type}/{code}/technicals` with asset types `index`, `etf`,
`sector`, or `spot`; use `provider=ths` for THS sectors. Compare data sufficiency before signals.
ETF price action does not replace composition/NAV/share-flow analysis. Sector index action does
not replace constituent breadth. Au99.99 reflects domestic RMB gold and cannot by itself separate
global bullion from currency effects. Never hide `limited_history` or claim a long-cycle signal
from a sparse monthly series.
