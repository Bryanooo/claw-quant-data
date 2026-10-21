"""Code-owned V2 derived-data handlers.

Transformations consume governed database datasets; they never call an
upstream provider.  The registry is deliberately explicit so task metadata
cannot load arbitrary code from the database.
"""

from __future__ import annotations

from datetime import date
from typing import Any

import psycopg2.extras

from service.db import get_conn
from service.research.fama_french import (
    FF3_FORMULA_VERSION,
    MIN_ELIGIBLE,
    daily_factors,
)
from service.research.service import _adjust_ohlcv
from service.research.technical_indicators import (
    COMMON_INDICATOR_FORMULA_VERSION,
    common_indicator_pack,
    niumen_breakout_lines,
    parameterized_indicator_pack,
)
from service.research.volume_price import transaction_cost_lines

FORMULA_VERSION = (
    "niumen-tongdaxin-v1+transaction-cost-v1+"
    f"{COMMON_INDICATOR_FORMULA_VERSION}+parameterized-technicals-v1"
)
SUPPORTED_TRANSFORMATION_TASK_KEYS = frozenset(
    {"technical_factor_snapshot", "fama_french_daily"}
)

# A-share Fama-French universe rule: a name listed for fewer than this many
# sessions is excluded so newly listed securities do not distort the split.
MIN_LISTING_BARS = 60


def fama_french_sources_complete(
    source_daily_count: int,
    matched_daily_cap_count: int,
) -> bool:
    """Return true only when every observed return has a market-cap row."""

    return (
        source_daily_count > 0
        and source_daily_count == matched_daily_cap_count
    )


def _number(value: Any) -> float | None:
    if value is None or value == "":
        return None
    return float(value)


