---
name: claw-quant-data
description: Query the governed Claw Quant research API with explicit quality and provenance checks. Use before every fundamental, technical, event, sector, ETF, index, or commodity analysis.
---

# Claw Quant Data

Set `BASE=${CLAW_QUANT_API_URL:-http://127.0.0.1:8000/api}` and use only
`$BASE/v1/research/*`. First read `/readiness`, then `/capabilities`. Treat warning or missing
provenance as a limitation. Never fall back to `/v1/data`, `/v1/ops`, SQL, or a token.

Important resources include macro regime/themes, industry fundamentals/breadth, stock fundamentals,
valuation, technicals, capital flow, repurchase progress, event study, market breadth, sector
rotation, investment calendar, and multi-asset instrument technicals. Use the macro and industry
specialists for their respective scopes, and the ETF-flow specialist for creations, redemptions,
exposure rotation, or state-team questions. Preserve `as_of` and method details in every conclusion.
