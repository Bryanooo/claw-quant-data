"""Fixed-query repository for cross-sectional research derivations."""

from __future__ import annotations

from datetime import date

from psycopg2 import sql

from service.collection_jobs.resolution import unresolved_failure_predicate


_SECTOR_TABLES = {
    "ths": ("ths_daily", "pct_change", "vol", "date"),
    "dc": ("dc_daily", "pct_change", "vol", "compact"),
    "tdx": ("tdx_daily", "pct_change", "vol", "compact"),
}


class ResearchRepository:
    def __init__(self, database):
        self._database = database

    def market_breadth(self, as_of: date) -> dict | None:
        return self._database.fetch_one(
            """
            WITH target AS (
                SELECT max(trade_date) AS trade_date
                FROM daily
                WHERE trade_date <= %s
            ), current_day AS MATERIALIZED (
                SELECT d.*
                FROM daily AS d
                JOIN target AS t ON t.trade_date = d.trade_date
            ), moving AS (
                SELECT current_day.ts_code,
                       avg(history.close) FILTER (
                           WHERE history.observation_rank <= 20
                       ) AS ma20,
                       avg(history.close) AS ma60
                FROM current_day
                CROSS JOIN target
                LEFT JOIN LATERAL (
                    SELECT recent.close,
                           row_number() OVER (
                               ORDER BY recent.trade_date DESC
                           ) AS observation_rank
                    FROM (
                        SELECT d.trade_date, d.close
                        FROM daily AS d
                        WHERE d.ts_code=current_day.ts_code
                          AND d.trade_date <= target.trade_date
                        ORDER BY d.trade_date DESC
                        LIMIT 60
                    ) AS recent
                ) AS history ON TRUE
                GROUP BY current_day.ts_code
            ), limits AS (
                SELECT count(*) FILTER (WHERE l."limit" = 'U') AS limit_up,
                       count(*) FILTER (WHERE l."limit" = 'D') AS limit_down,
                       count(*) FILTER (WHERE l.open_times > 0) AS opened_limits
                FROM limit_list_d AS l
                JOIN target AS t ON l.trade_date = to_char(t.trade_date, 'YYYYMMDD')
            )
            SELECT t.trade_date,
                   count(*) AS securities,
                   count(*) FILTER (WHERE c.close > c.pre_close) AS advancing,
                   count(*) FILTER (WHERE c.close < c.pre_close) AS declining,
                   count(*) FILTER (WHERE c.close = c.pre_close) AS unchanged,
                   avg(c.pct_chg) AS average_return_pct,
                   percentile_cont(0.5) WITHIN GROUP (ORDER BY c.pct_chg)
                       AS median_return_pct,
                   sum(c.amount) AS amount,
                   count(*) FILTER (WHERE c.close > m.ma20) AS above_ma20,
                   count(*) FILTER (WHERE c.close > m.ma60) AS above_ma60,
                   COALESCE(max(l.limit_up), 0) AS limit_up,
                   COALESCE(max(l.limit_down), 0) AS limit_down,
                   COALESCE(max(l.opened_limits), 0) AS opened_limits
            FROM target AS t
            JOIN current_day AS c ON TRUE
            LEFT JOIN moving AS m ON m.ts_code = c.ts_code
            LEFT JOIN limits AS l ON TRUE
            GROUP BY t.trade_date
            """,
            (as_of,),
        )

    def backfill_statuses(self, prefix: str = "research-backfill-v1") -> dict[str, dict]:
        unresolved_jobs = unresolved_failure_predicate("job")
        jobs = self._database.fetch_all(
            f"""
            SELECT split_part(job.idempotency_key, ':', 2) AS group_name,
                   count(*)::INTEGER AS total,
                   count(*) FILTER (
                       WHERE status IN ('queued', 'running', 'retrying')
                   )::INTEGER AS active,
                   count(*) FILTER (
                       WHERE {unresolved_jobs}
                   )::INTEGER AS unresolved,
                   count(*) FILTER (
                       WHERE status='success'
                         AND completion_status IN ('complete', 'empty')
                   )::INTEGER AS complete
            FROM sys_collection_job AS job
            WHERE job.idempotency_key LIKE %s
            GROUP BY group_name
            """,
            (f"{prefix}:%",),
        )
        campaigns = self._database.fetch_all(
            """
            SELECT split_part(idempotency_key, ':', 2) AS group_name,
                   count(*)::INTEGER AS total,
                   count(*) FILTER (
                       WHERE status='running'
                   )::INTEGER AS active,
                   count(*) FILTER (
                       WHERE status IN ('paused', 'attention')
                         AND superseded_by_campaign_id IS NULL
                   )::INTEGER AS unresolved,
                   count(*) FILTER (
                       WHERE status='success'
                         AND completion_status IN ('complete', 'empty')
                   )::INTEGER AS complete
            FROM sys_collection_fanout_campaign
            WHERE idempotency_key LIKE %s
            GROUP BY group_name
            """,
            (f"{prefix}:%",),
        )
        states: dict[str, dict] = {}
        for source, rows in (("jobs", jobs), ("campaigns", campaigns)):
            for row in rows:
                group = row["group_name"]
                state = states.setdefault(
                    group,
                    {
                        "jobs": 0,
                        "campaigns": 0,
                        "active": 0,
                        "unresolved": 0,
                        "completed": 0,
                    },
                )
                state[source] = int(row["total"] or 0)
                state["active"] += int(row["active"] or 0)
                state["unresolved"] += int(row["unresolved"] or 0)
                state["completed"] += int(row["complete"] or 0)
        for state in states.values():
            total = state["jobs"] + state["campaigns"]
            if state["unresolved"]:
                status = "attention"
            elif state["active"]:
                status = "running"
            elif total and state["completed"] == total:
                status = "complete"
            elif total:
                status = "incomplete"
            else:  # pragma: no cover - a grouped row always has at least one record
                status = "planned"
            state["status"] = status
        return states

    def sector_rotation(
        self,
        provider: str,
        *,
        as_of: date,
        lookback_days: int,
        limit: int,
        allowed_codes: list[str],
    ) -> list[dict]:
        table, pct_column, activity_column, date_storage = _SECTOR_TABLES[provider]
        trade_date = (
            sql.SQL("to_date({column}, 'YYYYMMDD')").format(
                column=sql.Identifier("trade_date")
            )
            if date_storage == "compact"
            else sql.Identifier("trade_date")
        )
        statement = sql.SQL(
            """
            WITH target AS (
                SELECT max({trade_date}) AS trade_date
                FROM {table}
                WHERE {trade_date} <= %s
            ), observations AS (
                SELECT d.ts_code, {dated_trade_date} AS trade_date, d.close,
                       d.{activity_column} AS activity,
                       d.{pct_column} AS daily_return,
                       row_number() OVER (
                           PARTITION BY d.ts_code ORDER BY {dated_trade_date} DESC
                       ) AS newest_rank,
                       row_number() OVER (
                           PARTITION BY d.ts_code ORDER BY {dated_trade_date} ASC
                       ) AS oldest_rank
                FROM {table} AS d
                CROSS JOIN target AS t
                WHERE {dated_trade_date} BETWEEN t.trade_date - (%s * INTERVAL '1 day')
                                             AND t.trade_date
                  AND d.ts_code = ANY(%s)
            ), aggregated AS (
                SELECT ts_code,
                       max(trade_date) AS trade_date,
                       max(close) FILTER (WHERE newest_rank = 1) AS close,
                       max(close) FILTER (WHERE oldest_rank = 1) AS start_close,
                       avg(activity) AS average_volume,
                       avg(daily_return) AS average_daily_return,
                       count(*) AS observations,
                       CASE
                           WHEN count(daily_return) > 0
                            AND bool_and(daily_return > -100)
                           THEN (
                               exp(sum(ln(1 + daily_return / 100))) - 1
                           ) * 100
                       END AS period_return_pct
                FROM observations
                GROUP BY ts_code
            )
            SELECT ts_code, trade_date, close, start_close, average_volume,
                   average_daily_return, observations, period_return_pct
            FROM aggregated
            WHERE observations >= 2
            ORDER BY period_return_pct DESC NULLS LAST, ts_code
            LIMIT %s
            """
        ).format(
            table=sql.Identifier(table),
            pct_column=sql.Identifier(pct_column),
            activity_column=sql.Identifier(activity_column),
            trade_date=trade_date,
            dated_trade_date=(
                sql.SQL("to_date(d.{column}, 'YYYYMMDD')").format(
                    column=sql.Identifier("trade_date")
                )
                if date_storage == "compact"
                else sql.SQL("d.{column}").format(column=sql.Identifier("trade_date"))
            ),
        )
        return self._database.fetch_all(
            statement,
            (as_of, lookback_days, allowed_codes, limit),
        )
