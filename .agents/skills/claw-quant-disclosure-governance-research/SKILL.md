---
name: claw-quant-disclosure-governance-research
description: Build official-evidence ledgers for company disclosures, ownership, governance, litigation, and regulatory risk. Use when a fundamental conclusion depends on announcement text or entity behavior; never treat media summaries or absent local rows as official proof.
---

# Claw Quant Disclosure and Governance Research

Start with `$claw-quant-data` readiness and the stock research pack. Inspect
`external_data_needed` before searching externally. The current research contract does not yet
provide complete announcement text, governance cases, litigation, regulatory actions, or full
point-in-time ownership history.

When official evidence is required, prefer exchange, regulator, court, issuer, and fund-manager
sources. Record publication time, effective period, entity, document type, source URL, and the
specific claim supported. Keep official fact, media narrative, analyst inference, and unresolved
hypothesis separate. `unknown_empty` or missing coverage means unknown, not that an event did not
happen.

Do not scrape or store a source unless the runtime is authorized to do so. If no official source
is accessible, return the exact unresolved evidence request and reduce conclusion confidence.
