---
name: claw-quant-data
description: Query governed stock, sector, market, event, fundamental, valuation, technical, and capital-flow research through the read-only clawq research contract. Use only the public research namespace; do not access lower data, operations, audit, PostgreSQL, or collection-management interfaces.
---

# Claw Quant Data

Use only the repository's public Agent contract under `/api/v1/research/*` through
`./clawq`. Do not couple answers to physical tables, raw SQL, lower service layers, or
undocumented response fields.

## Query workflow

1. Run `./clawq research readiness`. If the API is unavailable, report the failure and
   its JSON `error.code`; do not silently switch to PostgreSQL or another namespace.
2. Run `./clawq research capabilities` to confirm that the requested method is served
   and to identify declared data or source gaps.
3. Use the narrowest research command: a stock or sector research pack for context,
   then a deterministic fundamental, valuation, technical, capital-flow, event-study,
   repurchase-progress, instrument-technicals, market-breadth, sector-rotation, or
   investment-calendar command as needed.
4. Pass `--as-of` for historical research whenever the command supports it. Inspect
   `meta.quality`, `meta.provenance`, `meta.gaps`, and `external_data_needed` instead of
   inferring completeness from a non-empty response.
5. State the requested date or historical cutoff, the research method, provenance,
   and relevant readiness or quality limitations in the answer.

For a single-stock multi-role research workflow, prefer
`./clawq stock research-pack <TS_CODE>` as the first bounded data read after readiness
checks. Inspect `meta.provenance`, `meta.gaps`, and `meta.external_data_needed`; use
individual dataset queries only to drill into a section or paginate beyond the pack.
Treat `ownership_and_events.related_news` as keyword-matched media material, not an
official filing; use the declared external-data gap to retrieve exchange/company
announcements from an official source.
Never present the pack itself as a rating or trading recommendation.

For important macroeconomic releases and derivatives dates, use
`./clawq research calendar` or `./clawq research calendar-day` and preserve the event's
source, release status, previous value, forecast, and actual value.

## Boundaries

- The public Agent surface is `/api/v1/research/*` only. Lower data, operations, and
  audit namespaces are not Agent fallbacks, even when they are read-only.
- The CLI is read-only. Do not create, retry, cancel, initialize, or delete collection
  work. Management belongs to the Dashboard and its confirmation flow.
- Do not reveal `.env`, tokens, database passwords, or connection strings in commands
  or responses.
- Do not treat `never_collected`, optional, or unaudited resources as confirmed data
  loss without the corresponding evidence.
- If a needed capability is absent from `research capabilities`, report the declared
  gap instead of assembling an undocumented result from lower-layer records.
- Keep strategy, factor pipelines, backtests, and portfolio logic outside this data
  service unless the user explicitly asks to extend the research contract.
- For CLI flags, output formats, pagination, and exit codes, read
  [the CLI contract](../../../docs/CLI.md). Read the main
  [project overview](../../../README.md) only when architectural context is needed.
