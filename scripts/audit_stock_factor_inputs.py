#!/usr/bin/env python3
"""Produce a reproducible stock/factor-input gap breakdown from canonical data."""

from __future__ import annotations

import argparse
from datetime import date, datetime
import json
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from service.db import query


def _one(statement: str, params: tuple) -> dict:
    rows = query(statement, params)
    return dict(rows[0]) if rows else {}


def build_report(start: date, end: date) -> dict:
    bounds = (start, end)
    partitions = _one(
        """
        WITH calendar AS (
            SELECT cal_date
            FROM trade_cal
            WHERE exchange='SSE' AND is_open=1
              AND cal_date BETWEEN %s AND %s
        ), daily_rows AS (
            SELECT trade_date, count(*) AS rows
            FROM daily WHERE trade_date BETWEEN %s AND %s GROUP BY trade_date
        ), basic_rows AS (
            SELECT trade_date, count(*) AS rows
            FROM tushare_current_daily_basic
            WHERE trade_date BETWEEN %s AND %s GROUP BY trade_date
        ), factor_rows AS (
            SELECT trade_date, count(DISTINCT ts_code) AS rows
            FROM tushare_norm_adj_factor
            WHERE trade_date BETWEEN %s AND %s GROUP BY trade_date
        ), limit_rows AS (
            SELECT trade_date, count(*) AS rows
            FROM stk_limit WHERE trade_date BETWEEN %s AND %s GROUP BY trade_date
        ), ff3_rows AS (
            SELECT trade_date, count(*) AS rows
            FROM fama_french_daily
            WHERE trade_date BETWEEN %s AND %s GROUP BY trade_date
        )
        SELECT count(*) AS expected_sessions,
               count(*) FILTER (WHERE COALESCE(daily_rows.rows,0)=0)
                   AS stock_daily_missing_sessions,
               count(*) FILTER (WHERE COALESCE(basic_rows.rows,0)=0)
                   AS daily_basic_missing_sessions,
               count(*) FILTER (WHERE COALESCE(factor_rows.rows,0)=0)
                   AS adj_factor_missing_sessions,
               count(*) FILTER (WHERE COALESCE(limit_rows.rows,0)=0)
                   AS stock_limit_missing_sessions,
               count(*) FILTER (WHERE COALESCE(ff3_rows.rows,0)=0)
                   AS fama_french_missing_sessions
        FROM calendar
        LEFT JOIN daily_rows ON daily_rows.trade_date=calendar.cal_date
        LEFT JOIN basic_rows ON basic_rows.trade_date=calendar.cal_date
        LEFT JOIN factor_rows ON factor_rows.trade_date=calendar.cal_date
        LEFT JOIN limit_rows ON limit_rows.trade_date=calendar.cal_date
        LEFT JOIN ff3_rows ON ff3_rows.trade_date=calendar.cal_date
        """,
        bounds * 6,
    )

    missing_by_dataset = {}
    references = {
        "daily_basic": "tushare_current_daily_basic",
        "adj_factor": """(
            SELECT DISTINCT ON (ts_code,trade_date) ts_code,trade_date
            FROM tushare_norm_adj_factor
            WHERE trade_date BETWEEN %s AND %s
            ORDER BY ts_code,trade_date,_last_seen_at DESC,_record_hash DESC
        )""",
        "stock_limit": "stk_limit",
    }
    for dataset, table in references.items():
        extra_params: tuple = ()
        if dataset == "adj_factor":
            extra_params = bounds
        rows = query(
            f"""
            SELECT right(source.ts_code,2) AS exchange_suffix,
                   count(*) AS missing_rows,
                   count(DISTINCT source.trade_date) AS affected_sessions,
                   min(source.trade_date) AS first_date,
                   max(source.trade_date) AS last_date
            FROM daily AS source
            LEFT JOIN {table} AS target
              ON target.ts_code=source.ts_code
             AND target.trade_date=source.trade_date
            WHERE source.trade_date BETWEEN %s AND %s
              AND target.ts_code IS NULL
            GROUP BY right(source.ts_code,2)
            ORDER BY missing_rows DESC
            """,
            extra_params + bounds,
        )
        missing_by_dataset[dataset] = [dict(item) for item in rows]

    null_price_fields = query(
        """
        SELECT right(ts_code,2) AS exchange_suffix,
               count(*) AS rows,
               count(*) FILTER (WHERE open IS NULL OR high IS NULL
                                      OR low IS NULL OR close IS NULL) AS ohlc_null_rows,
               count(*) FILTER (WHERE pre_close IS NULL) AS pre_close_null_rows,
               count(*) FILTER (WHERE vol IS NULL OR amount IS NULL)
                   AS volume_null_rows,
               min(trade_date) AS first_date, max(trade_date) AS last_date
        FROM daily
        WHERE trade_date BETWEEN %s AND %s
          AND (open IS NULL OR high IS NULL OR low IS NULL OR close IS NULL
               OR pre_close IS NULL OR vol IS NULL OR amount IS NULL)
        GROUP BY right(ts_code,2)
        ORDER BY rows DESC
        """,
        bounds,
    )

    technical = query(
        """
        WITH calendar AS (
            SELECT cal_date
            FROM trade_cal
            WHERE exchange='SSE' AND is_open=1
              AND cal_date BETWEEN GREATEST(%s::date, DATE '2026-10-09') AND %s
        ), actual AS (
            SELECT snapshot_date, count(*) AS rows
            FROM technical_factor_snapshot
            WHERE snapshot_date BETWEEN GREATEST(%s::date, DATE '2026-10-09') AND %s
            GROUP BY snapshot_date
        ), expected AS (
            SELECT calendar.cal_date,
                   count(stock.*) AS rows
            FROM calendar
            LEFT JOIN stock_basic AS stock
              ON NULLIF(stock.list_date,'') IS NOT NULL
             AND to_date(stock.list_date,'YYYYMMDD')<=calendar.cal_date
             AND (NULLIF(stock.delist_date,'') IS NULL
                  OR to_date(stock.delist_date,'YYYYMMDD')>=calendar.cal_date)
            GROUP BY calendar.cal_date
        )
        SELECT expected.cal_date AS trade_date,
               expected.rows AS expected_rows,
               COALESCE(actual.rows,0) AS actual_rows,
               expected.rows-COALESCE(actual.rows,0) AS missing_rows
        FROM expected LEFT JOIN actual ON actual.snapshot_date=expected.cal_date
        WHERE expected.rows<>COALESCE(actual.rows,0)
        ORDER BY expected.cal_date
        """,
        bounds * 2,
    )

    cyq = query(
        """
        WITH recent_dates AS (
            SELECT cal_date
            FROM trade_cal
            WHERE exchange='SSE' AND is_open=1 AND cal_date<=%s
            ORDER BY cal_date DESC LIMIT 20
        ), expected AS (
            SELECT daily.trade_date, count(*) AS rows
            FROM daily JOIN recent_dates ON recent_dates.cal_date=daily.trade_date
            GROUP BY daily.trade_date
        ), actual AS (
            SELECT cyq_perf.trade_date, count(*) AS rows
            FROM cyq_perf JOIN recent_dates ON recent_dates.cal_date=cyq_perf.trade_date
            GROUP BY cyq_perf.trade_date
        )
        SELECT expected.trade_date, expected.rows AS expected_rows,
               COALESCE(actual.rows,0) AS actual_rows,
               round(COALESCE(actual.rows,0)::numeric/expected.rows,6)
                   AS coverage_ratio
        FROM expected LEFT JOIN actual USING(trade_date)
        WHERE COALESCE(actual.rows,0)<expected.rows
        ORDER BY expected.trade_date
        """,
        (end,),
    )

    sh_sz_blockers = sum(
        int(item["missing_rows"])
        for rows in missing_by_dataset.values()
        for item in rows
        if item["exchange_suffix"] in {"SH", "SZ"}
    )
    technical_missing = sum(int(item["missing_rows"]) for item in technical)
    core_ready = (
        all(int(value) == 0 for key, value in partitions.items() if key != "expected_sessions")
        and sh_sz_blockers == 0
        and technical_missing == 0
    )
    return {
        "generated_at": datetime.now().astimezone().isoformat(),
        "scope": {"start": start.isoformat(), "end": end.isoformat()},
        "status": "pass_with_documented_boundaries" if core_ready else "blocked",
        "partition_completeness": partitions,
        "cross_section_missing": missing_by_dataset,
        "null_price_fields": [dict(item) for item in null_price_fields],
        "technical_snapshot_mismatches": [dict(item) for item in technical],
        "cyq_recent_incomplete_sessions": [dict(item) for item in cyq],
        "classification": {
            "fixable_pipeline_gaps": {
                "technical_snapshot_missing_rows": technical_missing,
                "sh_sz_cross_section_missing_rows": sh_sz_blockers,
            },
            "documented_source_boundaries": {
                "bj_daily_basic_and_limit_before_2023": (
                    "Tushare daily_basic and stk_limit omit most Beijing-market "
                    "history through 2022-12-30; stock bars and adjustment factors exist"
                ),
                "bj_pre_close_nulls": (
                    "twelve provider rows have valid OHLC/volume but no pre_close; "
                    "they remain explicit nulls rather than fabricated prices"
                ),
            },
            "optional_repair_in_progress": {
                "cyq_perf": bool(cyq),
                "incomplete_sessions": len(cyq),
            },
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", type=date.fromisoformat, default=date(2021, 10, 20))
    parser.add_argument("--end", type=date.fromisoformat, default=date.today())
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = build_report(args.start, args.end)
    rendered = json.dumps(report, ensure_ascii=False, default=str, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if report["status"] != "blocked" else 2


if __name__ == "__main__":
    raise SystemExit(main())
