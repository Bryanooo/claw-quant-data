---
name: claw-quant-macro-research
description: Assess China's growth, inflation, liquidity, rates, and macro regime through Claw Quant's governed research APIs. Use for 宏观环境、经济周期、PMI、通胀、货币社融、流动性 or macro-to-market questions; do not treat observation-period data as unrevised publication vintages.
---

# Claw Quant Macro Research

Start with the governed contract and keep one cutoff across all calls:

```bash
./clawq research readiness
./clawq research macro-regime --as-of YYYY-MM-DD
./clawq research macro-theme growth --periods 24 --as-of YYYY-MM-DD
./clawq research macro-theme inflation --periods 24 --as-of YYYY-MM-DD
./clawq research macro-theme liquidity --periods 24 --as-of YYYY-MM-DD
```

Read [references/methodology.md](references/methodology.md) before interpreting a regime or
making a historical claim. Begin with component facts, then explain the rule-based regime. Keep
policy interpretation, market transmission, and portfolio implications separate from observed
data. Use the investment calendar for known releases and official external sources for policy
documents or publication timestamps that the API declares missing.

Show the as-of date, latest observation date per series, direction changes, conflicts, revisions
or vintage limitations, and the evidence that could falsify the conclusion. A regime label is a
compact description, not a forecast, causal proof, or allocation instruction.
