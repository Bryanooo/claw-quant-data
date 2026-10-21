#!/usr/bin/env python3
"""Probe daily-shaped datasets that are not protected by expected calendars.

The primary coverage registry remains authoritative.  This read-only diagnostic
targets the weaker ``observed_scope_transport`` class: if a whole day was never
collected, an observed-only audit cannot see it.  Every probe states which
calendar approximation it uses and never upgrades a diagnostic date mismatch
to authoritative completeness.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import date, datetime, timezone
import json
from pathlib import Path

from psycopg2 import sql

from service.config import DB_CONFIG
from service.data_service.database import Database
from service.data_service.models import DateStorage
from service.data_service.registry import DATASETS


@dataclass(frozen=True)
class DailyProbe:
    dataset: str
    calendar: str
    semantics: str


# Only datasets whose public contract describes daily observations and whose
# primary coverage rule is currently observed-only belong here.  Sparse event
# publications are explicit: an absent row needs an exact-date, verified-empty
# request before it can be called complete.
DAILY_PROBES = (
    DailyProbe("daily_basic", "SSE", "continuous"),
    DailyProbe("cyq_chips", "SSE", "continuous"),
    DailyProbe("cb_factor_pro", "SSE", "continuous"),
    DailyProbe("fund_factor_pro", "SSE", "continuous"),
    DailyProbe("fut_daily", "SSE", "continuous"),
    DailyProbe("fut_index_daily", "SSE", "continuous"),
    DailyProbe("fut_settle", "SSE", "continuous"),
    DailyProbe("opt_daily", "SSE", "continuous"),
    DailyProbe("repo_daily", "SSE", "continuous"),
    DailyProbe("dc_index", "SSE", "continuous"),
    DailyProbe("dc_member", "SSE", "continuous"),
    DailyProbe("etf_sh_cons", "SSE", "continuous"),
    DailyProbe("etf_sz_cons", "SSE", "continuous"),
    DailyProbe("factor_value", "SSE", "continuous"),
    DailyProbe("moneyflow_dc", "SSE", "continuous"),
    DailyProbe("stk_ah_comparison", "CONNECT", "continuous"),
    DailyProbe("stk_nineturn", "SSE", "continuous"),
    DailyProbe("stock_st", "SSE", "continuous"),
    DailyProbe("hk_daily", "HK", "continuous"),
    DailyProbe("moneyflow_hsgt", "CONNECT", "continuous"),
    DailyProbe("ggt_daily", "CONNECT", "continuous"),
    DailyProbe("hsgt_top10", "CONNECT", "sparse_daily"),
    DailyProbe("fut_holding", "SSE", "sparse_daily"),
    DailyProbe("shibor_quote", "SSE", "publication_daily"),
    DailyProbe("forex_daily", "WEEKDAY", "multi_market_daily"),
    DailyProbe("index_global", "WEEKDAY", "multi_market_daily"),
    DailyProbe("hibor", "HK", "publication_daily"),
    DailyProbe("libor", "WEEKDAY", "discontinued_daily"),
    DailyProbe("us_tbr", "US", "publication_daily"),
    DailyProbe("us_tltr", "US", "publication_daily"),
    DailyProbe("us_trltr", "US", "publication_daily"),
    DailyProbe("us_trycr", "US", "publication_daily"),
    DailyProbe("us_tycr", "US", "publication_daily"),
    DailyProbe("limit_list_d", "SSE", "sparse_daily"),
    DailyProbe("limit_list_ths", "SSE", "sparse_daily"),
    DailyProbe("stock_suspend", "SSE", "sparse_daily"),
    DailyProbe("top_list", "SSE", "sparse_daily"),
    DailyProbe("stk_alert", "SSE", "sparse_daily"),
    DailyProbe("stk_high_shock", "SSE", "sparse_daily"),
    DailyProbe("stk_shock", "SSE", "sparse_daily"),
)


def _date_expression(dataset):
    column = sql.Identifier(dataset.date_column)
    if dataset.date_storage == DateStorage.COMPACT:
        return sql.SQL("to_date(NULLIF({}, ''), 'YYYYMMDD')").format(column)
    if dataset.date_storage == DateStorage.MONTH:
        return sql.SQL(
            "(to_date(NULLIF({}, ''), 'YYYYMM') + "
            "INTERVAL '1 month - 1 day')::date"
        ).format(column)
    return sql.SQL("{}::date").format(column)


def _calendar_statement(calendar: str) -> str:
    if calendar == "SSE":
        return (
            "SELECT cal_date FROM trade_cal WHERE exchange='SSE' AND is_open=1 "
            "AND cal_date BETWEEN %s AND %s"
        )
    if calendar == "HK":
        return (
            "SELECT cal_date FROM tushare_norm_hk_tradecal WHERE is_open=1 "
            "AND cal_date BETWEEN %s AND %s"
        )
    if calendar == "US":
        return (
            "SELECT cal_date FROM tushare_norm_us_tradecal WHERE is_open=1 "
            "AND cal_date BETWEEN %s AND %s"
        )
    if calendar == "CONNECT":
        return (
            "SELECT s.cal_date FROM trade_cal AS s "
            "JOIN tushare_norm_hk_tradecal AS h USING (cal_date) "
            "WHERE s.exchange='SSE' AND s.is_open=1 AND h.is_open=1 "
            "AND s.cal_date BETWEEN %s AND %s"
        )
    if calendar == "WEEKDAY":
        return (
            "SELECT day::date FROM generate_series(%s::date,%s::date,"
            "INTERVAL '1 day') AS day WHERE extract(isodow FROM day)<6"
        )
    raise ValueError(f"unsupported calendar: {calendar}")


def run(end_date: date) -> dict:
    database = Database(DB_CONFIG, min_connections=1, max_connections=1)
    rows = []
    try:
        with database.connection() as connection, connection.cursor() as cursor:
            for probe in DAILY_PROBES:
                dataset = DATASETS.get(probe.dataset)
                expression = _date_expression(dataset)
                table = sql.Identifier(dataset.freshness_read_table)
                cursor.execute(
                    sql.SQL(
                        "SELECT min({d}), max({d}), count(DISTINCT {d}) "
                        "FROM {t} WHERE {d}<=%s"
                    ).format(d=expression, t=table),
                    (end_date,),
                )
                first_date, latest_date, observed_count = cursor.fetchone()
                if first_date is None:
                    rows.append({
                        "dataset": probe.dataset,
                        "calendar": probe.calendar,
                        "semantics": probe.semantics,
                        "status": "empty_unverified",
                        "first_date": None,
                        "latest_date": None,
                        "expected_dates": 0,
                        "observed_dates": 0,
                        "date_mismatches": 0,
                        "missing_date_sample": [],
                        "boundary": "no stored observation",
                    })
                    continue
                cursor.execute(
                    _calendar_statement(probe.calendar),
                    (first_date, end_date),
                )
                expected = {item[0] for item in cursor.fetchall()}
                cursor.execute(
                    sql.SQL(
                        "SELECT DISTINCT {d} FROM {t} "
                        "WHERE {d} BETWEEN %s AND %s"
                    ).format(d=expression, t=table),
                    (first_date, end_date),
                )
                observed = {item[0] for item in cursor.fetchall()}
                missing = sorted(expected - observed)
                if not missing:
                    status = "date_continuity_pass"
                elif probe.semantics == "continuous":
                    status = "date_gaps"
                else:
                    status = "requires_calendar_or_empty_proof"
                rows.append({
                    "dataset": probe.dataset,
                    "calendar": probe.calendar,
                    "semantics": probe.semantics,
                    "status": status,
                    "first_date": first_date.isoformat(),
                    "latest_date": latest_date.isoformat(),
                    "expected_dates": len(expected),
                    "observed_dates": len(observed),
                    "date_mismatches": len(missing),
                    "missing_date_sample": [item.isoformat() for item in missing[-20:]],
                    "boundary": (
                        "starts at first stored date; earlier provider history still "
                        "requires an independently proven availability boundary"
                    ),
                })
    finally:
        database.close()
    return {
        "contract": "daily-dataset-partition-diagnostic@v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "end_date": end_date.isoformat(),
        "semantics": (
            "Read-only date-presence probe for daily-shaped observed-only datasets. "
            "Continuous mismatches are gaps from the first stored date; sparse and "
            "publication calendars require exact verified-empty transport evidence."
        ),
        "summary": {
            "datasets": len(rows),
            "date_continuity_pass": sum(
                item["status"] == "date_continuity_pass" for item in rows
            ),
            "date_gaps": sum(item["status"] == "date_gaps" for item in rows),
            "requires_calendar_or_empty_proof": sum(
                item["status"] == "requires_calendar_or_empty_proof" for item in rows
            ),
            "empty_unverified": sum(
                item["status"] == "empty_unverified" for item in rows
            ),
        },
        "datasets": rows,
    }


def markdown(report: dict) -> str:
    lines = [
        "# 日频数据逐日连续性诊断",
        "",
        f"生成时间：`{report['generated_at']}`",
        f"检查截止：`{report['end_date']}`",
        "",
        "此报告专门检查当前仅有 observed-scope 证明的日频接口。日期不匹配不自动触发采集；",
        "稀疏事件和多市场序列必须先取得正确日历或权威空响应，不能把空日伪造成缺失数据。",
        "",
        "| 数据集 | 日历 | 语义 | 首日 | 末日 | 日期不匹配 | 结果 |",
        "|---|---|---|---|---|---:|---|",
    ]
    for item in report["datasets"]:
        lines.append(
            f"| {item['dataset']} | {item['calendar']} | {item['semantics']} | "
            f"{item['first_date'] or '-'} | {item['latest_date'] or '-'} | "
            f"{item['date_mismatches']} | {item['status']} |"
        )
    lines.extend(("", "## 异常日期样本", ""))
    for item in report["datasets"]:
        if item["date_mismatches"] or item["status"] == "empty_unverified":
            sample = ", ".join(item["missing_date_sample"]) or "无存量记录"
            lines.append(f"- `{item['dataset']}`：{sample}")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--end-date", type=date.fromisoformat, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = run(args.end_date)
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "daily-partitions.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    )
    (args.output / "daily-partitions.md").write_text(markdown(report))
    print(json.dumps(report["summary"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
