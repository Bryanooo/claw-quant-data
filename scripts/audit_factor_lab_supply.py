#!/usr/bin/env python3
"""Audit the governed claw-data surface consumed by claw-factor-lab.

The command is deliberately read-only.  It combines the dataset registry,
strict coverage results, delivery bundles and representative HTTP timings into
one reproducible JSON/Markdown acceptance artifact.  Collection and repair
remain explicit operator actions so an audit cannot spend provider quota.
"""

from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
import json
from pathlib import Path
import statistics
import time
from urllib.parse import urlencode
from urllib.request import urlopen


DOMAINS = {
    "stock_core": (
        "stock_basic", "stock_company", "bse_mapping", "namechange",
        "trade_calendar", "stock_daily", "stock_daily_basic", "adj_factor",
        "stock_limit", "stock_suspend", "stock_st",
    ),
    "stock_financial": (
        "income", "balancesheet", "cashflow", "financial_indicator",
        "forecast", "express", "fina_audit", "fina_mainbz",
        "disclosure_date", "report_rc",
    ),
    "corporate_events": (
        "dividend", "repurchase", "share_float", "new_share",
        "pledge_detail", "pledge_stat", "top10_holders",
        "top10_floatholders", "stk_holdernumber", "stk_holdertrade",
        "stk_managers", "stk_rewards",
    ),
    "company_news": (
        "major_news", "broker_recommend", "report_rc",
    ),
    "flow_sentiment": (
        "moneyflow", "margin", "margin_detail", "margin_secs", "hk_hold",
        "stock_hsgt", "hsgt_top10", "ggt_top10", "block_trade", "top_list",
        "top_inst", "cyq_chips", "cyq_perf", "stk_factor",
        "stk_factor_pro", "factor_value", "fama_french_daily",
        "technical_factor_snapshot",
    ),
    "etf": (
        "fund_basic", "etf_basic", "etf_index", "fund_daily", "fund_adj",
        "etf_share_size", "etf_sh_cons", "etf_sz_cons", "fund_company",
        "fund_manager", "fund_nav", "fund_share", "fund_portfolio",
        "fund_div", "fund_factor_pro", "mkt_idx_bmk",
    ),
    "index_industry": (
        "index_basic", "index_daily", "index_classify", "index_member_all",
        "ci_index_member", "index_weight", "sw_daily", "ci_daily",
        "industry_daily", "ths_index", "idx_factor_pro", "idx_anns",
        "daily_info",
    ),
    "macro": (
        "cn_gdp", "cn_cpi", "cn_pmi", "cn_ppi", "cn_m", "sf_month",
        "cn_lpr", "shibor", "shibor_quote", "libor", "hibor", "gz_index",
        "wz_index", "us_tbr", "us_tltr", "us_trltr", "us_trycr", "us_tycr",
        "repo_daily", "eco_cal", "cn_schedule",
    ),
}

BENCHMARKS = (
    ("stock_daily", {"date": "2026-10-20", "limit": 1000}),
    ("income", {"ts_code": "000001.SZ", "limit": 1000}),
    ("dividend", {"ts_code": "000001.SZ", "limit": 1000}),
    ("major_news", {"limit": 1000}),
    ("cyq_perf", {"date": "2026-10-20", "limit": 1000}),
    ("fund_daily", {"date": "2026-10-20", "limit": 1000}),
    ("index_daily", {"date": "2026-10-20", "limit": 1000}),
    ("cn_cpi", {"limit": 1000}),
)


def get_json(base_url: str, path: str, params: dict | None = None) -> object:
    query = f"?{urlencode(params)}" if params else ""
    with urlopen(base_url.rstrip("/") + path + query, timeout=30) as response:
        return json.load(response)


def benchmark(base_url: str, repeats: int) -> list[dict]:
    results = []
    for dataset, params in BENCHMARKS:
        samples = []
        payload = None
        for _ in range(repeats):
            started = time.perf_counter()
            payload = get_json(
                base_url, f"/api/v1/data/datasets/{dataset}/records", params
            )
            samples.append((time.perf_counter() - started) * 1000)
        assert isinstance(payload, dict)
        results.append({
            "dataset": dataset,
            "rows": len(payload["data"]),
            "p50_ms": round(statistics.median(samples), 3),
            "max_ms": round(max(samples), 3),
            "has_more": payload["page"]["has_more"],
        })
    return results