def build_technical_factor_snapshot_row(
    ts_code: str,
    snapshot_date: date,
    source_rows: list[dict[str, Any]],
    *,
    source_execution_id: int | None = None,
) -> dict[str, Any]:
    """Build one explicit, auditable stock snapshot from governed daily bars."""

    ordered = sorted(source_rows, key=lambda item: item.get("trade_date") or date.min)
    raw_bars = [dict(item) for item in ordered if item.get("trade_date")]
    adjustments = [
        {"trade_date": item["trade_date"], "adj_factor": item.get("adj_factor")}
        for item in raw_bars
        if item.get("adj_factor") is not None
    ]
    adjusted, adjustment = _adjust_ohlcv(
        raw_bars, adjustments, dataset="adj_factor"
    )
    # _adjust_ohlcv intentionally returns continuous raw bars when factors are
    # partial so charts do not acquire artificial multi-year holes.  A derived
    # adjusted-factor snapshot, however, must fail closed rather than compute
    # adjusted indicators from those raw bars.
    usable = [
        item for item in adjusted
        if adjustment["status"] == "applied"
        and all(
            _number(item.get(field)) is not None
            for field in ("high", "low", "close")
        )
    ]
    highs = [float(item["high"]) for item in usable]
    lows = [float(item["low"]) for item in usable]
    closes = [float(item["close"]) for item in usable]
    opens = [float(item["open"]) for item in usable]
    volumes = [float(_number(item.get("vol")) or 0) for item in usable]
    niumen = niumen_breakout_lines(highs, lows, closes)
    common = common_indicator_pack(highs, lows, closes, volumes)
    common_latest = common["latest"]
    parameterized = parameterized_indicator_pack(
        opens, highs, lows, closes, volumes, timeframe="1d"
    )
    parameterized_latest = parameterized["latest"]
    costs = transaction_cost_lines(
        usable,
        closes[-1] if closes else 0.0,
        amount_to_price_factor=10.0,
        windows=(20, 60),
    )
    cost20 = costs["windows"]["20_day"]
    cost60 = costs["windows"]["60_day"]
    reasons: list[dict[str, Any]] = []
    if not raw_bars:
        reasons.append({"indicator": "all", "reason": "no_daily_bars"})
    if adjustment["status"] in {"missing", "stale", "partial_history"}:
        reasons.append({
            "indicator": "price_adjustment",
            "reason": f"adjustment_{adjustment['status']}",
            "source_bars": len(raw_bars),
            "matched_factors": int(adjustment["matched"]),
        })
    if niumen["status"] != "ready":
        reasons.append({
            "indicator": "niumen_confirmation",
            "reason": niumen["status"],
            "required_bars": 21,
            "available_adjusted_bars": len(usable),
        })
    if common["status"] != "ready":
        reasons.append({
            "indicator": "common_technical_pack",
            "reason": common["status"],
            "required_bars": 200,
            "available_adjusted_bars": len(usable),
        })
    if parameterized["status"] != "ready":
        reasons.append({
            "indicator": "parameterized_technical_pack",
            "reason": parameterized["status"],
            "required_bars": 250,
            "available_adjusted_bars": len(usable),
        })
    normalized_costs: dict[int, dict[str, Any]] = {}
    for window, original in ((20, cost20), (60, cost60)):
        result = dict(original)
        if (
            result["status"] == "insufficient_history"
            and len(raw_bars) >= window
            and len(usable) < window
        ):
            result["status"] = "missing_input"
        normalized_costs[window] = result
        if result["status"] != "ready":
            reasons.append({
                "indicator": f"cost_{window}",
                "reason": result["status"],
                "required_bars": window,
                "available_adjusted_bars": len(usable),
                "usable_observations": result["usable_observations"],
            })

    cost20 = normalized_costs[20]
    cost60 = normalized_costs[60]

    statuses = (
        niumen["status"], cost20["status"], cost60["status"], common["status"],
        parameterized["status"],
    )
    # ``common_indicator_pack`` reports ``limited_history`` (rather than
    # ``insufficient_history``) when it has fewer than 200 usable bars, but
    # both words mean the same thing for the aggregate status: the history is
    # too short to compute every factor.  ``missing_input`` is reserved for
    # when bars exist yet computation is impossible (e.g. missing adjustment
    # factors), so it must not absorb a short-history case.
    short_history = {"insufficient_history", "limited_history"}
    if all(item == "ready" for item in statuses):
        calculation_status = "ready"
    elif any(item == "ready" for item in statuses):
        calculation_status = "partial"
    elif raw_bars and all(item in short_history for item in statuses):
        calculation_status = "insufficient_history"
    else:
        calculation_status = "missing_input"

    values = niumen["values"]
    events = niumen["events"]
    return {
        "snapshot_date": snapshot_date,
        "ts_code": ts_code,
        "source_trade_date": raw_bars[-1]["trade_date"] if raw_bars else None,
        "source_bar_count": len(raw_bars),
        "adjustment_status": adjustment["status"],
        "adjustment_matched_count": int(adjustment["matched"]),
        "price_basis": str(adjustment["price_basis"]),
        "close": closes[-1] if closes else None,
        "prior_high_20": values["prior_high_20"],
        "atrv_sma_14": values["atrv_sma_14"],
        "niumen_line": values["niumen_line"],
        "confirmation_line": values["confirmation_line"],
        "signal_ma_10": values["signal_ma_10"],
        "niumen_state": niumen["state"],
        "crossed_niumen": events["crossed_niumen_today"],
        "crossed_confirmation": events["crossed_confirmation_today"],
        "cost_20": cost20["value"],
        "cost_20_status": cost20["status"],
        "cost_60": cost60["value"],
        "cost_60_status": cost60["status"],
        "ema_20": common_latest.get("ema_20"),
        "ema_50": common_latest.get("ema_50"),
        "ema_200": common_latest.get("ema_200"),
        "ema_20_distance_pct": common_latest.get("ema_20_distance_pct"),
        "ema_50_distance_pct": common_latest.get("ema_50_distance_pct"),
        "ema_200_distance_pct": common_latest.get("ema_200_distance_pct"),
        "bias_6": common_latest.get("bias_6"),
        "bias_12": common_latest.get("bias_12"),
        "bias_24": common_latest.get("bias_24"),
        "bbi": common_latest.get("bbi"),
        "bbi_distance_pct": common_latest.get("bbi_distance_pct"),
        "ppo_12_26": common_latest.get("ppo"),
        "ppo_signal_9": common_latest.get("ppo_signal"),
        "ppo_histogram": common_latest.get("ppo_histogram"),
        "natr_14": common_latest.get("natr_14"),
        "keltner_middle_20": common_latest.get("keltner_middle"),
        "keltner_upper_20_2": common_latest.get("keltner_upper"),
        "keltner_lower_20_2": common_latest.get("keltner_lower"),
        "ttm_squeeze_on": common_latest.get("ttm_squeeze_on"),
        "ttm_squeeze_momentum": common_latest.get("ttm_squeeze_momentum"),
        "trix_12": common_latest.get("trix_12"),
        "trix_signal_9": common_latest.get("trix_signal_9"),
        "trix_histogram": common_latest.get("trix_histogram"),
        "pvt_20_change": common_latest.get("pvt_change_20"),
        "vroc_12": common_latest.get("vroc_12"),
        "vroc_20": common_latest.get("vroc_20"),
        "force_index_13": common_latest.get("force_index_13"),
        "force_index_13_normalized": common_latest.get(
            "force_index_13_normalized"
        ),
        "common_indicator_status": common["status"],
        "sma_30": parameterized_latest["sma"].get("30"),
        "ema_5": parameterized_latest["ema"].get("5"),
        "ema_10": parameterized_latest["ema"].get("10"),
        "ema_12": parameterized_latest["ema"].get("12"),
        "ema_26": parameterized_latest["ema"].get("26"),
        "ema_100": parameterized_latest["ema"].get("100"),
        **{
            f"rsi_{window}": parameterized_latest["rsi"].get(str(window))
            for window in (6, 12, 14, 24)
        },
        **{
            f"roc_{window}": parameterized_latest["roc"].get(str(window))
            for window in (5, 10, 20, 60, 120)
        },
        "cci_14": parameterized_latest["cci"].get("14"),
        "cci_20": parameterized_latest["cci"].get("20"),
        "atr_14": parameterized_latest["atr"].get("14"),
        "atr_20": parameterized_latest["atr"].get("20"),
        "natr_20": parameterized_latest["natr"].get("20"),
        "tsi_25_13": parameterized_latest["tsi_25_13"],
        "bollinger_percent_b_20_2": parameterized_latest[
            "bollinger_20_2"
        ]["percent_b"],
        "bollinger_bandwidth_20_2_pct": parameterized_latest[
            "bollinger_20_2"
        ]["bandwidth_pct"],
        **parameterized_latest["candle_geometry"],
        "range_position_60": parameterized_latest["structure"][
            "range_position_60"
        ],
        "atr_5_to_20_ratio": parameterized_latest["structure"][
            "atr_5_to_20_ratio"
        ],
        "retracement_depth_20": parameterized_latest["structure"][
            "retracement_depth_20"
        ],
        "retracement_depth_120": parameterized_latest["structure"][
            "retracement_depth_120"
        ],
        "regression_slope_20_pct": parameterized_latest["structure"][
            "regression_20"
        ]["slope_pct_per_bar"],
        "regression_r_squared_20": parameterized_latest["structure"][
            "regression_20"
        ]["r_squared"],
        "regression_slope_60_pct": parameterized_latest["structure"][
            "regression_60"
        ]["slope_pct_per_bar"],
        "regression_r_squared_60": parameterized_latest["structure"][
            "regression_60"
        ]["r_squared"],
        "breakout_over_prior_high_60_atr": parameterized_latest["structure"][
            "breakout_over_prior_high_60_atr"
        ],
        "high_touch_count_60_1pct": parameterized_latest["structure"][
            "high_touch_count_60_1pct"
        ],
        "low_touch_count_60_1pct": parameterized_latest["structure"][
            "low_touch_count_60_1pct"
        ],
        "parameterized_indicator_status": parameterized["status"],
        "calculation_status": calculation_status,
        "unavailable_reasons": reasons,
        "formula_version": FORMULA_VERSION,
        "source_execution_id": source_execution_id,
    }


