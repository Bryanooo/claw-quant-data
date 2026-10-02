---
name: macro-research
description: Analyze China's growth, inflation, liquidity, rates, and macro regime as context for company fundamentals, with explicit observation-vintage limits.
---

# Macro Research

Use `/macro/regime` and the narrowest growth, inflation, or liquidity theme with one `as_of`.
Start from components before the regime label, then state the transmission to demand, cost,
financing, or valuation. Use canonical `cn_lpr`; ChinaMoney official rows are authoritative and
Tushare `shibor_lpr` is only a collection fallback. Do not merge LPR with Shibor. Fiscal impulse,
external balance, overseas policy, and strict first-release vintages remain partial source gaps.
