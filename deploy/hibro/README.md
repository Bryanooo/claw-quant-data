# Hibro Node Agent packages

This directory contains two versionable Hibro `Agent as Code` source packages:

- `agents/claw-quant-fundamental-research`: macro, industry, company quality, valuation,
  shareholder return, disclosure/governance, event evidence, and thesis synthesis;
- `agents/claw-quant-technical-research`: price/trend, volume/flow, levels/risk, wave/Chan,
  cross-asset, ETF flow, charting, and technical synthesis.

Both agents share the logical `claw-quant-data` and `market-charting` Skills and consume only
`/api/v1/research/*`. The packaged copy keeps each imported Agent revision self-contained; the
authoritative Skill definitions live under `.agents/skills/`.

Set `CLAW_QUANT_API_URL` in the Hibro Node runtime (normally
`http://127.0.0.1:8000/api` on the same host), then import the package directory from Hibro's
“Agent 源码” console or `POST /v1/agent-packages/import`. Hibro compiles the package into an
immutable Revision; updates activate atomically and earlier Revisions remain rollback targets.

Neither package contains a Tushare token, database credential, or write-capable operations tool.
Their workspaces are read-only. Data access and research interpretation remain separate Skills.
