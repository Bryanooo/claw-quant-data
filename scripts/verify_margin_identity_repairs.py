"""Reconcile committed business rows to the frozen provider observations, read-only."""

import argparse
from collections import Counter
from decimal import Decimal
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from psycopg2.extras import RealDictCursor
from service.db import get_conn
from service.margin_quality import BALANCE_FIELDS, balance_issues, valid_balance_sql
from scripts.probe_margin_identities import lookup


def require(condition, key):
    if not condition:
        raise ValueError(f"failed independent reconciliation: {key}")


def amounts(row):
    return [None if row[k] is None else Decimal(str(row[k])) for k in BALANCE_FIELDS]


def run(folder, stamp):
    def path(name, ext="json"):
        return folder / f"margin-{name}-{stamp}.{ext}"

    def key(row):
        return row["ts_code"], row["trade_date"]

    frozen = json.loads(path("balance-before").read_text())["datasets"][
        "margin_detail"
    ]["invalid_identities"]
    original = {key(x): x for x in frozen}
    ts, em, ex, so = [
        lookup(path(label, "jsonl"))
        for label in ("probe-ts", "probe-em", "probe-exchange", "sohu-confirmed")
    ]
    outcomes = json.loads(path("repair-results").read_text())
    results = {key(x): x for x in outcomes["records"]}
    require(
        outcomes["applied"]
        and len(original) == len(frozen) == len(outcomes["records"])
        and results.keys() == ts.keys() == em.keys() == original.keys(),
        "identity inventory",
    )
    residual = []
    with get_conn() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        cur.execute(
            "SELECT ts_code,trade_date FROM margin_detail WHERE NOT ("
            + valid_balance_sql()
            + ")"
        )
        bad = {key(r) for r in cur.fetchall()}
        require(
            bad
            == ex.keys()
            == so.keys()
            == {k for k, v in results.items() if v["status"] == "unresolved"},
            "residual set",
        )
        for k, initial in original.items():
            decision = results[k]
            cur.execute(
                "SELECT * FROM margin_detail WHERE ts_code=%s AND trade_date=%s", k
            )
            live = cur.fetchone()
            cur.execute(
                "SELECT * FROM margin_detail_repair_evidence WHERE ts_code=%s AND trade_date=%s",
                k,
            )
            saved = cur.fetchone()
            cur.execute(
                """SELECT request_params,response_hash FROM tushare_raw_request
                WHERE request_id=%s AND api_name='margin_detail' AND status='success'""",
                (ts[k]["proof"],),
            )
            request = cur.fetchone()
            require(
                request
                and request["response_hash"]
                and request["request_params"] == ts[k]["parameters"],
                k,
            )
            if k in bad:
                require(
                    live
                    and not saved
                    and amounts(initial) == amounts(live)
                    and not em[k]["values"],
                    k,
                )
                exchange = ex[k]
                require(exchange["market_published"] and exchange["exact"], k)
                reason = {
                    "not_in_published_detail": "同日交易所已发布市场数据，但该证券不在公开明细中；没有可核验的余额。",
                    "published_detail": "交易所有该证券明细，但未提供融券余额金额及两融合计；股数不能替代金额。",
                }[exchange["status"]]
                residual.append(
                    dict(
                        ts_code=k[0],
                        trade_date=k[1],
                        reason=reason,
                        missing_or_invalid=balance_issues(live),
                        tushare=ts[k],
                        eastmoney=em[k],
                        exchange=exchange,
                        sohu=so[k],
                    )
                )
            else:
                require(
                    saved
                    and saved["source"] == decision["source"]
                    and saved["provider_evidence"]
                    == dict(tushare=ts[k], eastmoney=em[k])
                    and key(saved["before_row"]) == k
                    and amounts(saved["before_row"]) == amounts(initial),
                    k,
                )
                if decision["status"] == "quarantined":
                    require(live is None and saved["source"] == "quarantine_header", k)
                else:
                    require(
                        decision["status"] == "repaired"
                        and live
                        and not balance_issues(live)
                        and amounts(live)
                        == amounts(em[k]["values"])
                        == amounts(saved["replacement"])
                        and all(
                            str(live[f]) == str(saved["before_row"][f])
                            or (
                                live[f] is not None
                                and saved["before_row"][f] is not None
                                and Decimal(str(live[f]))
                                == Decimal(str(saved["before_row"][f]))
                            )
                            for f in ("rqyl", "rzmre", "rzche", "rqmcl", "rqchl")
                        ),
                        k,
                    )
    res = dict(
        checked=len(results),
        counts=dict(Counter(x["status"] for x in results.values())),
        unexplained_identity_changes=0,
        residual_dates=len({x["trade_date"] for x in residual}),
        residual=residual,
    )
    path("final-verification").write_text(
        json.dumps(res, ensure_ascii=False, indent=2) + "\n"
    )
    print({k: v for k, v in res.items() if k != "residual"})


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("folder", type=Path)
    p.add_argument("stamp")
    args = p.parse_args()
    run(args.folder, args.stamp)