def materialize_technical_factor_snapshot(
    snapshot_date: date,
    *,
    source_execution_id: int | None = None,
) -> dict[str, Any]:
    """Atomically materialize all stocks listed on ``snapshot_date``."""

    compact_date = snapshot_date.strftime("%Y%m%d")
    connection = get_conn()
    try:
        # The source query returns roughly 260 bars for every listed stock.
        # A server-side cursor keeps that million-row working set in
        # PostgreSQL and materializes only one security at a time in Python.
        # The previous fetchall()+grouped-dict path used several GiB and made
        # the daily derived task compete with collection workers for memory.
        cursor_name = (
            f"technical_snapshot_{snapshot_date:%Y%m%d}_"
            f"{source_execution_id or 0}"
        )
        rows: list[dict[str, Any]] = []
        with connection.cursor(
            name=cursor_name,
            cursor_factory=psycopg2.extras.RealDictCursor,
        ) as source_cursor:
            source_cursor.itersize = 5000
            source_cursor.execute(
                """
                SELECT stock.ts_code, bars.trade_date, bars.open, bars.high,
                       bars.low, bars.close, bars.pre_close, bars.vol,
                       bars.amount, bars.adj_factor
                FROM stock_basic AS stock
                LEFT JOIN LATERAL (
                    SELECT daily.trade_date, daily.open, daily.high, daily.low,
                           daily.close, daily.pre_close, daily.vol, daily.amount,
                           factor.adj_factor
                    FROM daily
                    LEFT JOIN LATERAL (
                        SELECT source.adj_factor
                        FROM tushare_norm_adj_factor AS source
                        WHERE source.ts_code=daily.ts_code
                          AND source.trade_date=daily.trade_date
                          AND source.adj_factor IS NOT NULL
                        ORDER BY source._last_seen_at DESC,
                                 source._record_hash DESC
                        LIMIT 1
                    ) AS factor ON TRUE
                    WHERE daily.ts_code=stock.ts_code
                      AND daily.trade_date <= %s
                    ORDER BY daily.trade_date DESC
                    LIMIT 260
                ) AS bars ON TRUE
                WHERE NULLIF(stock.list_date, '') IS NOT NULL
                  AND stock.list_date <= %s
                  AND (
                      NULLIF(stock.delist_date, '') IS NULL
                      OR stock.delist_date >= %s
                  )
                ORDER BY stock.ts_code, bars.trade_date
                """,
                (snapshot_date, compact_date, compact_date),
            )
            current_ts_code: str | None = None
            source_rows: list[dict[str, Any]] = []
            for item in source_cursor:
                row = dict(item)
                ts_code = str(row.pop("ts_code"))
                if current_ts_code is not None and ts_code != current_ts_code:
                    rows.append(
                        build_technical_factor_snapshot_row(
                            current_ts_code,
                            snapshot_date,
                            source_rows,
                            source_execution_id=source_execution_id,
                        )
                    )
                    source_rows = []
                current_ts_code = ts_code
                if row.get("trade_date") is not None:
                    source_rows.append(row)
            if current_ts_code is not None:
                rows.append(
                    build_technical_factor_snapshot_row(
                        current_ts_code,
                        snapshot_date,
                        source_rows,
                        source_execution_id=source_execution_id,
                    )
                )

        with connection.cursor(
            cursor_factory=psycopg2.extras.RealDictCursor
        ) as cursor:
            columns = tuple(rows[0]) if rows else ()
            if rows:
                values = [
                    tuple(
                        psycopg2.extras.Json(value)
                        if column == "unavailable_reasons"
                        else value
                        for column, value in (
                            (column, row[column]) for column in columns
                        )
                    )
                    for row in rows
                ]
                updates = ", ".join(
                    f"{column}=EXCLUDED.{column}"
                    for column in columns
                    if column not in {"snapshot_date", "ts_code"}
                )
                psycopg2.extras.execute_values(
                    cursor,
                    f"INSERT INTO technical_factor_snapshot ({', '.join(columns)}) VALUES %s "
                    f"ON CONFLICT (snapshot_date, ts_code) DO UPDATE SET {updates}, computed_at=NOW()",
                    values,
                    page_size=1000,
                )
            cursor.execute(
                """
                DELETE FROM technical_factor_snapshot AS snapshot
                WHERE snapshot.snapshot_date=%s
                  AND NOT EXISTS (
                      SELECT 1 FROM stock_basic AS stock
                      WHERE stock.ts_code=snapshot.ts_code
                        AND NULLIF(stock.list_date, '') IS NOT NULL
                        AND stock.list_date <= %s
                        AND (NULLIF(stock.delist_date, '') IS NULL OR stock.delist_date >= %s)
                  )
                """,
                (snapshot_date, compact_date, compact_date),
            )
            cursor.execute(
                """
                SELECT count(*) AS total,
                       count(*) FILTER (WHERE calculation_status='ready') AS ready,
                       count(*) FILTER (WHERE calculation_status='partial') AS partial,
                       count(*) FILTER (WHERE calculation_status='insufficient_history') AS insufficient_history,
                       count(*) FILTER (WHERE calculation_status='missing_input') AS missing_input,
                       count(*) FILTER (WHERE adjustment_status IN ('missing','stale','partial_history')) AS adjustment_incomplete,
                       count(*) FILTER (WHERE niumen_line IS NOT NULL AND confirmation_line IS NOT NULL) AS niumen_ready,
                       count(*) FILTER (WHERE cost_20_status='ready') AS cost_20_ready,
                       count(*) FILTER (WHERE cost_60_status='ready') AS cost_60_ready,
                       count(*) FILTER (WHERE common_indicator_status='ready') AS common_indicator_ready,
                       count(*) FILTER (WHERE parameterized_indicator_status='ready') AS parameterized_indicator_ready,
                       count(*) FILTER (WHERE ttm_squeeze_on) AS ttm_squeeze_on
                FROM technical_factor_snapshot WHERE snapshot_date=%s
                """,
                (snapshot_date,),
            )
            summary = dict(cursor.fetchone())
            if int(summary["total"]) != len(rows):
                raise RuntimeError(
                    "technical snapshot row count does not equal listed-stock universe"
                )
        connection.commit()
        return {
            "dataset": "technical_factor_snapshot",
            "snapshot_date": snapshot_date.isoformat(),
            "formula_version": FORMULA_VERSION,
            "rows_written": len(rows),
            **{key: int(value) for key, value in summary.items()},
        }
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def materialize_fama_french_daily(
    snapshot_date: date,
    *,
    source_execution_id: int | None = None,
) -> dict[str, Any]:
    """Materialize one session of SH/SZ A-share Fama-French factor returns.

    A single cross-section is computed from already-governed datasets: daily
    returns, total market cap, and the latest disclosed reported total equity. The
    eligible universe is Shanghai/Shenzhen A-shares listed at least
    ``MIN_LISTING_BARS`` sessions before ``snapshot_date``, excluding names
    present in the ST list for that session. Beijing/NEEQ securities are kept
    out explicitly because their historical daily-basic coverage starts on a
    different boundary. The risk-free rate is intentionally pinned to zero so
    the MKT premium equals the value-weighted SH/SZ return; this is recorded as
    part of the formula contract rather than silently sourcing an external rate.
    """

    compact_date = snapshot_date.strftime("%Y%m%d")
    connection = get_conn()
    try:
        with connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
            cursor.execute(
                """
                WITH listing_cutoff AS (
                    SELECT cal_date
                    FROM trade_cal
                    WHERE exchange = 'SSE'
                      AND is_open = 1
                      AND cal_date <= %(date)s
                    ORDER BY cal_date DESC
                    OFFSET %(min_bars_minus_one)s
                    LIMIT 1
                ), universe AS (
                    SELECT stock.ts_code
                    FROM stock_basic AS stock
                    CROSS JOIN listing_cutoff AS cutoff
                    WHERE NULLIF(stock.list_date, '') IS NOT NULL
                      AND stock.ts_code ~ '\\.(SH|SZ)$'
                      AND stock.list_date <= to_char(cutoff.cal_date, 'YYYYMMDD')
                      AND (
                          NULLIF(stock.delist_date, '') IS NULL
                          OR stock.delist_date > %(compact)s
                      )
                      AND NOT EXISTS (
                          SELECT 1 FROM stock_st AS st
                          WHERE st.ts_code = stock.ts_code
                            AND st.trade_date = %(compact)s
                      )
                )
                SELECT count(*) AS source_daily_count
                FROM daily AS d
                JOIN universe AS u ON u.ts_code = d.ts_code
                WHERE d.trade_date = %(date)s
                  AND d.pct_chg IS NOT NULL
                """,
                {
                    "date": snapshot_date,
                    "compact": compact_date,
                    "min_bars_minus_one": MIN_LISTING_BARS - 1,
                },
            )
            source_daily_count = int(cursor.fetchone()["source_daily_count"])
            cursor.execute(
                """
                WITH listing_cutoff AS (
                    SELECT cal_date
                    FROM trade_cal
                    WHERE exchange = 'SSE'
                      AND is_open = 1
                      AND cal_date <= %(date)s
                    ORDER BY cal_date DESC
                    OFFSET %(min_bars_minus_one)s
                    LIMIT 1
                ), universe AS (
                    SELECT stock.ts_code, stock.list_date
                    FROM stock_basic AS stock
                    CROSS JOIN listing_cutoff AS cutoff
                    WHERE NULLIF(stock.list_date, '') IS NOT NULL
                      AND stock.ts_code ~ '\\.(SH|SZ)$'
                      -- Eligibility means *listed* for 60 market sessions;
                      -- scanning the complete daily history for every name
                      -- merely to count those sessions is both slower and a
                      -- subtly different missing-bars test.
                      AND stock.list_date <= to_char(cutoff.cal_date, 'YYYYMMDD')
                      AND (
                          NULLIF(stock.delist_date, '') IS NULL
                          OR stock.delist_date > %(compact)s
                      )
                      AND NOT EXISTS (
                          SELECT 1 FROM stock_st AS st
                          WHERE st.ts_code = stock.ts_code
                            AND st.trade_date = %(compact)s
                      )
                ), eligible AS (
                    SELECT u.ts_code
                    FROM universe AS u
                ), day_returns AS (
                    SELECT d.ts_code, d.pct_chg
                    FROM daily AS d
                    JOIN eligible AS e ON e.ts_code = d.ts_code
                    WHERE d.trade_date = %(date)s
                      AND d.pct_chg IS NOT NULL
                ), day_caps AS (
                    SELECT v.ts_code, v.total_mv
                    FROM tushare_current_daily_basic AS v
                    JOIN eligible AS e ON e.ts_code = v.ts_code
                    WHERE v.trade_date = %(date)s
                      AND v.total_mv IS NOT NULL
                ), latest_equity AS (
                    SELECT DISTINCT ON (b.ts_code)
                           b.ts_code, b.total_hldr_eqy_inc_min_int
                    FROM balancesheet AS b
                    JOIN eligible AS e ON e.ts_code = b.ts_code
                    WHERE b.ann_date <= %(date)s
                      AND b.total_hldr_eqy_inc_min_int IS NOT NULL
                    ORDER BY b.ts_code, b.end_date DESC, b.ann_date DESC
                )
                SELECT dr.ts_code,
                       dr.pct_chg AS pct_chg,
                       dc.total_mv AS total_mv,
                       le.total_hldr_eqy_inc_min_int AS book_equity
                FROM day_returns AS dr
                JOIN day_caps AS dc ON dc.ts_code = dr.ts_code
                LEFT JOIN latest_equity AS le ON le.ts_code = dr.ts_code
                """,
                {
                    "date": snapshot_date,
                    "compact": compact_date,
                    "min_bars_minus_one": MIN_LISTING_BARS - 1,
                },
            )
            rows = [dict(item) for item in cursor.fetchall()]

        input_complete = fama_french_sources_complete(
            source_daily_count,
            len(rows),
        )

        returns = [float(item["pct_chg"]) / 100.0 for item in rows]
        caps = [float(item["total_mv"]) for item in rows]
        book_equity = [
            float(item["book_equity"]) if item["book_equity"] is not None else None
            for item in rows
        ]
        result = daily_factors(returns, caps, book_equity, risk_free=0.0)

        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO fama_french_daily (
                    trade_date, mkt, smb, hml, risk_free,
                    eligible_count, book_value_eligible_count,
                    small_count, big_count,
                    status, formula_version, source_execution_id
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (trade_date) DO UPDATE SET
                    mkt = EXCLUDED.mkt,
                    smb = EXCLUDED.smb,
                    hml = EXCLUDED.hml,
                    risk_free = EXCLUDED.risk_free,
                    eligible_count = EXCLUDED.eligible_count,
                    book_value_eligible_count = EXCLUDED.book_value_eligible_count,
                    small_count = EXCLUDED.small_count,
                    big_count = EXCLUDED.big_count,
                    status = EXCLUDED.status,
                    formula_version = EXCLUDED.formula_version,
                    source_execution_id = EXCLUDED.source_execution_id,
                    computed_at = NOW()
                """,
                (
                    snapshot_date,
                    result["mkt"],
                    result["smb"],
                    result["hml"],
                    0.0,
                    result["eligible_count"],
                    result["book_value_eligible_count"],
                    result["small_count"],
                    result["big_count"],
                    result["status"],
                    result["formula_version"],
                    source_execution_id,
                ),
            )
        connection.commit()
        return {
            "dataset": "fama_french_daily",
            "snapshot_date": snapshot_date.isoformat(),
            "formula_version": FF3_FORMULA_VERSION,
            "status": result["status"],
            # Keep the diagnostic row, but do not let the generic row-exists
            # coverage audit certify a day whose six portfolios could not be
            # constructed.  The V2 runtime turns this into an actionable
            # non-retryable execution instead of publishing dataset ready.
            "publishable": result["status"] == "ready" and input_complete,
            "input_complete": input_complete,
            "source_daily_count": source_daily_count,
            "matched_daily_cap_count": len(rows),
            "eligible_count": result["eligible_count"],
            "book_value_eligible_count": result["book_value_eligible_count"],
            "small_count": result["small_count"],
            "big_count": result["big_count"],
            "mkt": result["mkt"],
            "smb": result["smb"],
            "hml": result["hml"],
            "risk_free": 0.0,
        }
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def run_transformation(
    task_key: str,
    observation_date: date,
    *,
    source_execution_id: int | None = None,
) -> dict[str, Any]:
    handlers = {
        "technical_factor_snapshot": materialize_technical_factor_snapshot,
        "fama_french_daily": materialize_fama_french_daily,
    }
    try:
        handler = handlers[task_key]
    except KeyError as exc:
        raise LookupError(f"no code-owned transformation handler: {task_key}") from exc
    return handler(observation_date, source_execution_id=source_execution_id)
