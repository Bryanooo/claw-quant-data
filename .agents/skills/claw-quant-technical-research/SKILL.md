---
name: claw-quant-technical-research
description: Synthesize a complete multi-timeframe technical view from price-trend, volume-flow, levels-risk, wave-structure, cross-asset, ETF-flow, and chart evidence. Use for full technical reports or scenario requests; use the narrower component Skills for one technical lens.
---

# Claw Quant Technical Research Synthesis

This is the Technical Research Agent's synthesis Skill. Start with the shared data contract and
keep the requested observation date explicit:

```bash
./clawq research readiness
./clawq research capabilities
./clawq research technicals TS_CODE --lookback-days 400 --chart-points 120 --as-of YYYY-MM-DD
./clawq research capital-flow TS_CODE --lookback-days 60 --as-of YYYY-MM-DD
```

Keep all calls on the same `as_of` cutoff. Inspect `meta.quality`, `meta.provenance`,
`meta.gaps`, and `external_data_needed` before interpreting a non-empty response. Repurchases,
dividends, and capital allocation are fundamental/event evidence, not technical indicators;
route those questions to `$claw-quant-fundamental-research` and
`$claw-quant-event-research`.

Load only the Skills needed for the question:

- K-line, multi-timeframe trend, patterns, and momentum: `$claw-quant-price-trend-research`;
- volume, price-volume confirmation, and governed flow evidence:
  `$claw-quant-volume-flow-research`;
- support/resistance, pivots, Fibonacci, volatility, and risk:
  `$claw-quant-levels-risk-research`;
- ZigZag, Elliott, and Chan candidates: `$claw-quant-wave-chan-research`;
- index, ETF, sector, or SGE comparison: `$claw-quant-cross-asset-research`;
- ETF share flows and identity evidence: `$claw-quant-etf-flow-research`;
- visual output: `$claw-quant-market-charting`.

Analyze in this order:

1. Price structure and K-line patterns.
2. Trend regime and strength: moving averages, MACD, ADX/DMI, Aroon, PSAR, MA250 boundary.
3. Momentum and exhaustion: RSI, KDJ, CCI, Williams %R, MFI, ROC.
4. Volume confirmation: activity Z-score/percentile, the four price-volume regimes, breakout
   confirmation, OBV/A-D divergence, PVT, Force Index, Ease of Movement, turnover normalization,
   and daily-bar anchored VWAP proxies. Never describe the proxies as intraday VWAP.
5. Volatility and risk: ATR, Bollinger, drawdown, downside deviation, historical VaR/ES and
   Sortino. When a benchmark is supplied, include Beta, correlation, Alpha, tracking error and
   information ratio using the same aligned window.
6. Levels: repeated swing zones first; then compare Classic, Fibonacci, Woodie, Camarilla,
   DeMark, and CPR next-period pivots. Treat `fibonacci_retracement` separately: it is anchored
   to the last completed swing, while Fibonacci pivots are based on the prior period range.
7. Relative strength and capital flow.
8. Wave and Chan candidates: describe alternate scenarios and invalidation, not a single certain
   count. Read the returned Chan variant and never turn a candidate buy/sell point into advice.

End with a primary scenario, an alternate scenario, and explicit price/volume/time invalidation.
Treat oversold as a condition rather than a reversal signal, and never convert wave or Chan
candidates into trading advice. A whole-market screener is not currently part of the governed
research contract; do not emulate one by querying lower data APIs or raw SQL.
