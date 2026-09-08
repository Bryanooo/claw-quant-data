---
name: claw-quant-data
description: Query and assess the running claw-quant-data service through its read-only clawq CLI. Use for stock, fund, index, financial, market, freshness, coverage, dataset-discovery, or data-health questions backed by this repository; do not use it as authorization to manage collection jobs or access PostgreSQL directly.
---

# Claw Quant Data

Use the repository's public REST contract through `./clawq`. Do not couple answers to
physical tables, raw SQL, or undocumented response fields.

## Query workflow

1. Run `./clawq health`. If the API is unavailable, report the failure and its JSON
   `error.code`; do not silently switch to PostgreSQL.
2. Run `./clawq status` before making claims about current or complete data. Inspect
   issues relevant to the requested resource. A global `critical` status does not make
   every unrelated dataset unusable.
3. Discover the resource with `./clawq datasets list`, then run
   `./clawq datasets describe <dataset>`. Use only filters and date fields declared by
   that contract.
4. For time-bounded conclusions, check `./clawq freshness <dataset>` and
   `./clawq coverage show <dataset>`. Distinguish confirmed `missing` or `partial`
   partitions from unknown or unaudited coverage.
5. Start with a small query. Follow the response's `page.has_more`, `limit`, and
   `offset` values when more rows are necessary. Request `--include-total` only when an
   exact count materially helps because it can be expensive on large datasets.
6. State the dataset, requested date range, latest available partition, and any
   relevant health or coverage limitation in the answer.

For a single-stock multi-role research workflow, prefer
`./clawq stock research-pack <TS_CODE>` as the first bounded data read after health
checks. Inspect `meta.provenance`, `meta.gaps`, and `meta.external_data_needed`; use
individual dataset queries only to drill into a section or paginate beyond the pack.
Treat `ownership_and_events.related_news` as keyword-matched media material, not an
official filing; use the declared external-data gap to retrieve exchange/company
announcements from an official source.
Never present the pack itself as a rating or trading recommendation.

Use `./clawq interfaces describe <api_name>` and `interfaces query` when the request is
about a Tushare interface contract or normalized interface records rather than a named
public dataset. Never guess an interface's input fields.

## Boundaries

- The CLI is read-only. Do not create, retry, cancel, initialize, or delete collection
  work unless the user separately requests that state change. Management operations
  belong to the Dashboard or management API and require the product's confirmation
  flow.
- Do not reveal `.env`, tokens, database passwords, or connection strings in commands
  or responses.
- Do not treat `never_collected`, optional, or unaudited resources as confirmed data
  loss without the corresponding evidence.
- For factor calculation, research pipelines, or backtests, use this service as the
  source of governed data; keep strategy and derived-research logic outside this data
  service unless the user explicitly asks to extend it.
- For CLI flags, output formats, pagination, and exit codes, read
  [the CLI contract](../../../docs/CLI.md). Read the main
  [project overview](../../../README.md) only when architectural context is needed.
