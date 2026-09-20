---
name: claw-quant-technical-research
description: Analyze A-share price action with candlesticks, trend, momentum, volume, volatility, support/resistance, relative strength, and reproducible wave candidates from Claw Quant research APIs. Use for technical analysis, K-line charts, timing, oversold/overbought, or price-level questions; do not present subjective wave counts as facts.
---

# Claw Quant Technical Research

Run the governed endpoint and keep the requested observation date explicit:

```bash
./clawq research readiness
./clawq research technicals TS_CODE --lookback-days 400 --chart-points 120
./clawq research capital-flow TS_CODE --lookback-days 60
```

Read [references/methodology.md](references/methodology.md) before explaining support,
resistance, wave structure, candlestick patterns, or bull/bear lines.

Render the returned `chart.points` as a real candlestick chart when visual output is available.
Use aligned panels for volume and momentum; overlay only the few moving averages or Bollinger
bands that matter to the conclusion. Never substitute a dense metric table for price structure.

Analyze in this order:

1. Price structure and K-line patterns.
2. Trend regime and strength: moving averages, MACD, ADX/DMI, MA250 boundary.
3. Momentum and exhaustion: RSI, KDJ, CCI, Williams %R, MFI, ROC.
4. Volume confirmation: volume ratios and OBV.
5. Volatility and risk: ATR, Bollinger, drawdown.
6. Levels: repeated swing zones first, classic next-session pivots second, rolling extremes as
   descriptive context only.
7. Relative strength and capital flow.
8. Wave candidates: describe alternate scenarios and invalidation, not a single certain count.

Treat a candlestick pattern as a candidate until the next bar, trend, and volume confirm it.
Treat oversold as a condition, not a reversal signal. State the exact formula or method behind
every important level.
