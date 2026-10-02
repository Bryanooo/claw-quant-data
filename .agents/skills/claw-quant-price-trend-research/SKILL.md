---
name: claw-quant-price-trend-research
description: Analyze governed daily, weekly, monthly, and long-horizon price structure, candlesticks, gaps, trend, momentum, and regime conflicts. Use for K-line, trend, momentum, overbought, or oversold questions; do not treat a pattern or oscillator as a confirmed reversal.
---

# Claw Quant Price and Trend Research

Use `$claw-quant-data`, then query `technicals` on one cutoff. Compare monthly, weekly, then daily
structure. Unfinished weekly or monthly bars must not confirm a completed-period pattern.

Treat moving averages, MACD, ADX/DMI, Aroon, PSAR, Ichimoku, Donchian, and Supertrend as
overlapping evidence rather than independent votes. RSI, KDJ, CCI, Williams %R, MFI, ROC, and
StochRSI describe state or momentum; overbought and oversold are not reversal facts. A
candlestick pattern requires preceding trend, next-bar, and volume context.

Report gaps separately. A full upward gap has low above the prior high, and a downward gap the
inverse; only crossing the far boundary completes a fill. Use long-horizon output for annual
returns, CAGR, 52-week position, and drawdown, and do not invent annual oscillators from sparse
history. State which timeframe governs when signals conflict.
