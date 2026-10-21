#!/usr/bin/env python3
"""Compare per-day entity counts for related market datasets.

Date continuity alone cannot detect a truncated response: one row is enough to
make a partition exist.  This read-only diagnostic compares each target with a
same-day reference universe and reports low-coverage partitions.  The ratios
are diagnostics rather than provider guarantees; each pair records its chosen
threshold and only evaluates dates from the target's first stored partition.
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
class CrossSectionProbe:
    target: str
    reference: str
    min_ratio: float
    rationale: str


PROBES = (
    CrossSectionProbe("daily_basic", "stock_daily", 0.90, "A-share daily valuation versus bars"),
    CrossSectionProbe("adj_factor", "stock_daily", 0.98, "adjustment factors versus bars"),
    CrossSectionProbe("stock_limit", "stock_daily", 0.90, "daily price limits versus bars"),
    CrossSectionProbe("moneyflow", "stock_daily", 0.85, "money flow versus bars"),
    CrossSectionProbe("cyq_perf", "stock_daily", 0.90, "chip metrics versus bars"),
    CrossSectionProbe("cyq_chips", "stock_daily", 0.90, "chip price bands versus bars"),
    CrossSectionProbe("stk_factor", "stock_daily", 0.90, "technical factors versus bars"),
    CrossSectionProbe("stk_factor_pro", "stock_daily", 0.90, "pro factors versus bars"),
    CrossSectionProbe(
        "technical_factor_snapshot", "stock_daily", 0.90,
        "locally materialized technical snapshot versus bars",
    ),
    CrossSectionProbe("fund_adj", "fund_daily", 0.90, "fund adjustment factors versus fund bars"),
    CrossSectionProbe("fund_factor_pro", "fund_daily", 0.90, "fund factors versus fund bars"),
    CrossSectionProbe("cb_factor_pro", "cb_daily", 0.90, "convertible-bond factors versus bond bars"),
)


def _date_expression(dataset, alias: str):
    column = sql.SQL("{}.{}").format(sql.Identifier(alias), sql.Identifier(dataset.date_column))
    if dataset.date_storage == DateStorage.COMPACT:
        return sql.SQL("to_date(NULLIF({}, ''), 'YYYYMMDD')").format(column)
    if dataset.date_storage == DateStorage.MONTH:
        return sql.SQL(
            "(to_date(NULLIF({}, ''), 'YYYYMM') + INTERVAL '1 month - 1 day')::date"
        ).format(column)
    return sql.SQL("{}::date").format(column)


def run(end_date: date) -> dict:
    database = Database(DB_CONFIG, min_connections=1, max_connections=1)
    results = []
    try:
        with database.connection() as connection, connection.cursor() as cursor:
            for probe in PROBES:
                target = DATASETS.get(probe.target)
                reference = DATASETS.get(probe.reference)
                target_date = _date_expression(target, "t")
                reference_date = _date_expression(reference, "r")
                cursor.execute(
                    sql.SQL("SELECT min({d}) FROM {table} AS t WHERE {d}<=%s").format(
                        d=target_date,
                        table=sql.Identifier(target.freshness_read_table),
                    ),
                    (end_date,),
                )
                first_date = cursor.fetchone()[0]
                if first_date is None:
                    results.append({
                        "target": probe.target,
                        "reference": probe.reference,
                        "status": "empty_unverified",
                        "first_date": None,
                        "end_date": end_date.isoformat(),
                        "min_ratio_required": probe.min_ratio,
                        "compared_dates": 0,
                        "missing_target_dates": 0,
                        "low_ratio_dates": 0,
                        "minimum_ratio": None,
                        "problem_sample": [],
                        "rationale": probe.rationale,
                    })
                    continue

                statement = sql.SQL(
                    "WITH target_counts AS ("
                    " SELECT {td} AS day, count(DISTINCT t.ts_code) AS entity_count"
                    " FROM {tt} AS t WHERE {td} BETWEEN %s AND %s GROUP BY 1"
                    "), reference_counts AS ("
                    " SELECT {rd} AS day, count(DISTINCT r.ts_code) AS entity_count"
                    " FROM {rt} AS r WHERE {rd} BETWEEN %s AND %s GROUP BY 1"
                    ") SELECT r.day, coalesce(t.entity_count,0), r.entity_count,"
                    " CASE WHEN r.entity_count=0 THEN NULL"
                    " ELSE coalesce(t.entity_count,0)::double precision/r.entity_count END AS ratio"
                    " FROM reference_counts AS r LEFT JOIN target_counts AS t USING(day)"
                    " ORDER BY r.day"
                ).format(
                    td=target_date,
                    tt=sql.Identifier(target.freshness_read_table),
                    rd=reference_date,
                    rt=sql.Identifier(reference.freshness_read_table),
                )
                cursor.execute(statement, (first_date, end_date, first_date, end_date))
                partitions = cursor.fetchall()
                missing = [row for row in partitions if row[1] == 0]
                low = [
                    row for row in partitions
                    if row[3] is not None and row[3] < probe.min_ratio
                ]
                problems = sorted(low, key=lambda row: (row[3], row[0]))[:20]
                minimum = min((row[3] for row in partitions if row[3] is not None), default=None)
                results.append({
                    "target": probe.target,
                    "reference": probe.reference,
                    "status": "cross_section_pass" if not low else "cross_section_gaps",
                    "first_date": first_date.isoformat(),
                    "end_date": end_date.isoformat(),
                    "min_ratio_required": probe.min_ratio,
                    "compared_dates": len(partitions),
                    "missing_target_dates": len(missing),
                    "low_ratio_dates": len(low),
                    "minimum_ratio": round(minimum, 6) if minimum is not None else None,
                    "problem_sample": [
                        {
                            "date": row[0].isoformat(),
                            "target_entities": row[1],
                            "reference_entities": row[2],
                            "ratio": round(row[3], 6),
                        }
                        for row in problems
                    ],
                    "rationale": probe.rationale,
                    "boundary": (
                        "comparison starts at target's first stored date; it does not prove "
                        "that this is the provider's true availability start"
                    ),
                })
    finally:
        database.close()

    return {
        "contract": "daily-cross-section-diagnostic@v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "end_date": end_date.isoformat(),
        "summary": {
            "datasets": len(results),
            "cross_section_pass": sum(r["status"] == "cross_section_pass" for r in results),
            "cross_section_gaps": sum(r["status"] == "cross_section_gaps" for r in results),
            "empty_unverified": sum(r["status"] == "empty_unverified" for r in results),
            "low_ratio_partitions": sum(r["low_ratio_dates"] for r in results),
        },
        "datasets": results,
    }


def markdown(report: dict) -> str:
    lines = [
        "# 日频数据横截面完整性诊断",
        "",
        f"生成时间：`{report['generated_at']}`",
        f"检查截止：`{report['end_date']}`",
        "",
        "同一天有记录并不代表采集完整。本报告将目标数据的证券数与同日行情证券数比较。",
        "阈值用于发现截断和漏采；它不是对上游证券适用范围的永久定义。",
        "",
        "| 目标 | 同日参照 | 首日 | 比较日数 | 最低比例 | 低于阈值日数 | 结果 |",
        "|---|---|---|---:|---:|---:|---|",
    ]
    for item in report["datasets"]:
        minimum = "-" if item["minimum_ratio"] is None else f"{item['minimum_ratio']:.3f}"
        lines.append(
            f"| {item['target']} | {item['reference']} | {item['first_date'] or '-'} | "
            f"{item['compared_dates']} | {minimum} | {item['low_ratio_dates']} | "
            f"{item['status']} |"
        )
    lines.extend(("", "## 最低覆盖分区样本", ""))
    for item in report["datasets"]:
        if not item["problem_sample"]:
            continue
        sample = "; ".join(
            f"{row['date']}={row['target_entities']}/{row['reference_entities']} "
            f"({row['ratio']:.3f})"
            for row in item["problem_sample"]
        )
        lines.append(f"- `{item['target']}`：{sample}")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--end-date", type=date.fromisoformat, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = run(args.end_date)
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "daily-cross-sections.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    )
    (args.output / "daily-cross-sections.md").write_text(markdown(report))
    print(json.dumps(report["summary"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
