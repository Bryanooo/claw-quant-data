---
name: claw-quant-data
description: Query governed Claw Quant research contracts with explicit quality, provenance, cutoff, and gap checks. Use before every internal fundamental-data read; do not access lower data, operations, audit, SQL, or collection interfaces.
---

# Claw Quant Data

Set `BASE=${CLAW_QUANT_API_URL:-http://127.0.0.1:8000/api}` and use only
`$BASE/v1/research/*`. Read `/readiness` and `/capabilities`, keep one `as_of`, and preserve
quality, provenance, gaps, and external-data requirements. A non-empty result is not proof of
completeness. Never fall back to SQL or lower namespaces.
