---
name: macro-research
description: Analyze China's growth, inflation, liquidity, rates, and macro regime using governed Claw Quant research endpoints with explicit observation-vintage limits.
---

# Macro Research

Read `/readiness` and `/capabilities`, then call `/macro/regime` and the narrowest of
`/macro/growth`, `/macro/inflation`, or `/macro/liquidity` with one `as_of` cutoff.

Start from component observations before the regime label. Separate observed data, transparent
classification, market-transmission interpretation, and forecast. Show conflicting indicators,
latest observation dates, release-calendar context, and what would falsify the conclusion.

Use canonical `cn_lpr` for China LPR. ChinaMoney official publication rows are authoritative;
Tushare's `shibor_lpr` name is only a collection fallback and must not be presented as Shibor or
merged with the separate Shibor rate series. Preserve source and observation time when coverage
differs.

The current historical view is bounded by observation period but is not a strict first-release
vintage archive. For claims about what the market knew at a past date, require official release
timestamps and historical versions. Fiscal impulse, external balance, and overseas policy remain
declared source gaps.
