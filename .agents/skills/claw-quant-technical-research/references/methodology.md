# Technical methodology

## Price levels

- `rolling high/low`: observed extrema over the named window. These are descriptive bounds,
  not automatically support or resistance.
- `swing_zones`: three-bar local extrema clustered within the larger of half ATR14 or 1% of
  the latest close. Rank nearby zones by repeated touches.
- `classic_pivots`: next-session levels from the prior session: `P=(H+L+C)/3`,
  `S1=2P-H`, `R1=2P-L`, `S2=P-(H-L)`, `R2=P+(H-L)`.
- `fibonacci`: classic pivot plus/minus 0.382, 0.618, and 1.0 times the prior range.
- `woodie`: `P=(H+L+2C)/4`, then symmetric support/resistance from the prior range.
- `camarilla`: prior close plus/minus 1.1 times the prior range at 1/12, 1/6, 1/4, and 1/2.
- `demark`: conditional `X` from prior open versus close; one projected support/resistance pair.
- `cpr`: central pivot range from `P`, `(H+L)/2`, and `2P-BC`.

Every family uses the prior completed bar of the requested timeframe. Do not mix a daily pivot
with a weekly claim or present six nearby formulas as six independent confirmations.

## Timeframes

- `1d`, `1w`, and `1mo` are calculated from the same governed daily OHLCV source. Weekly bars
  end on the last observed session in the ISO week; monthly bars end on the last observed session.
- Read higher timeframe first for regime, daily second for execution detail.
- `long_horizon` uses daily observations for calendar-year returns, CAGR, 52-week range, and
  max drawdown. It intentionally omits annual oscillators when too few annual bars exist.

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
