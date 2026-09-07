#!/usr/bin/env python3
"""One-request, no-write smoke test for discovered Tushare collectors."""

from __future__ import annotations

import argparse
from datetime import date, timedelta
import importlib
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from collectors.stock.finance.base import BaseFinanceCollector
from service.collector_catalog import discover_collectors
from service.db import query


STOCK_CODE = "000001.SZ"
INDEX_CODE = "000001.SH"

STOCK_CODE_APIS = {
    "dividend", "pledge_detail", "pledge_stat", "stk_holdernumber",
    "stk_managers", "stk_rewards", "top10_floatholders", "top10_holders",
}
TRADE_DATE_APIS = {
    "bak_basic", "block_trade", "ccass_hold", "ccass_hold_detail", "daily",
    "dc_daily", "ggt_top10", "hsgt_top10", "limit_cpt_list",
    "limit_list_d", "limit_step", "moneyflow", "moneyflow_dc",
    "moneyflow_hsgt", "stk_ah_comparison", "stk_auction",
    "stk_auction_c", "stk_auction_o", "stk_factor_pro", "stk_limit",
    "stk_nineturn", "suspend_d", "tdx_daily", "ths_daily", "top_inst",
    "top_list",
}


def latest_trade_date() -> str:
    try:
        rows = query(
            "SELECT max(cal_date) AS trade_date FROM trade_cal "
            "WHERE is_open = 1 AND cal_date <= CURRENT_DATE"
        )
        if rows and rows[0]["trade_date"]:
            return rows[0]["trade_date"].strftime("%Y%m%d")
    except Exception:
        pass
    return (date.today() - timedelta(days=1)).strftime("%Y%m%d")


def parameters_for(contract, trade_date: str) -> dict:
    api_name = contract.api_name
    if api_name == "broker_recommend":
        return {"month": trade_date[:6]}
    if api_name in {"cyq_chips", "cyq_perf"}:
        return {"ts_code": STOCK_CODE, "trade_date": trade_date}
    if api_name == "stk_weekly_monthly":
        return {"trade_date": trade_date, "freq": "week"}
    if contract.table_name == "ggt_monthly":
        month = trade_date[:6]
        return {"start_month": month, "end_month": month}
    if api_name == "stock_hsgt":
        return {"trade_date": trade_date, "type": "HK_SH"}
    if api_name == "fx_obasic":
        return {"exchange": "FXCM", "classify": "FX"}
    if api_name == "fx_daily":
        return {
            "ts_code": "EURUSD.FXCM",
            "start_date": trade_date,
            "end_date": trade_date,
        }
    if api_name == "sge_daily":
        return {
            "ts_code": "Au99.99.SGE",
            "start_date": trade_date,
            "end_date": trade_date,
        }
    if api_name.startswith("index_") and api_name != "index_basic":
        return {
            "ts_code": INDEX_CODE,
            "start_date": trade_date,
            "end_date": trade_date,
        }
    if api_name in STOCK_CODE_APIS:
        return {"ts_code": STOCK_CODE}
    if api_name in TRADE_DATE_APIS:
        return {"trade_date": trade_date}
    return {}


def run_probe(contract, trade_date: str) -> int:
    module_name, class_name = contract.qualified_name.rsplit(".", 1)
    collector_class = getattr(importlib.import_module(module_name), class_name)
    collector = collector_class()

    if contract.api_name == "stock_st":
        frame = collector.fetch_stock_st(trade_date)
    elif issubclass(collector_class, BaseFinanceCollector):
        frame = collector.fetch_period(f"{int(trade_date[:4]) - 1}1231")
    else:
        frame = collector.fetch(**parameters_for(contract, trade_date))
    if frame is None:
        return 0
    return len(collector.transform(frame))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("filter", nargs="?", help="substring of class, API, or table")
    parser.add_argument("--delay", type=float, default=0.2)
    parser.add_argument("--limit", type=int)
    parser.add_argument(
        "--require-data",
        action="store_true",
        help="treat an empty but successful response as a failed acceptance check",
    )
    args = parser.parse_args()

    contracts = tuple(
        item
        for item in discover_collectors()
        if item.qualified_name != "collectors.tushare_raw.CatalogRawCollector"
    )
    if args.filter:
        needle = args.filter.lower()
        contracts = tuple(
            item for item in contracts
            if needle in f"{item.qualified_name} {item.api_name} {item.table_name}".lower()
        )
    if args.limit is not None:
        contracts = contracts[: args.limit]
    if not contracts:
        parser.error("no collectors matched")

    trade_date = latest_trade_date()
    failures = []
    for contract in contracts:
        try:
            rows = run_probe(contract, trade_date)
            if args.require_data and rows == 0:
                failures.append(contract.qualified_name)
                print(f"FAIL {contract.table_name:28} empty response")
            else:
                print(f"PASS {contract.table_name:28} rows={rows}")
        except Exception as exc:
            failures.append(contract.qualified_name)
            print(f"FAIL {contract.table_name:28} {type(exc).__name__}: {exc}")
        time.sleep(max(args.delay, 0))

    print(
        f"checked={len(contracts)} "
        f"passed={len(contracts) - len(failures)} failed={len(failures)}"
    )
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
