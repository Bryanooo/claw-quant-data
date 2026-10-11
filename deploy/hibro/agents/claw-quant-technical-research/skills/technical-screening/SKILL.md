---
name: technical-screening
description: Discover and rank A-share candidates with governed trend, breakout, oversold-reversal, and volume-breakout presets while preserving coverage and audit evidence.
---

# Technical Screening

Run `./clawq research readiness`, then use `./clawq research technical-screen --preset PRESET
--limit N --as-of YYYY-MM-DD`. Check actual data date, universe coverage, audit evidence, quality,
eligible count, and exclusions before reading the rank. Explain only the returned rules and
metrics; a candidate is not a recommendation.

Use multiple presets as separate lenses rather than blending their ranks. Drill shortlisted
stocks through stock technicals and capital flow on the same cutoff. Oversold is only a state;
do not confirm reversal without the returned positive-day rule and subsequent price/volume
evidence. Never reproduce the screen through raw SQL or lower data APIs.
