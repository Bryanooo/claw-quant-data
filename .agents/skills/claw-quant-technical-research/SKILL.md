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
./clawq research repurchase-progress TS_CODE
```

Read [references/methodology.md](references/methodology.md) before explaining support,
resistance, wave structure, candlestick patterns, or bull/bear lines.

Render the returned `chart.points` as a real candlestick chart when visual output is available.
Use aligned panels for volume and momentum; overlay only the few moving averages or Bollinger
bands that matter to the conclusion. Never substitute a dense metric table for price structure.

Analyze in this order:

1. Price structure and K-line patterns.
2. Trend regime and strength: moving averages, MACD, ADX/DMI, Aroon, PSAR, MA250 boundary.
3. Momentum and exhaustion: RSI, KDJ, CCI, Williams %R, MFI, ROC.
4. Volume confirmation: volume ratios and OBV.
5. Volatility and risk: ATR, Bollinger, drawdown, downside deviation, historical VaR/ES and
   Sortino. When a benchmark is supplied, include Beta, correlation, Alpha, tracking error and
   information ratio using the same aligned window.
6. Levels: repeated swing zones first; then compare Classic, Fibonacci, Woodie, Camarilla,
   DeMark, and CPR next-period pivots. Treat `fibonacci_retracement` separately: it is anchored
   to the last completed swing, while Fibonacci pivots are based on the prior period range.
7. Relative strength and capital flow.
8. Wave and Chan candidates: describe alternate scenarios and invalidation, not a single certain
   count. Read the returned Chan variant and never turn a candidate buy/sell point into advice.

Report open price gaps separately from ordinary support/resistance. A full gap is filled only after
price crosses its far boundary; partial penetration is not a completed fill.

Treat a candlestick pattern as a candidate until the next bar, trend, and volume confirm it.
Treat oversold as a condition, not a reversal signal. State the exact formula or method behind
every important level.

Always compare `data.timeframes.1d`, `1w`, and `1mo`. A daily reversal candidate that conflicts
with weekly/monthly trend is lower confidence. Use `data.long_horizon` for calendar-year returns,
CAGR, 52-week position, and drawdown; do not invent annual RSI/MACD when annual history is short.
Use Ichimoku, Donchian, and Supertrend as overlapping trend evidence, not three independent votes.
Use StochRSI and CMF only with their price regime and volume context.
