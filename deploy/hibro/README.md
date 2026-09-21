# Hibro Node Agent packages

`agents/claw-quant-research` is a versionable Hibro `Agent as Code` source package. It keeps
investment agents outside the data service while consuming only `/api/v1/research/*`.

Set `CLAW_QUANT_API_URL` in the Hibro Node runtime (normally
`http://127.0.0.1:8000/api` on the same host), then import the package directory from Hibro's
“Agent 源码” console or `POST /v1/agent-packages/import`. Hibro compiles the package into an
immutable Revision; updates activate atomically and earlier Revisions remain rollback targets.

The package does not contain a Tushare token, database credential, or write-capable operations
tool. Its workspace is read-only and its skills are pure research contracts.
