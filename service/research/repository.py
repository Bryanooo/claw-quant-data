"""Fixed-query repository for cross-sectional research derivations."""

from __future__ import annotations

from datetime import date
from threading import Lock
from time import monotonic

from psycopg2 import sql



_SECTOR_TABLES = {
    "ths": ("ths_daily", "pct_change", "vol", "date"),
    "dc": ("dc_daily", "pct_change", "vol", "compact"),
    "tdx": ("tdx_daily", "pct_change", "vol", "compact"),
}

_TECHNICAL_SCREEN_CACHE_SECONDS = 60.0
_TECHNICAL_SCREEN_CACHE: dict[date, tuple[float, dict]] = {}
_TECHNICAL_SCREEN_CACHE_LOCK = Lock()


class ResearchRepository:
    def __init__(self, database):
        self._database = database

    def search_stocks(self, query: str, *, limit: int = 20) -> list[dict]:
        """Search the security master by code, name, full name or pinyin."""

        normalized = query.strip()
        pattern = f"%{normalized}%"
        prefix = f"{normalized}%"
        return self._database.fetch_all(
            """
            SELECT ts_code, symbol, name, fullname, area, industry, market,
                   exchange, list_status, list_date, delist_date
            FROM stock_basic
            WHERE ts_code ILIKE %s
               OR symbol ILIKE %s
               OR name ILIKE %s
               OR fullname ILIKE %s
               OR cnspell ILIKE %s
            ORDER BY
                CASE
                    WHEN upper(ts_code)=upper(%s) OR symbol=%s OR name=%s THEN 0
                    WHEN ts_code ILIKE %s OR symbol ILIKE %s
                      OR name ILIKE %s OR cnspell ILIKE %s THEN 1
                    ELSE 2
                END,
                CASE WHEN list_status='L' THEN 0 ELSE 1 END,
                ts_code
            LIMIT %s
            """,
            (
                pattern, pattern, pattern, pattern, pattern,
                normalized, normalized, normalized,
                prefix, prefix, prefix, prefix,
                limit,
            ),
        )

    def stock_watchlist(self) -> list[dict]:
        """Return durable dashboard favourites with security-master metadata."""

        return self._database.fetch_all(
            """
            SELECT watchlist.ts_code, basic.symbol, basic.name, basic.fullname,
                   basic.area, basic.industry, basic.market, basic.exchange,
                   basic.list_status, basic.list_date, basic.delist_date,
                   watchlist.sort_order, watchlist.added_at
            FROM sys_stock_watchlist AS watchlist
            JOIN stock_basic AS basic USING (ts_code)
            ORDER BY watchlist.sort_order, watchlist.added_at, watchlist.ts_code
            """
        )

    def add_stock_watchlist(self, ts_code: str) -> dict | None:
        """Idempotently add one known stock and return its display metadata."""

        return self._database.execute_one(
            """
            WITH saved AS (
                INSERT INTO sys_stock_watchlist (ts_code, sort_order)
                SELECT basic.ts_code,
                       COALESCE((SELECT max(sort_order) + 1
                                 FROM sys_stock_watchlist), 0)
                FROM stock_basic AS basic
                WHERE basic.ts_code=%s
                ON CONFLICT (ts_code) DO UPDATE
                SET updated_at=NOW()
                RETURNING ts_code, sort_order, added_at
            )
            SELECT saved.ts_code, basic.symbol, basic.name, basic.fullname,
                   basic.area, basic.industry, basic.market, basic.exchange,
                   basic.list_status, basic.list_date, basic.delist_date,
                   saved.sort_order, saved.added_at
            FROM saved
            JOIN stock_basic AS basic USING (ts_code)
            """,
            (ts_code,),
        )

    def remove_stock_watchlist(self, ts_code: str) -> dict | None:
        """Remove one favourite without touching any market data."""

        return self._database.execute_one(
            """
            DELETE FROM sys_stock_watchlist
            WHERE ts_code=%s
            RETURNING ts_code
            """,
            (ts_code,),
        )

    def fund_ownership_history(
        self,
        ts_code: str,
        *,
        start_date: date,
        as_of: date,
        periods: int = 8,
    ) -> list[dict]:
        """Aggregate point-in-time fund ownership without a row-count cap.

        ``fund_portfolio`` can contain tens of thousands of fund-position rows
        for one widely held stock.  Performing this bounded aggregation in
        PostgreSQL avoids treating an HTTP pagination ceiling as complete
        institutional coverage.
        """

        return self._database.fetch_all(
            """
            WITH latest AS (
                SELECT portfolio.*,
                       row_number() OVER (
                           PARTITION BY portfolio.end_date, portfolio.ts_code
                           ORDER BY portfolio.ann_date DESC NULLS LAST,
                                    portfolio._last_seen_at DESC NULLS LAST
                       ) AS revision_rank
                FROM tushare_norm_fund_portfolio AS portfolio
                WHERE portfolio.symbol=%s
                  AND portfolio.end_date BETWEEN %s AND %s
                  AND (portfolio.ann_date IS NULL OR portfolio.ann_date <= %s)
            )
            SELECT end_date AS period,
                   count(DISTINCT ts_code) AS fund_count,
                   sum(mkv) AS market_value,
                   sum(amount) AS shares,
                   sum(stk_float_ratio) AS reported_float_ratio_sum_pct
            FROM latest
            WHERE revision_rank=1
            GROUP BY end_date
            ORDER BY end_date DESC
            LIMIT %s
            """,
            (ts_code, start_date, as_of, as_of, periods),
        )

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

    def technical_screen_snapshot(self, as_of: date) -> dict:
        """Return one governed cross-sectional technical factor snapshot.

        Split-adjusted price geometry is reconstructed from the provider's
        daily return series. This avoids comparing raw price levels across
        corporate actions while keeping the screen on the indexed daily table.
        """
        now = monotonic()
        with _TECHNICAL_SCREEN_CACHE_LOCK:
            cached = _TECHNICAL_SCREEN_CACHE.get(as_of)
            if cached and now - cached[0] <= _TECHNICAL_SCREEN_CACHE_SECONDS:
                return cached[1]
        rows = self._database.fetch_all(
            """
            WITH target AS (
                SELECT max(trade_date) AS trade_date
                FROM daily
                WHERE trade_date <= %s
            ), recent_dates AS MATERIALIZED (
                SELECT DISTINCT d.trade_date
                FROM daily AS d
                CROSS JOIN target
                WHERE d.trade_date <= target.trade_date
                ORDER BY d.trade_date DESC
                -- Screening rules need at most 120 completed observations.
                -- Keep a small buffer for newly listed/suspended securities
                -- without scanning 1.4M+ rows on every bounded query.
                LIMIT 125
            ), raw AS MATERIALIZED (
                SELECT d.ts_code, d.trade_date, d.close, d.pct_chg,
                       d.vol, d.amount,
                       exp(sum(ln(greatest(
                           1 + COALESCE(d.pct_chg, 0)::double precision / 100,
                           0.000001
                       ))) OVER (
                           PARTITION BY d.ts_code ORDER BY d.trade_date
                           ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
                       )) AS price_index
                FROM daily AS d
                JOIN recent_dates USING (trade_date)
            ), changes AS (
                SELECT raw.*,
                       price_index - lag(price_index) OVER (
                           PARTITION BY ts_code ORDER BY trade_date
                       ) AS price_change
                FROM raw
            ), factors AS (
                SELECT changes.*,
                       row_number() OVER (
                           PARTITION BY ts_code ORDER BY trade_date DESC
                       ) AS latest_rank,
                       count(*) OVER (PARTITION BY ts_code) AS history_observations,
                       lag(price_index, 1) OVER (
                           PARTITION BY ts_code ORDER BY trade_date
                       ) AS previous_index,
                       lag(price_index, 20) OVER (
                           PARTITION BY ts_code ORDER BY trade_date
                       ) AS index_20d_ago,
                       lag(price_index, 60) OVER (
                           PARTITION BY ts_code ORDER BY trade_date
                       ) AS index_60d_ago,
                       avg(price_index) OVER (
                           PARTITION BY ts_code ORDER BY trade_date
                           ROWS BETWEEN 19 PRECEDING AND CURRENT ROW
                       ) AS ma20,
                       avg(price_index) OVER (
                           PARTITION BY ts_code ORDER BY trade_date
                           ROWS BETWEEN 59 PRECEDING AND CURRENT ROW
                       ) AS ma60,
                       avg(price_index) OVER (
                           PARTITION BY ts_code ORDER BY trade_date
                           ROWS BETWEEN 119 PRECEDING AND CURRENT ROW
                       ) AS ma120,
                       max(price_index) OVER (
                           PARTITION BY ts_code ORDER BY trade_date
                           ROWS BETWEEN 20 PRECEDING AND 1 PRECEDING
                       ) AS prior_high20,
                       avg(vol) OVER (
                           PARTITION BY ts_code ORDER BY trade_date
                           ROWS BETWEEN 20 PRECEDING AND 1 PRECEDING
                       ) AS prior_volume20,
                       avg(greatest(price_change, 0)) OVER (
                           PARTITION BY ts_code ORDER BY trade_date
                           ROWS BETWEEN 13 PRECEDING AND CURRENT ROW
                       ) AS average_gain14,
                       avg(greatest(-price_change, 0)) OVER (
                           PARTITION BY ts_code ORDER BY trade_date
                           ROWS BETWEEN 13 PRECEDING AND CURRENT ROW
                       ) AS average_loss14
                FROM changes
            ), universe AS (
                SELECT count(*)::INTEGER AS expected_securities
                FROM stock_basic
                CROSS JOIN target
                WHERE list_status='L'
                  AND (list_date IS NULL OR list_date='' OR
                       to_date(list_date, 'YYYYMMDD') <= target.trade_date)
            ), audit AS (
                SELECT partition.status, partition.row_count,
                       partition.entity_count,
                       partition.expected_entity_count,
                       partition.entity_coverage_ratio,
                       partition.checked_at
                FROM sys_data_coverage_partition AS partition
                CROSS JOIN target
                WHERE partition.dataset_name='stock_daily'
                  AND partition.partition_date=target.trade_date
            )
            SELECT factors.ts_code, basic.name, basic.industry, basic.market,
                   factors.trade_date, factors.close, factors.pct_chg,
                   factors.vol, factors.amount, factors.price_index,
                   factors.previous_index, factors.index_20d_ago,
                   factors.index_60d_ago, factors.ma20, factors.ma60,
                   factors.ma120, factors.prior_high20,
                   factors.prior_volume20, factors.average_gain14,
                   factors.average_loss14, factors.history_observations,
                   universe.expected_securities,
                   count(*) OVER ()::INTEGER AS observed_securities,
                   audit.status AS audit_status,
                   audit.row_count AS audit_row_count,
                   audit.entity_count AS audit_entity_count,
                   audit.expected_entity_count AS audit_expected_entity_count,
                   audit.entity_coverage_ratio AS audit_entity_coverage_ratio,
                   audit.checked_at AS audit_checked_at
            FROM factors
            JOIN stock_basic AS basic USING (ts_code)
            CROSS JOIN universe
            LEFT JOIN audit ON TRUE
            WHERE factors.latest_rank=1
              AND factors.trade_date=(SELECT trade_date FROM target)
            ORDER BY factors.ts_code
            """,
            (as_of,),
        )
        if not rows:
            result = {"rows": [], "summary": {}}
            with _TECHNICAL_SCREEN_CACHE_LOCK:
                _TECHNICAL_SCREEN_CACHE[as_of] = (now, result)
            return result
        first = rows[0]
        summary_keys = {
            "expected_securities", "observed_securities", "audit_status",
            "audit_row_count", "audit_entity_count",
            "audit_expected_entity_count", "audit_entity_coverage_ratio",
            "audit_checked_at",
        }
        summary = {key: first.get(key) for key in summary_keys}
        result = {
            "rows": [
                {key: value for key, value in row.items() if key not in summary_keys}
                for row in rows
            ],
            "summary": summary,
        }
        with _TECHNICAL_SCREEN_CACHE_LOCK:
            _TECHNICAL_SCREEN_CACHE.clear()
            _TECHNICAL_SCREEN_CACHE[as_of] = (now, result)
        return result

    def backfill_statuses(self) -> dict[str, dict]:
        """Return execution progress and independently audited data state.

        A successful workflow proves that code ran; it does not prove that a
        dataset's historical contract is complete.  Keep both facts in the
        same projection so the research catalog cannot label a workstream
        ready from execution counts alone.
        """
        rows = self._database.fetch_all(
            """
            SELECT task_key AS group_name,
                   count(*)::INTEGER AS total,
                   count(*) FILTER (
                       WHERE status IN (
                         'created','queued','running','waiting_dependency',
                         'retrying','validating','publishing'
                       )
                   )::INTEGER AS active,
                   count(*) FILTER (
                       WHERE status='attention'
                         AND NOT EXISTS (
                           SELECT 1
                           FROM orchestration_v2.task_execution AS recovered
                           WHERE recovered.task_key=execution.task_key
                             AND recovered.observation_key=execution.observation_key
                             AND recovered.status='success'
                             AND recovered.task_execution_id > execution.task_execution_id
                         )
                   )::INTEGER AS unresolved,
                   count(*) FILTER (
                       WHERE status='success'
                   )::INTEGER AS complete,
                   count(*) FILTER (
                       WHERE status='cancelled'
                         AND NOT EXISTS (
                           SELECT 1
                           FROM orchestration_v2.task_execution AS recovered
                           WHERE recovered.task_key=execution.task_key
                             AND recovered.observation_key=execution.observation_key
                             AND recovered.status='success'
                             AND recovered.task_execution_id > execution.task_execution_id
                         )
                   )::INTEGER AS cancelled
            FROM orchestration_v2.task_execution AS execution
            WHERE purpose IN ('backfill','initialization','repair')
            GROUP BY group_name
            """
        )
        states: dict[str, dict] = {}
        for row in rows:
            group = row["group_name"]
            states[group] = {
                "engine": "orchestration_v2",
                "executions": int(row["total"] or 0),
                "active": int(row["active"] or 0),
                "unresolved": int(row["unresolved"] or 0),
                "completed": int(row["complete"] or 0),
                "cancelled": int(row["cancelled"] or 0),
            }
        for state in states.values():
            total = state["executions"]
            if state["unresolved"]:
                status = "attention"
            elif state["active"]:
                status = "running"
            elif state["cancelled"]:
                status = "paused"
            elif total:
                # Resolved failures and superseded attempts are historical
                # evidence, not unfinished work.  ``active`` and ``unresolved``
                # above are the effective completion gate.
                status = "complete"
            else:  # pragma: no cover - a grouped row always has at least one record
                status = "planned"
            state["status"] = status
        # Reuse the same durable aggregate used by the operations dashboard.
        # Import locally to keep the research query module free of a startup
        # dependency on coverage orchestration.
        from service.data_coverage.repository import CoverageRepository

        for dataset_name, audit in CoverageRepository().latest_audits().items():
            state = states.setdefault(dataset_name, {
                "engine": "orchestration_v2",
                "executions": 0,
                "active": 0,
                "unresolved": 0,
                "completed": 0,
                "cancelled": 0,
                "status": "planned",
            })
            coverage_status = str(audit.get("status") or "unverified")
            state.update({
                "coverage_status": coverage_status,
                "coverage_start": audit.get("start_date"),
                "coverage_end": audit.get("end_date"),
                "expected_partitions": int(audit.get("expected_partitions") or 0),
                "present_partitions": int(audit.get("present_partitions") or 0),
                "missing_partitions": int(audit.get("missing_partitions") or 0),
                "partial_partitions": int(audit.get("partial_partitions") or 0),
            })
            if not state["unresolved"] and not state["active"]:
                state["status"] = (
                    "complete"
                    if coverage_status in {"complete", "empty"}
                    else "attention"
                    if coverage_status in {"gaps", "unverified"}
                    else "planned"
                )
        return states

    def latest_stock_valuations(
        self, ts_codes: list[str], *, as_of: date,
    ) -> dict[str, dict]:
        """Load the latest valuation row for many peers in one indexed query."""

        if not ts_codes:
            return {}
        rows = self._database.fetch_all(
            """
            SELECT DISTINCT ON (ts_code)
                   ts_code, trade_date, pe_ttm, pb, ps_ttm
            FROM tushare_current_daily_basic
            WHERE ts_code = ANY(%s)
              AND trade_date <= %s
            ORDER BY ts_code, trade_date DESC
            """,
            (ts_codes, as_of),
        )
        return {row["ts_code"]: row for row in rows}

    def macro_series(self, *, as_of: date, limit: int = 24) -> dict[str, list[dict]]:
        """Return bounded, normalized macro series with explicit observation dates."""

        return {
            "gdp": self._database.fetch_all(
                """
                WITH latest AS (
                    SELECT DISTINCT ON (quarter) *
                    FROM tushare_norm_cn_gdp
                    WHERE quarter IS NOT NULL
                    ORDER BY quarter, _source_collected_at DESC, _last_seen_at DESC
                )
                SELECT quarter AS period,
                       (
                           make_date(split_part(quarter, 'Q', 1)::INTEGER,
                                     split_part(quarter, 'Q', 2)::INTEGER * 3, 1)
                           + INTERVAL '1 month - 1 day'
                       )::DATE AS observation_date,
                       gdp, gdp_yoy, pi_yoy, si_yoy, ti_yoy
                FROM latest
                WHERE (
                    make_date(split_part(quarter, 'Q', 1)::INTEGER,
                              split_part(quarter, 'Q', 2)::INTEGER * 3, 1)
                    + INTERVAL '1 month - 1 day'
                )::DATE <= %s
                ORDER BY observation_date DESC
                LIMIT %s
                """,
                (as_of, limit),
            ),
            "pmi": self._database.fetch_all(
                """
                WITH latest AS (
                    SELECT DISTINCT ON (month) *
                    FROM tushare_norm_cn_pmi
                    WHERE month IS NOT NULL
                    ORDER BY month, _source_collected_at DESC, _last_seen_at DESC
                )
                SELECT month AS period,
                       (to_date(month, 'YYYYMM') + INTERVAL '1 month - 1 day')::DATE
                           AS observation_date,
                       pmi010000 AS manufacturing,
                       pmi010100 AS large_enterprise,
                       pmi010200 AS medium_enterprise,
                       pmi010300 AS small_enterprise,
                       pmi010400 AS production,
                       pmi010500 AS new_orders,
                       pmi030000 AS composite
                FROM latest
                WHERE (to_date(month, 'YYYYMM') + INTERVAL '1 month - 1 day')::DATE <= %s
                ORDER BY observation_date DESC
                LIMIT %s
                """,
                (as_of, limit),
            ),
            "cpi": self._database.fetch_all(
                """
                WITH latest AS (
                    SELECT DISTINCT ON (month) *
                    FROM tushare_norm_cn_cpi
                    WHERE month IS NOT NULL
                    ORDER BY month, _source_collected_at DESC, _last_seen_at DESC
                )
                SELECT month AS period,
                       (to_date(month, 'YYYYMM') + INTERVAL '1 month - 1 day')::DATE
                           AS observation_date,
                       nt_val AS national_index, nt_yoy AS yoy, nt_mom AS mom,
                       town_yoy, cnt_yoy
                FROM latest
                WHERE (to_date(month, 'YYYYMM') + INTERVAL '1 month - 1 day')::DATE <= %s
                ORDER BY observation_date DESC
                LIMIT %s
                """,
                (as_of, limit),
            ),
            "ppi": self._database.fetch_all(
                """
                WITH latest AS (
                    SELECT DISTINCT ON (month) *
                    FROM tushare_norm_cn_ppi
                    WHERE month IS NOT NULL
                    ORDER BY month, _source_collected_at DESC, _last_seen_at DESC
                )
                SELECT month AS period,
                       (to_date(month, 'YYYYMM') + INTERVAL '1 month - 1 day')::DATE
                           AS observation_date,
                       ppi_yoy AS yoy, ppi_mom AS mom, ppi_accu AS cumulative_yoy
                FROM latest
                WHERE (to_date(month, 'YYYYMM') + INTERVAL '1 month - 1 day')::DATE <= %s
                ORDER BY observation_date DESC
                LIMIT %s
                """,
                (as_of, limit),
            ),
            "money_supply": self._database.fetch_all(
                """
                WITH latest AS (
                    SELECT DISTINCT ON (month) *
                    FROM tushare_norm_cn_m
                    WHERE month IS NOT NULL
                    ORDER BY month, _source_collected_at DESC, _last_seen_at DESC
                )
                SELECT month AS period,
                       (to_date(month, 'YYYYMM') + INTERVAL '1 month - 1 day')::DATE
                           AS observation_date,
                       m0, m0_yoy, m1, m1_yoy, m2, m2_yoy
                FROM latest
                WHERE (to_date(month, 'YYYYMM') + INTERVAL '1 month - 1 day')::DATE <= %s
                ORDER BY observation_date DESC
                LIMIT %s
                """,
                (as_of, limit),
            ),
            "social_financing": self._database.fetch_all(
                """
                WITH latest AS (
                    SELECT DISTINCT ON (month) *
                    FROM tushare_norm_sf_month
                    WHERE month IS NOT NULL
                    ORDER BY month, _source_collected_at DESC, _last_seen_at DESC
                )
                SELECT month AS period,
                       (to_date(month, 'YYYYMM') + INTERVAL '1 month - 1 day')::DATE
                           AS observation_date,
                       inc_month, inc_cumval, stk_endval
                FROM latest
                WHERE (to_date(month, 'YYYYMM') + INTERVAL '1 month - 1 day')::DATE <= %s
                ORDER BY observation_date DESC
                LIMIT %s
                """,
                (as_of, limit),
            ),
            "shibor": self._database.fetch_all(
                """
                WITH latest AS (
                    SELECT DISTINCT ON (date) *
                    FROM tushare_norm_shibor
                    WHERE date IS NOT NULL
                    ORDER BY date, _source_collected_at DESC, _last_seen_at DESC
                )
                SELECT date AS observation_date, "on" AS overnight,
                       "1w" AS one_week, "1m" AS one_month,
                       "3m" AS three_month, "1y" AS one_year
                FROM latest
                WHERE date <= %s
                ORDER BY date DESC
                LIMIT %s
                """,
                (as_of, limit),
            ),
            "lpr": self._database.fetch_all(
                """
                WITH latest AS (
                    SELECT DISTINCT ON (date) *
                    FROM canonical_cn_lpr
                    WHERE date IS NOT NULL
                    ORDER BY date, _source_collected_at DESC, _last_seen_at DESC
                )
                SELECT date AS observation_date, "1y" AS one_year,
                       "5y" AS five_year
                FROM latest
                WHERE date <= %s
                ORDER BY date DESC
                LIMIT %s
                """,
                (as_of, limit),
            ),
        }

    def industry_fundamentals(
        self,
        member_codes: list[str],
        *,
        as_of: date,
    ) -> dict | None:
        if not member_codes:
            return None
        return self._database.fetch_one(
            """
            WITH members AS (
                SELECT unnest(%s::text[]) AS ts_code
            ), income_rows AS MATERIALIZED (
                SELECT DISTINCT ON (i.ts_code, i.end_date)
                       i.ts_code, i.end_date, i.revenue, i.n_income_attr_p
                FROM income AS i
                JOIN members USING (ts_code)
                WHERE i.end_date <= %s
                  AND COALESCE(i.f_ann_date, i.ann_date) <= %s
                ORDER BY i.ts_code, i.end_date,
                         COALESCE(i.f_ann_date, i.ann_date) DESC NULLS LAST,
                         i.report_type
            ), period_coverage AS (
                SELECT end_date, count(*) AS companies
                FROM income_rows
                GROUP BY end_date
            ), target AS (
                SELECT end_date
                FROM period_coverage
                ORDER BY (
                    companies >= GREATEST(3, CEIL(%s * 0.5))
                ) DESC, end_date DESC
                LIMIT 1
            ), current_income AS (
                SELECT i.* FROM income_rows AS i JOIN target USING (end_date)
            ), prior_income AS (
                SELECT i.*
                FROM income_rows AS i
                CROSS JOIN target AS t
                WHERE i.end_date = (t.end_date - INTERVAL '1 year')::DATE
            ), cash_rows AS MATERIALIZED (
                SELECT DISTINCT ON (c.ts_code, c.end_date)
                       c.ts_code, c.end_date, c.n_cashflow_act, c.free_cashflow
                FROM cashflow AS c
                JOIN members USING (ts_code)
                WHERE c.end_date <= %s
                  AND COALESCE(c.f_ann_date, c.ann_date) <= %s
                ORDER BY c.ts_code, c.end_date,
                         COALESCE(c.f_ann_date, c.ann_date) DESC NULLS LAST,
                         c.report_type
            ), current_cash AS (
                SELECT c.* FROM cash_rows AS c JOIN target USING (end_date)
            ), indicators AS MATERIALIZED (
                SELECT DISTINCT ON (f.ts_code, f.end_date)
                       f.ts_code, f.end_date, f.grossprofit_margin,
                       f.netprofit_margin, f.roe, f.roic, f.debt_to_assets
                FROM fina_indicator AS f
                JOIN members USING (ts_code)
                WHERE f.end_date <= %s
                  AND f.ann_date <= %s
                ORDER BY f.ts_code, f.end_date, f.ann_date DESC NULLS LAST,
                         f.report_type
            ), current_indicators AS (
                SELECT f.* FROM indicators AS f JOIN target USING (end_date)
            ), valuation_rows AS MATERIALIZED (
                SELECT DISTINCT ON (d.ts_code)
                       d.ts_code, d.trade_date, d.total_mv, d.pe_ttm,
                       d.pb, d.ps_ttm, d.dv_ttm
                FROM tushare_current_daily_basic AS d
                JOIN members USING (ts_code)
                WHERE d.trade_date <= %s
                ORDER BY d.ts_code, d.trade_date DESC, d._last_seen_at DESC
            )
            SELECT (SELECT end_date FROM target) AS report_period,
                   %s::INTEGER AS member_count,
                   (SELECT count(*) FROM current_income)::INTEGER
                       AS financial_covered,
                   (SELECT count(*) FROM prior_income)::INTEGER
                       AS prior_financial_covered,
                   (SELECT sum(revenue) FROM current_income) AS revenue,
                   (SELECT sum(revenue) FROM prior_income) AS prior_revenue,
                   (SELECT sum(n_income_attr_p) FROM current_income) AS net_income,
                   (SELECT sum(n_income_attr_p) FROM prior_income) AS prior_net_income,
                   (SELECT sum(n_cashflow_act) FROM current_cash)
                       AS operating_cashflow,
                   (SELECT sum(free_cashflow) FROM current_cash) AS free_cashflow,
                   (SELECT percentile_cont(0.5) WITHIN GROUP (
                       ORDER BY grossprofit_margin
                   ) FROM current_indicators WHERE grossprofit_margin IS NOT NULL)
                       AS median_gross_margin,
                   (SELECT percentile_cont(0.5) WITHIN GROUP (
                       ORDER BY netprofit_margin
                   ) FROM current_indicators WHERE netprofit_margin IS NOT NULL)
                       AS median_net_margin,
                   (SELECT percentile_cont(0.5) WITHIN GROUP (
                       ORDER BY roe
                   ) FROM current_indicators WHERE roe IS NOT NULL) AS median_roe,
                   (SELECT percentile_cont(0.5) WITHIN GROUP (
                       ORDER BY roic
                   ) FROM current_indicators WHERE roic IS NOT NULL) AS median_roic,
                   (SELECT percentile_cont(0.5) WITHIN GROUP (
                       ORDER BY debt_to_assets
                   ) FROM current_indicators WHERE debt_to_assets IS NOT NULL)
                       AS median_debt_to_assets,
                   (SELECT count(*) FROM valuation_rows)::INTEGER
                       AS valuation_covered,
                   (SELECT max(trade_date) FROM valuation_rows) AS valuation_date,
                   (SELECT sum(total_mv) FROM valuation_rows) AS total_market_value,
                   (SELECT percentile_cont(0.5) WITHIN GROUP (ORDER BY pe_ttm)
                    FROM valuation_rows WHERE pe_ttm > 0) AS median_pe_ttm,
                   (SELECT percentile_cont(0.5) WITHIN GROUP (ORDER BY pb)
                    FROM valuation_rows WHERE pb > 0) AS median_pb,
                   (SELECT percentile_cont(0.5) WITHIN GROUP (ORDER BY ps_ttm)
                    FROM valuation_rows WHERE ps_ttm > 0) AS median_ps_ttm,
                   (SELECT percentile_cont(0.5) WITHIN GROUP (ORDER BY dv_ttm)
                    FROM valuation_rows WHERE dv_ttm IS NOT NULL) AS median_dv_ttm
            """,
            (
                member_codes,
                as_of,
                as_of,
                len(member_codes),
                as_of,
                as_of,
                as_of,
                as_of,
                as_of,
                len(member_codes),
            ),
        )

    def industry_contributors(
        self,
        member_codes: list[str],
        *,
        as_of: date,
        report_period: date,
        limit: int = 10,
    ) -> list[dict]:
        if not member_codes:
            return []
        return self._database.fetch_all(
            """
            WITH members AS (
                SELECT unnest(%s::text[]) AS ts_code
            ), rows AS MATERIALIZED (
                SELECT DISTINCT ON (i.ts_code)
                       i.ts_code, b.name, i.revenue, i.n_income_attr_p
                FROM income AS i
                JOIN members USING (ts_code)
                LEFT JOIN stock_basic AS b USING (ts_code)
                WHERE i.end_date = %s
                  AND COALESCE(i.f_ann_date, i.ann_date) <= %s
                ORDER BY i.ts_code,
                         COALESCE(i.f_ann_date, i.ann_date) DESC NULLS LAST,
                         i.report_type
            ), totals AS (
                SELECT sum(revenue) AS revenue,
                       sum(n_income_attr_p) AS net_income
                FROM rows
            )
            SELECT rows.*,
                   rows.revenue / NULLIF(totals.revenue, 0) * 100
                       AS revenue_share_pct,
                   rows.n_income_attr_p / NULLIF(totals.net_income, 0) * 100
                       AS net_income_share_pct
            FROM rows CROSS JOIN totals
            ORDER BY abs(rows.revenue) DESC NULLS LAST, rows.ts_code
            LIMIT %s
            """,
            (member_codes, report_period, as_of, limit),
        )

    def industry_breadth(
        self,
        member_codes: list[str],
        *,
        as_of: date,
    ) -> dict | None:
        if not member_codes:
            return None
        return self._database.fetch_one(
            """
            WITH members AS (
                SELECT unnest(%s::text[]) AS ts_code
            ), target AS (
                SELECT max(d.trade_date) AS trade_date
                FROM daily AS d JOIN members USING (ts_code)
                WHERE d.trade_date <= %s
            ), current_day AS MATERIALIZED (
                SELECT d.*
                FROM daily AS d
                JOIN members USING (ts_code)
                JOIN target AS t ON t.trade_date=d.trade_date
            ), moving AS (
                SELECT c.ts_code,
                       avg(history.close) FILTER (
                           WHERE history.observation_rank <= 20
                       ) AS ma20,
                       avg(history.close) AS ma60
                FROM current_day AS c
                LEFT JOIN LATERAL (
                    SELECT recent.close,
                           row_number() OVER (
                               ORDER BY recent.trade_date DESC
                           ) AS observation_rank
                    FROM (
                        SELECT d.trade_date, d.close
                        FROM daily AS d
                        WHERE d.ts_code=c.ts_code
                          AND d.trade_date <= c.trade_date
                        ORDER BY d.trade_date DESC
                        LIMIT 60
                    ) AS recent
                ) AS history ON TRUE
                GROUP BY c.ts_code
            )
            SELECT max(t.trade_date) AS trade_date,
                   count(c.ts_code)::INTEGER AS observed_members,
                   count(*) FILTER (WHERE c.close > c.pre_close)::INTEGER AS advancing,
                   count(*) FILTER (WHERE c.close < c.pre_close)::INTEGER AS declining,
                   count(*) FILTER (WHERE c.close = c.pre_close)::INTEGER AS unchanged,
                   avg(c.pct_chg) AS average_return_pct,
                   percentile_cont(0.5) WITHIN GROUP (ORDER BY c.pct_chg)
                       AS median_return_pct,
                   count(*) FILTER (WHERE c.close > m.ma20)::INTEGER AS above_ma20,
                   count(*) FILTER (WHERE c.close > m.ma60)::INTEGER AS above_ma60,
                   sum(c.amount) AS amount
            FROM target AS t
            LEFT JOIN current_day AS c ON TRUE
            LEFT JOIN moving AS m USING (ts_code)
            """,
            (member_codes, as_of),
        )

    def etf_share_flows(
        self,
        *,
        as_of: date,
        lookback_observations: int,
    ) -> list[dict]:
        """Return per-ETF primary-market flow proxies from governed shares.

        ``total_share`` is expressed in ten-thousand shares. Multiplying its
        change by NAV and dividing by 10,000 therefore yields RMB 100m.  NAV
        is preferred over close because secondary-market price changes are
        not primary-market creations/redemptions; reported size/share is a
        deterministic fallback when NAV is absent.
        """

        baseline_rank = lookback_observations + 1
        calendar_lookback_days = lookback_observations * 3 + 30
        return self._database.fetch_all(
            """
            WITH target AS (
                SELECT max(trade_date) AS trade_date
                FROM tushare_norm_etf_share_size
                WHERE trade_date <= %s
            ), ranked AS MATERIALIZED (
                SELECT shares.ts_code, shares.trade_date, shares.total_share,
                       shares.total_size, shares.nav, shares.close,
                       row_number() OVER (
                           PARTITION BY shares.ts_code
                           ORDER BY shares.trade_date DESC
                       ) AS observation_rank
                FROM tushare_norm_etf_share_size AS shares
                CROSS JOIN target
                WHERE shares.trade_date <= target.trade_date
                  AND shares.trade_date >= target.trade_date - (%s * INTERVAL '1 day')
            ), bounds AS (
                SELECT ts_code,
                       max(trade_date) FILTER (WHERE observation_rank=1)
                           AS latest_date,
                       max(trade_date) FILTER (WHERE observation_rank=%s)
                           AS baseline_date,
                       max(total_share) FILTER (WHERE observation_rank=1)
                           AS latest_share,
                       max(total_share) FILTER (WHERE observation_rank=%s)
                           AS baseline_share,
                       max(total_size) FILTER (WHERE observation_rank=1)
                           AS latest_size,
                       max(nav) FILTER (WHERE observation_rank=1) AS latest_nav,
                       max(close) FILTER (WHERE observation_rank=1) AS latest_close,
                       count(*) FILTER (WHERE observation_rank <= %s)
                           AS observations
                FROM ranked
                WHERE observation_rank <= %s
                GROUP BY ts_code
            ), basic AS (
                SELECT DISTINCT ON (ts_code)
                       ts_code, index_code, index_name, csname, extname,
                       cname, mgr_name, etf_type
                FROM tushare_norm_etf_basic
                ORDER BY ts_code, _last_seen_at DESC
            ), fund AS (
                SELECT DISTINCT ON (ts_code)
                       ts_code, fund_type, invest_type, type
                FROM tushare_norm_fund_basic
                ORDER BY ts_code, _last_seen_at DESC
            )
            SELECT bounds.*, basic.index_code, basic.index_name,
                   COALESCE(basic.csname, basic.extname, basic.cname) AS etf_name,
                   basic.mgr_name, basic.etf_type,
                   fund.fund_type, fund.invest_type, fund.type AS fund_class,
                   COALESCE(
                       bounds.latest_nav,
                       bounds.latest_size / NULLIF(bounds.latest_share, 0)
                   ) AS unit_nav,
                   (
                       bounds.latest_share - bounds.baseline_share
                   ) * COALESCE(
                       bounds.latest_nav,
                       bounds.latest_size / NULLIF(bounds.latest_share, 0)
                   ) / 10000 AS estimated_flow_yi
            FROM bounds
            LEFT JOIN basic USING (ts_code)
            LEFT JOIN fund USING (ts_code)
            WHERE bounds.baseline_share IS NOT NULL
              AND bounds.latest_share IS NOT NULL
            ORDER BY abs((
                bounds.latest_share - bounds.baseline_share
            ) * COALESCE(
                bounds.latest_nav,
                bounds.latest_size / NULLIF(bounds.latest_share, 0)
            )) DESC NULLS LAST, bounds.ts_code
            """,
            (
                as_of,
                calendar_lookback_days,
                baseline_rank,
                baseline_rank,
                baseline_rank,
                baseline_rank,
            ),
        )

    def index_period_returns(
        self,
        periods: dict[str, tuple[date, date]],
    ) -> dict[str, dict]:
        if not periods:
            return {}
        index_codes = list(periods)
        starts = [periods[code][0] for code in index_codes]
        ends = [periods[code][1] for code in index_codes]
        rows = self._database.fetch_all(
            """
            SELECT requested.index_code,
                   baseline.trade_date AS baseline_date,
                   baseline.close AS baseline_close,
                   latest.trade_date AS latest_date,
                   latest.close AS latest_close
            FROM unnest(
                %s::text[], %s::date[], %s::date[]
            ) AS requested(index_code, baseline_target, latest_target)
            LEFT JOIN LATERAL (
                SELECT trade_date, close
                FROM index_daily
                WHERE ts_code=requested.index_code
                  AND trade_date <= requested.baseline_target
                ORDER BY trade_date DESC
                LIMIT 1
            ) AS baseline ON TRUE
            LEFT JOIN LATERAL (
                SELECT trade_date, close
                FROM index_daily
                WHERE ts_code=requested.index_code
                  AND trade_date <= requested.latest_target
                ORDER BY trade_date DESC
                LIMIT 1
            ) AS latest ON TRUE
            """,
            (index_codes, starts, ends),
        )
        return {row["index_code"]: row for row in rows}

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
