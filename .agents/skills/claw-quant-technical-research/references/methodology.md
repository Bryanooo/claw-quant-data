# Technical methodology

## Price levels

- `rolling high/low`: observed extrema over the named window. These are descriptive bounds,
  not automatically support or resistance.
- `swing_zones`: three-bar local extrema clustered within the larger of half ATR14 or 1% of
  the latest close. Rank nearby zones by repeated touches.
- `classic_pivots`: next-session levels from the prior session: `P=(H+L+C)/3`,
  `S1=2P-H`, `R1=2P-L`, `S2=P-(H-L)`, `R2=P+(H-L)`.

## Trend lines

- `bull_bear_boundary` is MA250, commonly called the annual line or bull/bear boundary. It is
  not proof of a bull or bear market by itself.
- `weighted_trend.bull_line` is the 20-period linearly weighted average of
  `(3×close+low+open+high)/6`; `bear_line` is its six-period simple average. This is reported
  separately because informal names such as “牛门线” are not standardized.

## Waves

`wave_analysis` uses a volatility-adjusted ZigZag threshold bounded between 5% and 15%.
Confirmed pivots are reproducible; the last pivot is live until a reversal exceeds the
threshold. Elliott 1–5/A–B–C labels remain scenario-dependent, so present a primary and an
alternate interpretation with explicit invalidation.

## Candlesticks

Pattern names describe OHLC geometry only. Confirm reversal candidates with the following
bar, the preceding trend, and volume. Never infer causality from a candle.
