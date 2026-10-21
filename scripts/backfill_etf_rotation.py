"""Bounded, resumable ETF acquisition using the existing governed collectors.

Run inside the claw-data application environment. No credentials are serialized.
Evidence records are written after each completed scope; a failed scope is retried
on the next invocation. This does not publish whole-market readiness.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

SYMBOLS = (
    "510050.SH", "510300.SH", "510500.SH", "512100.SH", "159915.SZ",
    "588000.SH", "159928.SZ", "512010.SH", "512480.SH", "512880.SH",
    "512690.SH", "515000.SH",
)


def scopes(start, end):
    for symbol in SYMBOLS:
        yield "fund_div", {"ts_code": symbol}
        for year in range(start.year, end.year + 1):
            left, right = max(start, date(year, 1, 1)), min(end, date(year, 12, 31))
            params = dict(ts_code=symbol, start_date=left.strftime("%Y%m%d"),
                          end_date=right.strftime("%Y%m%d"))
            for dataset in ("fund_daily", "fund_adj", "stk_limit", "suspend_d"):
                yield dataset, params


def collect_scope(dataset, params):
    from collectors.tushare_raw import CatalogRawCollector
    from collectors.stock.market.stk_limit import STKLimitCollector
    from collectors.stock.market.suspend_d import SuspendDCollector

    if dataset in ("fund_daily", "fund_adj"):
        collector = CatalogRawCollector(dataset)
        rows = collector.collect_complete(**params)
        return {"rows_stored": rows, **collector.completion_evidence}
    collector = (
        CatalogRawCollector(dataset) if dataset == "fund_div" else
        STKLimitCollector() if dataset == "stk_limit" else SuspendDCollector()
    )
    frame = collector.fetch(**params)
    # A single fund's complete distributions are naturally bounded. Annual
    # daily scopes are below one provider page. Fail on a possible capped result.
    if len(frame) >= 1000:
        raise ValueError("Potentially truncated response")
    if not frame.empty:
        if set(frame.ts_code) != {params["ts_code"]}:
            raise ValueError("Provider returned an unrequested security")
        if "start_date" in params:
            days = frame.trade_date.astype(str).str.replace("-", "", regex=False)
            if not days.between(params["start_date"], params["end_date"]).all():
                raise ValueError("Provider returned dates outside requested scope")
    rows = collector.store(frame) if not frame.empty else 0
    return {"rows_stored": rows, "rows_fetched": len(frame),
            "verification_type": "single_security_bounded_response",
            "empty_response": frame.empty,
            "note": "An empty event response is not proof of ETF suspension coverage."}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", type=date.fromisoformat, default=date(2019, 1, 1))
    parser.add_argument("--end", type=date.fromisoformat, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if args.end < args.start:
        parser.error("end precedes start")
    jobs = list(scopes(args.start, args.end))
    if not args.apply:
        print(json.dumps({"symbols": SYMBOLS, "scopes": len(jobs)}))
        return
    args.evidence.parent.mkdir(parents=True, exist_ok=True)
    previous = [json.loads(line) for line in args.evidence.read_text().splitlines()] if args.evidence.exists() else []
    key = lambda d, p: json.dumps([d, p], sort_keys=True)
    done = {key(r["dataset"], r["parameters"]) for r in previous if r["status"] == "success"}
    failures = 0
    for dataset, params in jobs:
        if key(dataset, params) in done:
            continue
        record = {"dataset": dataset, "parameters": params,
                  "collected_at": datetime.now(timezone.utc).isoformat()}
        try:
            record.update(status="success", evidence=collect_scope(dataset, params))
        except Exception as exc:
            # Do not serialize arbitrary provider error strings (may contain URLs).
            record.update(status="failed", error_type=type(exc).__name__)
            failures += 1
        with args.evidence.open("a") as handle:
            handle.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
        print(json.dumps(record, ensure_ascii=False, default=str), flush=True)
    if failures:
        raise SystemExit(f"{failures} scopes failed; inspect acquisition evidence")


if __name__ == "__main__":
    main()
