"""PostgreSQL repository for intraday facts, conclusions and watch settings."""

from __future__ import annotations

from datetime import date, datetime
import json
from typing import Any

import psycopg2.extras


def _json(value: Any) -> psycopg2.extras.Json:
    # Provider timestamps and Decimal-like values must never make an otherwise
    # valid observation transaction fail during evidence serialization.
    return psycopg2.extras.Json(value, dumps=lambda item: json.dumps(item, default=str))


class IntradayRepository:
    def __init__(self, database):
        self._database = database

    def claim_run(self, scheduled_for: datetime, trigger_source: str) -> int | None:
        row = self._database.execute_one(
            """
            INSERT INTO sys_intraday_collection_run
                (scheduled_for, status, trigger_source)
            VALUES (%s, 'running', %s)
            ON CONFLICT (scheduled_for) DO NOTHING
            RETURNING run_id
            """,
            (scheduled_for, trigger_source),
        )
        return int(row["run_id"]) if row else None

    def observed_watchlist(self) -> list[dict]:
        return self._database.fetch_all(
            """
            SELECT watchlist.ts_code AS symbol, basic.name, basic.industry,
                   watchlist.observation_profile
            FROM sys_stock_watchlist AS watchlist
            JOIN stock_basic AS basic USING (ts_code)
            WHERE watchlist.intraday_observation_enabled
              AND (watchlist.observation_muted_until IS NULL
                   OR watchlist.observation_muted_until <= NOW())
              AND basic.list_status='L'
            ORDER BY watchlist.sort_order, watchlist.ts_code
            LIMIT 160
            """
        )

    def watchlist_samples(self, *, limit: int = 3) -> list[dict]:
        return self._database.fetch_all(
            """
            SELECT watchlist.ts_code AS symbol, basic.name, basic.industry,
                   watchlist.observation_profile
            FROM sys_stock_watchlist AS watchlist
            JOIN stock_basic AS basic USING (ts_code)
            WHERE basic.list_status='L'
            ORDER BY watchlist.sort_order, watchlist.ts_code
            LIMIT %s
            """,
            (limit,),
        )

    def random_stock_samples(
        self,
        *,
        limit: int = 30,
        seed: str = "intraday-validation-v1",
        listed_before: date,
    ) -> list[dict]:
        """Return a deterministic random sample with enough listing history."""

        return self._database.fetch_all(
            """
            SELECT ts_code AS symbol, name, industry, 'balanced' AS observation_profile
            FROM stock_basic
            WHERE list_status='L'
              AND ts_code ~ '^[0-9]{6}\\.(SH|SZ)$'
              AND NULLIF(list_date, '') IS NOT NULL
              AND to_date(list_date, 'YYYYMMDD') <= %s
            ORDER BY md5(ts_code || %s), ts_code
            LIMIT %s
            """,
            (listed_before, seed, limit),
        )

    def recent_trade_days(self, *, before: date, limit: int) -> list[date]:
        rows = self._database.fetch_all(
            """
            SELECT cal_date FROM trade_cal
            WHERE exchange='SSE' AND is_open=1 AND cal_date < %s
            ORDER BY cal_date DESC LIMIT %s
            """,
            (before, limit),
        )
        return [row["cal_date"] for row in rows]

    def complete_validation_days(
        self,
        *,
        days: list[date],
        watch_symbols: set[str],
    ) -> set[date]:
        """Find days already complete for the exact validation universe."""

        if not days or not watch_symbols:
            return set()
        rows = self._database.fetch_all(
            """
            WITH requested(day) AS (SELECT unnest(%s::date[])),
            suspended AS (
                SELECT trade_date AS day, COUNT(DISTINCT ts_code) AS symbols
                FROM suspend_d
                WHERE trade_date=ANY(%s) AND ts_code=ANY(%s)
                  AND suspend_type='S'
                GROUP BY trade_date
            ),
            bar_counts AS (
                SELECT (bar_time AT TIME ZONE 'Asia/Shanghai')::date AS day,
                       COUNT(DISTINCT symbol) FILTER (
                           WHERE scope_type='etf' AND bar_count=242
                       ) AS etfs,
                       COUNT(DISTINCT symbol) FILTER (
                           WHERE scope_type='index' AND bar_count=242
                       ) AS indices,
                       COUNT(DISTINCT symbol) FILTER (
                           WHERE scope_type='industry' AND bar_count=242
                       ) AS industries,
                       COUNT(DISTINCT symbol) FILTER (
                           WHERE scope_type='stock' AND symbol=ANY(%s) AND bar_count=242
                       ) AS stocks
                FROM (
                    SELECT symbol, scope_type, bar_time,
                           COUNT(*) OVER (
                               PARTITION BY symbol,
                               (bar_time AT TIME ZONE 'Asia/Shanghai')::date
                           ) AS bar_count
                    FROM intraday_quote_bar
                    WHERE period='P_Min1'
                      AND (bar_time AT TIME ZONE 'Asia/Shanghai')::date=ANY(%s)
                ) bars
                GROUP BY 1
            ),
            analysis_counts AS (
                SELECT (as_of AT TIME ZONE 'Asia/Shanghai')::date AS day,
                       COUNT(*) FILTER (WHERE scope_type='market') AS market_rows,
                       COUNT(*) FILTER (WHERE scope_type='etf') AS etf_rows,
                       COUNT(*) FILTER (WHERE scope_type='index') AS index_rows,
                       COUNT(*) FILTER (
                           WHERE scope_type='stock' AND scope_code=ANY(%s)
                       ) AS stock_rows
                FROM intraday_analysis_snapshot
                WHERE (as_of AT TIME ZONE 'Asia/Shanghai')::date=ANY(%s)
                GROUP BY 1
            )
            SELECT requested.day
            FROM requested
            JOIN bar_counts USING (day)
            JOIN analysis_counts USING (day)
            LEFT JOIN suspended USING (day)
            WHERE etfs=4 AND indices=2 AND industries=31
              AND stocks=%s-COALESCE(suspended.symbols, 0)
              AND market_rows=4 AND etf_rows=16 AND index_rows=8
              AND stock_rows=(%s-COALESCE(suspended.symbols, 0))*4
            """,
            (
                days, days, list(watch_symbols),
                list(watch_symbols), days,
                list(watch_symbols), days,
                len(watch_symbols), len(watch_symbols),
            ),
        )
        return {row["day"] for row in rows}

    def load_history_day(self, day: date, watchlist: list[dict]) -> dict:
        quote_rows = self._database.fetch_all(
            """
            SELECT symbol, bar_time, period, scope_type, name, open, high, low,
                   close, previous_close, volume, amount, pct_chg,
                   trade_status, limit_status, payload
            FROM intraday_quote_bar
            WHERE period='P_Min1'
              AND bar_time >= (%s::date::timestamp AT TIME ZONE 'Asia/Shanghai')
              AND bar_time < ((%s::date + 1)::timestamp AT TIME ZONE 'Asia/Shanghai')
            ORDER BY symbol, bar_time
            """,
            (day, day),
        )
        flow_rows = self._database.fetch_all(
            """
            SELECT symbol, snapshot_time, period, main_in, main_out,
                   main_net_inflow, retail_net_in, total_net_in, payload
            FROM intraday_flow_snapshot
            WHERE snapshot_time >= (%s::date::timestamp AT TIME ZONE 'Asia/Shanghai')
              AND snapshot_time < ((%s::date + 1)::timestamp AT TIME ZONE 'Asia/Shanghai')
            ORDER BY snapshot_time
            """,
            (day, day),
        )
        watch_symbols = {str(row["symbol"]) for row in watchlist}
        return {
            "day": day,
            "quote_rows": quote_rows,
            "flow_rows": flow_rows,
            "flow_source": [dict(row["payload"]) for row in flow_rows],
            "proxy_symbols": {"510300.SH", "512100.SH", "588000.SH", "159915.SZ"},
            "index_symbols": {"399001.SZ", "399006.SZ"},
            "industry_symbols": {row["symbol"] for row in quote_rows if row["scope_type"] == "industry"},
            "watch_symbols": watch_symbols,
            "expected_proxies": 4,
            "expected_sectors": 31,
            "missing_symbols": [],
            "usage": {"outer_calls": 0, "subrequests": 0, "fetched_rows": 0},
        }

    def clear_historical_replay(self, day: date) -> int:
        with self._database.writable_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    DELETE FROM sys_intraday_collection_run
                    WHERE trigger_source='historical_backfill'
                      AND scheduled_for >= (%s::date::timestamp AT TIME ZONE 'Asia/Shanghai')
                      AND scheduled_for < ((%s::date + 1)::timestamp AT TIME ZONE 'Asia/Shanghai')
                    """,
                    (day, day),
                )
                return cursor.rowcount

    def set_watchlist_observation(
        self,
        symbol: str,
        *,
        enabled: bool,
        profile: str = "balanced",
    ) -> dict | None:
        return self._database.execute_one(
            """
            UPDATE sys_stock_watchlist
            SET intraday_observation_enabled=%s,
                observation_profile=%s,
                observation_enabled_at=CASE
                    WHEN %s THEN COALESCE(observation_enabled_at, NOW())
                    ELSE NULL
                END,
                updated_at=NOW()
            WHERE ts_code=%s
            RETURNING ts_code, intraday_observation_enabled,
                      observation_profile, observation_enabled_at,
                      observation_muted_until
            """,
            (enabled, profile, enabled, symbol),
        )

    def persist(
        self,
        *,
        run_id: int,
        quote_rows: list[dict],
        flow_rows: list[dict],
        analyses: list[dict],
        usage: dict,
        evidence: dict,
    ) -> None:
        with self._database.writable_connection() as connection:
            with connection.cursor() as cursor:
                if quote_rows:
                    psycopg2.extras.execute_values(
                        cursor,
                        """
                        INSERT INTO intraday_quote_bar (
                            symbol, bar_time, period, scope_type, name,
                            open, high, low, close, previous_close, volume,
                            amount, pct_chg, trade_status, limit_status,
                            run_id, payload
                        ) VALUES %s
                        ON CONFLICT (symbol, bar_time, period) DO UPDATE SET
                            open=EXCLUDED.open, high=EXCLUDED.high,
                            low=EXCLUDED.low, close=EXCLUDED.close,
                            previous_close=EXCLUDED.previous_close,
                            volume=EXCLUDED.volume, amount=EXCLUDED.amount,
                            pct_chg=EXCLUDED.pct_chg,
                            trade_status=EXCLUDED.trade_status,
                            limit_status=EXCLUDED.limit_status,
                            run_id=EXCLUDED.run_id, payload=EXCLUDED.payload,
                            collected_at=NOW()
                        """,
                        [(
                            row["symbol"], row["bar_time"], row["period"],
                            row["scope_type"], row.get("name"), row.get("open"),
                            row.get("high"), row.get("low"), row.get("close"),
                            row.get("previous_close"), row.get("volume"),
                            row.get("amount"), row.get("pct_chg"),
                            row.get("trade_status"), row.get("limit_status"),
                            run_id, _json(row.get("payload", {})),
                        ) for row in quote_rows],
                        page_size=1000,
                    )
                if flow_rows:
                    psycopg2.extras.execute_values(
                        cursor,
                        """
                        INSERT INTO intraday_flow_snapshot (
                            symbol, snapshot_time, period, main_in, main_out,
                            main_net_inflow, retail_net_in, total_net_in,
                            run_id, payload
                        ) VALUES %s
                        ON CONFLICT (symbol, snapshot_time, period) DO UPDATE SET
                            main_in=EXCLUDED.main_in,
                            main_out=EXCLUDED.main_out,
                            main_net_inflow=EXCLUDED.main_net_inflow,
                            retail_net_in=EXCLUDED.retail_net_in,
                            total_net_in=EXCLUDED.total_net_in,
                            run_id=EXCLUDED.run_id, payload=EXCLUDED.payload,
                            collected_at=NOW()
                        """,
                        [(
                            row["symbol"], row["snapshot_time"], row["period"],
                            row.get("main_in"), row.get("main_out"),
                            row.get("main_net_inflow"), row.get("retail_net_in"),
                            row.get("total_net_in"), run_id,
                            _json(row.get("payload", {})),
                        ) for row in flow_rows],
                        page_size=1000,
                    )
                for item in analyses:
                    cursor.execute(
                        """
                        INSERT INTO intraday_analysis_snapshot (
                            run_id, as_of, scope_type, scope_code, scope_name,
                            state, score, confidence, conclusion, metrics,
                            signals, evidence, data_quality, rule_version
                        ) VALUES (
                            %(run_id)s, %(as_of)s, %(scope_type)s,
                            %(scope_code)s, %(scope_name)s, %(state)s,
                            %(score)s, %(confidence)s, %(conclusion)s,
                            %(metrics)s, %(signals)s, %(evidence)s,
                            %(data_quality)s, %(rule_version)s
                        )
                        ON CONFLICT (run_id, scope_type, scope_code) DO UPDATE SET
                            state=EXCLUDED.state, score=EXCLUDED.score,
                            confidence=EXCLUDED.confidence,
                            conclusion=EXCLUDED.conclusion,
                            metrics=EXCLUDED.metrics, signals=EXCLUDED.signals,
                            evidence=EXCLUDED.evidence,
                            data_quality=EXCLUDED.data_quality
                        """,
                        {
                            **item,
                            "run_id": run_id,
                            "metrics": _json(item["metrics"]),
                            "signals": _json(item["signals"]),
                            "evidence": _json(item["evidence"]),
                            "data_quality": _json(item["data_quality"]),
                        },
                    )
                cursor.execute(
                    """
                    UPDATE sys_intraday_collection_run
                    SET status=%s, completed_at=NOW(), outer_calls=%s,
                        subrequests=%s, fetched_rows=%s, stored_rows=%s,
                        evidence=%s
                    WHERE run_id=%s
                    """,
                    (
                        "success" if all(a["data_quality"]["status"] == "complete" for a in analyses) else "attention",
                        usage["outer_calls"], usage["subrequests"],
                        usage["fetched_rows"], len(quote_rows) + len(flow_rows) + len(analyses),
                        _json(evidence), run_id,
                    ),
                )

    def fail_run(self, run_id: int, error: Exception, usage: dict) -> None:
        self._database.execute_one(
            """
            UPDATE sys_intraday_collection_run
            SET status='failed', completed_at=NOW(), outer_calls=%s,
                subrequests=%s, fetched_rows=%s, error_message=%s
            WHERE run_id=%s
            RETURNING run_id
            """,
            (
                usage.get("outer_calls", 0), usage.get("subrequests", 0),
                usage.get("fetched_rows", 0), str(error)[:2000], run_id,
            ),
        )

    def overview(self, *, history_limit: int = 24) -> dict:
        latest = self._database.fetch_all(
            """
            SELECT DISTINCT ON (scope_type, scope_code)
                   analysis_id, run_id, as_of, scope_type, scope_code,
                   scope_name, state, score, confidence, conclusion, metrics,
                   signals, evidence, data_quality, rule_version
            FROM intraday_analysis_snapshot
            ORDER BY scope_type, scope_code, as_of DESC, analysis_id DESC
            """
        )
        history = self._database.fetch_all(
            """
            SELECT as_of, state, score, confidence, conclusion, metrics,
                   signals, evidence, data_quality
            FROM intraday_analysis_snapshot
            WHERE scope_type='market' AND scope_code='CN_A_SHARE'
            ORDER BY as_of DESC, analysis_id DESC
            LIMIT %s
            """,
            (history_limit,),
        )
        instrument_history = self._database.fetch_all(
            """
            SELECT as_of, scope_type, scope_code, scope_name, state, score,
                   confidence, conclusion, metrics, signals, data_quality,
                   rule_version
            FROM intraday_analysis_snapshot
            WHERE scope_type IN ('stock', 'etf', 'index')
            ORDER BY as_of DESC, analysis_id DESC
            LIMIT 500
            """
        )
        validation_summary = self._database.fetch_all(
            """
            WITH validation_days AS (
                SELECT DISTINCT (scheduled_for AT TIME ZONE 'Asia/Shanghai')::date AS trade_day
                FROM sys_intraday_collection_run
                WHERE trigger_source='historical_backfill' AND status IN ('success', 'attention')
                ORDER BY trade_day DESC
                LIMIT 30
            )
            SELECT scope_code, MAX(scope_name) AS scope_name,
                   COUNT(DISTINCT (as_of AT TIME ZONE 'Asia/Shanghai')::date) AS days,
                   COUNT(*) AS checkpoints,
                   COUNT(*) FILTER (WHERE state='strong_uptrend') AS strong_uptrend,
                   COUNT(*) FILTER (WHERE state='uptrend') AS uptrend,
                   COUNT(*) FILTER (WHERE state='range') AS range_count,
                   COUNT(*) FILTER (WHERE state='downtrend') AS downtrend,
                   COUNT(*) FILTER (WHERE state='strong_downtrend') AS strong_downtrend,
                   COUNT(*) FILTER (WHERE metrics->>'event_state'='leading_reversal') AS reversals,
                   COUNT(*) FILTER (WHERE metrics->>'event_state'='relative_strength') AS relative_strength,
                   COUNT(*) FILTER (WHERE metrics->>'event_state'='relative_weakness') AS relative_weakness,
                   COUNT(*) FILTER (WHERE data_quality->>'status'<>'complete') AS incomplete,
                   MIN(as_of) AS first_at, MAX(as_of) AS last_at
            FROM intraday_analysis_snapshot
            WHERE scope_type='stock'
              AND (as_of AT TIME ZONE 'Asia/Shanghai')::date IN (SELECT trade_day FROM validation_days)
            GROUP BY scope_code
            ORDER BY scope_code
            """
        )
        run = self._database.fetch_one(
            """
            SELECT run_id, scheduled_for, status, trigger_source, started_at,
                   completed_at, outer_calls, subrequests, fetched_rows,
                   stored_rows, error_message, evidence
            FROM sys_intraday_collection_run
            ORDER BY scheduled_for DESC LIMIT 1
            """
        )
        watchlist = self._database.fetch_all(
            """
            SELECT watchlist.ts_code, basic.name,
                   watchlist.intraday_observation_enabled,
                   watchlist.observation_profile,
                   watchlist.observation_muted_until
            FROM sys_stock_watchlist AS watchlist
            JOIN stock_basic AS basic USING (ts_code)
            ORDER BY watchlist.sort_order, watchlist.ts_code
            """
        )
        return {
            "schema_version": "claw-data.intraday-overview/v1",
            "cadence_minutes": 15,
            "latest": latest,
            "market_history": history,
            "instrument_history": instrument_history,
            "validation_summary": validation_summary,
            "last_run": run,
            "watchlist": watchlist,
        }
