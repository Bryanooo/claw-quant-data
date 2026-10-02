---
name: claw-quant-market-charting
description: Turn governed Claw Quant research responses into decision-focused candlestick, financial-trend, flow, breadth, and comparison charts. Use when a research conclusion benefits from a visual; do not hide data gaps or imply unsupported intraday precision.
---

# Claw Quant Market Charting

Chart only fields returned by the governed research contract and preserve `as_of`, source,
adjustment, timeframe, units, and quality warnings. For stocks, use `chart.points` for candlesticks
with aligned volume and at most the few overlays that affect the conclusion. Put momentum or flow
in separate panels rather than mixing incompatible scales.

Use line charts for comparable financial periods, bars for contributions or exposure flows,
heatmaps for multi-window ETF flows or breadth, and small multiples for cross-asset comparisons.
Mark announcements only when their timestamps and evidence source are known. Daily anchored VWAP
must remain labelled as a proxy; never render it as an intraday volume profile.

If visual rendering is unavailable, return a compact chart specification containing series,
units, cutoff, annotations, and warnings. A chart must clarify a decision-driving relationship,
not reproduce every response field.
