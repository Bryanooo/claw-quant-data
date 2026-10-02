---
name: claw-quant-volume-flow-research
description: Analyze volume-price regimes, breakout confirmation, cumulative volume indicators, turnover, governed capital flows, margin, northbound, block-trade, and chip evidence. Use for volume or flow questions; preserve optional-dataset quality warnings.
---

# Claw Quant Volume and Flow Research

Use `$claw-quant-data`, then query both contracts on one cutoff:

```bash
./clawq research technicals TS_CODE --lookback-days 400 --as-of YYYY-MM-DD
./clawq research capital-flow TS_CODE --lookback-days 60 --as-of YYYY-MM-DD
```

Interpret 5/20-day activity, 120-day Z-score, and 250-day percentile in the returned method.
Breakout confirmation requires the stated price boundary and volume threshold. OBV/A-D, PVT,
Force Index, and Ease of Movement are directional within one security; do not compare their raw
levels across securities. Daily anchored VWAP is a proxy from daily typical price and volume, not
intraday VWAP or volume profile.

Keep price-volume evidence separate from main-money flow, margin, northbound, block trades, and
chip distribution. If `hk_hold` is stale or `margin_detail`/`cyq_perf` is unverified, show that
section as unavailable or provisional rather than allowing it to contaminate core volume
analysis. Flow correlation does not identify an investor or prove causality.