def run(base_url: str, repeats: int) -> dict:
    registry = get_json(base_url, "/api/v1/data/datasets")
    freshness = get_json(base_url, "/api/v1/data/freshness")
    coverage = get_json(base_url, "/api/v1/ops/coverage")
    contracts = get_json(base_url, "/api/v1/research/factor-inputs")
    assert isinstance(registry, list)
    assert isinstance(freshness, list)
    assert isinstance(coverage, dict)
    assert isinstance(contracts, dict)
    registered = {item["name"] for item in registry}
    delivered = {
        dataset["name"]
        for bundle in contracts["bundles"]
        for dataset in bundle["datasets"]
    }
    latest = {
        item["dataset"]: item.get("latest") or {}
        for item in coverage["datasets"]
    }
    freshness_by_dataset = {item["dataset"]: item for item in freshness}
    today = datetime.now(timezone.utc).date()
    domains = {}
    for domain, datasets in DOMAINS.items():
        rows = []
        for dataset in datasets:
            status = latest.get(dataset, {}).get("status", "not_audited")
            freshness_status = freshness_by_dataset.get(dataset, {}).get(
                "status", "not_reported"
            )
            verified_end = latest.get(dataset, {}).get("verified_end_date")
            transport_current_empty = bool(
                freshness_status == "stale"
                and status == "complete"
                and latest.get(dataset, {}).get("evidence", {}).get(
                    "strict_audit_mode"
                ) == "observed_scope_transport"
                and verified_end
                and (today - date.fromisoformat(verified_end)).days <= 3
            )
            rows.append({
                "dataset": dataset,
                "registered": dataset in registered,
                "delivered_to_factor_lab": dataset in delivered,
                "coverage_status": status,
                "freshness_status": freshness_status,
                "freshness_accepted_by_verified_empty_scope": (
                    transport_current_empty
                ),
                "missing_partitions": latest.get(dataset, {}).get(
                    "missing_partitions", 0
                ),
                "partial_partitions": latest.get(dataset, {}).get(
                    "partial_partitions", 0
                ),
            })
        domains[domain] = {
            "accepted": all(
                row["registered"]
                and row["delivered_to_factor_lab"]
                and row["coverage_status"] in {"complete", "empty"}
                and (
                    row["freshness_status"] not in {"stale", "empty"}
                    or row["freshness_accepted_by_verified_empty_scope"]
                )
                for row in rows
            ),
            "datasets": rows,
        }
    timings = benchmark(base_url, repeats)
    return {
        "contract": "factor-lab-supply-audit@v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "base_url": base_url,
        "accepted": all(item["accepted"] for item in domains.values())
        and all(item["p50_ms"] <= 500 for item in timings),
        "latency_slo_ms": 500,
        "domains": domains,
        "benchmarks": timings,
        "coverage_summary": coverage["summary"],
    }


def markdown(report: dict) -> str:
    lines = [
        "# Factor-lab 数据供应验收",
        "",
        f"生成时间：`{report['generated_at']}`",
        "",
        f"总结果：**{'通过' if report['accepted'] else '未通过'}**",
        "",
        "| 领域 | 数据集数 | 结果 | 异常数据集 |",
        "|---|---:|---|---|",
    ]
    for name, domain in report["domains"].items():
        bad = [
            row["dataset"]
            for row in domain["datasets"]
            if not (
                row["registered"]
                and row["delivered_to_factor_lab"]
                and row["coverage_status"] in {"complete", "empty"}
                and (
                    row["freshness_status"] not in {"stale", "empty"}
                    or row["freshness_accepted_by_verified_empty_scope"]
                )
            )
        ]
        lines.append(
            f"| {name} | {len(domain['datasets'])} | "
            f"{'通过' if domain['accepted'] else '未通过'} | "
            f"{', '.join(bad) or '-'} |"
        )
    lines.extend((
        "", "## 查询性能", "",
        "| 数据集 | 返回行数 | P50 | 最大值 |", "|---|---:|---:|---:|",
    ))
    for item in report["benchmarks"]:
        lines.append(
            f"| {item['dataset']} | {item['rows']} | {item['p50_ms']} ms | "
            f"{item['max_ms']} ms |"
        )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.repeats < 1:
        parser.error("--repeats must be positive")
    report = run(args.base_url, args.repeats)
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "acceptance.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    )
    (args.output / "acceptance.md").write_text(markdown(report))
    print(json.dumps({
        "accepted": report["accepted"],
        "output": str(args.output),
    }, ensure_ascii=False))
    return 0 if report["accepted"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
