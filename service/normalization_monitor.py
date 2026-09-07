"""Read-only operational status for the Tushare standardization layer."""

from __future__ import annotations

from datetime import datetime, timezone

from service.tushare_normalization import NORMALIZATION_CONTRACTS


class NormalizationMonitorService:
    def __init__(self, database):
        self._database = database

    def overview(self) -> dict:
        contracts = NORMALIZATION_CONTRACTS.list()
        api_names = [contract.api_name for contract in contracts]
        tables = [contract.table_name for contract in contracts]
        raw_rows = {
            row["api_name"]: int(row["rows"])
            for row in self._database.fetch_all(
                """
                SELECT api_name, count(*) AS rows
                FROM tushare_raw_record
                WHERE api_name = ANY(%s)
                GROUP BY api_name
                """,
                (api_names,),
            )
        }
        normalized_rows = {
            row["table_name"]: int(row["rows"])
            for row in self._database.fetch_all(
                """
                SELECT relname AS table_name, COALESCE(n_live_tup, 0)::bigint AS rows
                FROM pg_stat_user_tables
                WHERE schemaname='public' AND relname = ANY(%s)
                """,
                (tables,),
            )
        }
        latest_runs = {
            row["api_name"]: row
            for row in self._database.fetch_all(
                """
                SELECT DISTINCT ON (api_name)
                    api_name, status, raw_rows, normalized_rows,
                    quarantined_rows, unknown_fields, missing_fields, created_at
                FROM sys_tushare_normalization_run
                ORDER BY api_name, created_at DESC, normalization_run_id DESC
                """
            )
        }
        errors = {
            row["api_name"]: int(row["errors"])
            for row in self._database.fetch_all(
                """
                SELECT api_name, count(*) AS errors
                FROM sys_tushare_normalization_error
                WHERE resolved_at IS NULL
                GROUP BY api_name
                """
            )
        }
        drift = {
            row["api_name"]: int(row["drift"])
            for row in self._database.fetch_all(
                """
                SELECT api_name, count(*) AS drift
                FROM sys_tushare_schema_drift
                WHERE resolved_at IS NULL AND severity <> 'info'
                GROUP BY api_name
                """
            )
        }

        interfaces = []
        for contract in contracts:
            latest = latest_runs.get(contract.api_name)
            raw_count = raw_rows.get(contract.api_name, 0)
            normalized_count = normalized_rows.get(contract.table_name, 0)
            error_count = errors.get(contract.api_name, 0)
            drift_count = drift.get(contract.api_name, 0)
            if error_count:
                status = "quarantined"
            elif drift_count:
                status = "drift"
            elif raw_count and not latest:
                status = "pending_replay"
            elif latest and latest["status"] == "complete":
                status = "healthy"
            elif raw_count == 0:
                status = "empty"
            else:
                status = "pending"
            interfaces.append(
                {
                    "api_name": contract.api_name,
                    "table": contract.table_name,
                    "status": status,
                    "raw_rows": raw_count,
                    "estimated_normalized_rows": normalized_count,
                    "unresolved_errors": error_count,
                    "unresolved_drift": drift_count,
                    "last_run_at": latest["created_at"] if latest else None,
                    "last_run_status": latest["status"] if latest else None,
                }
            )
        status_counts: dict[str, int] = {}
        for item in interfaces:
            status_counts[item["status"]] = status_counts.get(item["status"], 0) + 1
        return {
            "generated_at": datetime.now(timezone.utc),
            "summary": {
                "interfaces": len(interfaces),
                "raw_rows": sum(item["raw_rows"] for item in interfaces),
                "estimated_normalized_rows": sum(
                    item["estimated_normalized_rows"] for item in interfaces
                ),
                "unresolved_errors": sum(
                    item["unresolved_errors"] for item in interfaces
                ),
                "unresolved_drift": sum(
                    item["unresolved_drift"] for item in interfaces
                ),
                "statuses": status_counts,
            },
            "interfaces": interfaces,
        }

    def drift(
        self,
        *,
        api_name: str | None,
        unresolved_only: bool,
        limit: int,
    ) -> list[dict]:
        conditions = []
        params: list[object] = []
        if api_name:
            conditions.append("api_name=%s")
            params.append(api_name)
        if unresolved_only:
            conditions.append("resolved_at IS NULL")
        where = " WHERE " + " AND ".join(conditions) if conditions else ""
        return self._database.fetch_all(
            """
            SELECT api_name, field_name, drift_type, severity, occurrences,
                   first_seen_at, last_seen_at, resolved_at
            FROM sys_tushare_schema_drift
            """
            + where
            + " ORDER BY last_seen_at DESC, api_name, field_name LIMIT %s",
            (*params, limit),
        )

    def errors(
        self,
        *,
        api_name: str | None,
        unresolved_only: bool,
        limit: int,
    ) -> list[dict]:
        conditions = []
        params: list[object] = []
        if api_name:
            conditions.append("api_name=%s")
            params.append(api_name)
        if unresolved_only:
            conditions.append("resolved_at IS NULL")
        where = " WHERE " + " AND ".join(conditions) if conditions else ""
        return self._database.fetch_all(
            """
            SELECT api_name, request_hash, record_hash, error_code,
                   error_message, attempts, first_seen_at, last_seen_at, resolved_at
            FROM sys_tushare_normalization_error
            """
            + where
            + " ORDER BY last_seen_at DESC, api_name LIMIT %s",
            (*params, limit),
        )
