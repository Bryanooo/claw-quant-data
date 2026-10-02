---
name: claw-quant-valuation-shareholder-research
description: Analyze historical and peer valuation, scenario inputs, repurchase execution, dividends, dilution, and total shareholder return evidence. Use for valuation or capital-allocation questions; distinguish announced plans from executed shareholder return.
---

# Claw Quant Valuation and Shareholder Return

Use `$claw-quant-data` and keep one cutoff:

```bash
./clawq research readiness
./clawq research capabilities
./clawq research valuation TS_CODE --lookback-days 730 --as-of YYYY-MM-DD
./clawq research repurchase-progress TS_CODE --as-of YYYY-MM-DD
```

Prefer the company's own history before peer medians. Check business, growth, capital structure,
and accounting comparability before using peers. PE may be meaningless for losses or strong
cycles; consider PB, PS, yield, and lifecycle. DCF or DDM scenarios must disclose forecast period,
growth, margins, discount rate, terminal value, and net debt.

Separate repurchase proposal, approval, implementation, and completion. Use the latest cumulative
execution value rather than summing cumulative notices. Dividends, repurchases, issuance,
unlocking, and share-count changes jointly determine shareholder return. When capabilities report
that dividend or ownership history is incomplete, return a partial capital-allocation conclusion;
never relabel repurchase progress alone as total shareholder return.
