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

## Fibonacci retracement

`fibonacci_retracement` is not the Fibonacci pivot family. It anchors to the latest two confirmed
volatility-filtered ZigZag pivots and returns 23.6%, 38.2%, 50%, 61.8%, and 78.6% retracement plus
127.2%, 161.8%, and 200% extension levels. The live pivot is disclosed but excluded as an anchor.
If fewer than two pivots are confirmed, report that the structure is insufficient.
The latest weekly/monthly aggregate is marked incomplete and excluded from structural confirmation.

## Chan structure

`chan_analysis` implements one auditable candidate variant: merge containing bars in the inferred
direction; confirm three-bar top/bottom fractals; connect alternating fractals whose indices are
at least four apart (five bars inclusive) into strokes; expose three-stroke extension segments; and define a center
as the common price interval of at least three consecutive strokes. Divergence requires a new
same-direction price extreme with absolute MACD-histogram energy below 80% of the prior stroke.
First, second, and third buy/sell labels are structural candidates only. Always state that Chan
schools differ and use the returned `methodology` instead of silently substituting another variant.

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
- `Aroon(25)` measures how recently the rolling high and low occurred. `Parabolic SAR` is an
  iterative trailing reversal system. They overlap other trend evidence and are not extra votes.

## Gaps and risk

- A full up-gap requires the current low above the prior high; a full down-gap requires the current
  high below the prior low. `filled` means a later bar crossed the far boundary; otherwise inspect
  `fill_progress_pct`.
- Historical VaR and Expected Shortfall use observed returns without assuming a normal
  distribution. Sortino uses a zero target; this assumption is explicit in the response.
- Benchmark Beta, correlation, zero-risk-free-rate Alpha, tracking error, and information ratio use
  aligned close-to-close returns for the named window. Do not compare metrics from different windows
  or benchmarks as if they shared a sample.

## Volume and price

- `activity` compares the five-bar average with the twenty-bar average, and reports the latest
  volume's 120-bar Z-score and 250-bar percentile. `expanding` requires at least 1.2×; `contracting`
  requires at most 0.8×.
- `price_volume_regime` is descriptive: price up/down is combined with expanding/contracting
  volume. A selling-exhaustion label is only a candidate and does not confirm a reversal.
- `breakout_confirmation` requires a close outside the prior twenty completed bars. Confirmation
  requires latest volume of at least 1.2× the prior-twenty average.
- OBV and A/D divergence requires price to move at least 2% over the named window while the
  cumulative volume indicator moves oppositely. Treat it as a candidate until price structure
  confirms it.
- PVT, A/D, Force Index, and Ease of Movement raw levels are instrument-specific. Compare their
  direction and history, not their numeric levels across assets.
- `anchored_vwap_proxy` volume-weights the daily typical price `(H+L+C)/3`. It is useful for
  daily positioning but is not session VWAP or a price-volume profile. Those require intraday or
  trade data.
- Raw traded quantity is not adjustment-factor normalized. For stocks, prefer free-float turnover
  when comparing across share-capital changes.

## Waves

`wave_analysis` uses a volatility-adjusted ZigZag threshold bounded between 5% and 15%.
Confirmed pivots are reproducible; the last pivot is live until a reversal exceeds the
threshold. Elliott 1–5/A–B–C labels remain scenario-dependent, so present a primary and an
alternate interpretation with explicit invalidation.

## Candlesticks

Pattern names describe OHLC geometry only. Confirm reversal candidates with the following
bar, the preceding trend, and volume. Never infer causality from a candle.
