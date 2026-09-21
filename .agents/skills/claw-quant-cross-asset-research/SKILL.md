---
name: claw-quant-cross-asset-research
description: Analyze governed Chinese indices, ETFs, THS sectors, and Shanghai Gold Exchange spot contracts with one multi-timeframe technical contract. Use for 科创50、行业板块、ETF、Au99.99 or cross-asset comparison requests; disclose limited history and composition gaps.
---

# Claw Quant Cross-Asset Research

Use the public research namespace only:

```bash
./clawq research readiness
./clawq research instrument-technicals index 000688.SH --benchmark 000300.SH
./clawq research instrument-technicals etf 512480.SH --benchmark 000300.SH
./clawq research instrument-technicals sector 884229.TI --provider ths --benchmark 000300.SH
./clawq research instrument-technicals spot Au99.99
```

Analyze each asset in this order:

1. Confirm `meta.quality`, observation count, first/last date, and source dataset.
2. Compare monthly, weekly, then daily trend; do not let a daily oscillator override a sparse
   higher timeframe.
3. Use swing zones and the returned pivot families as scenarios, not targets guaranteed to trade.
4. Compare relative strength only when the benchmark has overlapping dates.
5. For ETFs, separately request composition, NAV, share, and flow capabilities when available;
   price technicals alone do not explain tracking error or investor flows.
6. For sectors, separate index trend from constituent breadth and concentration. If member breadth
   is unavailable, state that the conclusion is price-index-only.
7. For SGE spot, state that domestic RMB gold embeds global bullion and currency effects; do not
   infer either component without the corresponding governed series.

Never hide `limited_history`. Return a comparison table of regime, momentum, volatility, relative
strength, key levels, and data sufficiency, followed by instrument-specific caveats.
