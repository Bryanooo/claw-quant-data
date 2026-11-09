"""Repair only frozen invalid identities using exact provider observations. Dry run by default."""

import argparse
from collections import Counter
from decimal import Decimal
import json
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from psycopg2.extras import Json, RealDictCursor
from service.db import get_conn
from service.margin_quality import BALANCE_FIELDS, balance_issues
from scripts.probe_margin_identities import FIELDS, lookup


def number(value):
    return None if value is None else Decimal(str(value))


def choose(old, primary, secondary):
    code, day = old["ts_code"], old["trade_date"]
    if not re.fullmatch(r"[0-9]{6}\.(SH|SZ|BJ)", code):
        if code == f"日期：{day[:4]}-{day[4:6]}-{day[6:]}.BJ" and all(
            old[k] is None for k in FIELDS
        ):
            return "quarantine_header", {}, []
        return None, {}, ["unrecognized_identifier"]
    errors = []
    for source, probe in (("tushare", primary), ("eastmoney", secondary)):
        if (probe["source"], probe["ts_code"], probe["trade_date"]) != (
            source,
            code,
            day,
        ) or not probe["proof"]:
            raise ValueError("unverified source identity")
        row = probe["values"]
        if row is None or balance_issues(row):
            errors.append(
                source + ":" + (",".join(balance_issues(row)) if row else "no_row")
            )
            continue
        qty = number(row["rqyl"])
        if (
            qty is None
            or not qty.is_finite()
            or qty < 0
            or (qty > 0 and number(row["rqye"]) == 0)
        ):
            errors.append(source + ":short_amount_quantity_conflict")
            continue
        if source == "eastmoney":
            # These are corroborating fields, not the broken short/total amounts.
            # Require at least one observed anchor; never match solely on name.
            anchors = [
                (k, number(record[k]))
                for record in (old, primary.get("values") or {})
                for k in ("rzye", "rqyl")
                if record.get(k) is not None
            ]
            if not anchors or any(number(row[k]) != v for k, v in anchors):
                errors.append(source + ":uncorroborated_or_conflicting_anchor")
                continue
        elif old["rqyl"] is not None and number(old["rqyl"]) != qty:
            errors.append(source + ":changed_short_quantity")
            continue
        return source, {k: str(row[k]) for k in BALANCE_FIELDS}, errors
    return None, {}, errors


def repair(scope, primary_file, secondary_file, output, apply):
    primary, secondary = lookup(primary_file), lookup(secondary_file)
    items = json.loads(scope.read_text())["datasets"]["margin_detail"][
        "invalid_identities"
    ]
    keys = {(r["ts_code"], r["trade_date"]) for r in items}
    if len(keys) != len(items) or set(primary) != keys or set(secondary) != keys:
        raise ValueError("incomplete or incorrect probe inventory")
    decisions = []
    with get_conn() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SET LOCAL lock_timeout='3s'")
        if not apply:
            cur.execute("SET TRANSACTION READ ONLY")
        for item in items:
            code, day = item["ts_code"], item["trade_date"]
            key = code, day
            cur.execute(
                "SELECT * FROM margin_detail WHERE ts_code=%s AND trade_date=%s"
                + (" FOR UPDATE" if apply else ""),
                key,
            )
            old = cur.fetchone()
            if old is None or not balance_issues(old):
                decisions.append(
                    dict(
                        ts_code=code,
                        trade_date=day,
                        status="already_valid" if old else "absent",
                    )
                )
                continue
            if any(number(old[k]) != number(item[k]) for k in BALANCE_FIELDS):
                raise ValueError(f"unexpected concurrent change: {key}")
            src, values, why = choose(old, primary[key], secondary[key])
            proof = dict(tushare=primary[key], eastmoney=secondary[key])
            decision = dict(
                ts_code=code,
                trade_date=day,
                source=src,
                reasons=why,
                before={
                    k: None if old[k] is None else str(old[k]) for k in BALANCE_FIELDS
                },
                after=values,
                primary_request=primary[key]["proof"],
                secondary_hash=secondary[key]["proof"],
            )
            if src and apply:
                cur.execute(
                    """INSERT INTO margin_detail_repair_evidence
                    (ts_code,trade_date,source,before_row,replacement,provider_evidence)
                    SELECT ts_code,trade_date,%s,to_jsonb(d),%s,%s FROM margin_detail d
                    WHERE ts_code=%s AND trade_date=%s""",
                    (src, Json(values), Json(proof), code, day),
                )
                if src == "quarantine_header":
                    cur.execute(
                        "DELETE FROM margin_detail WHERE ts_code=%s AND trade_date=%s",
                        key,
                    )
                else:
                    cur.execute(
                        """UPDATE margin_detail SET rzye=%s,rqye=%s,rzrqye=%s
                        WHERE ts_code=%s AND trade_date=%s RETURNING rzye,rqye,rzrqye""",
                        (*[values[k] for k in BALANCE_FIELDS], code, day),
                    )
                    if balance_issues(cur.fetchone()):
                        raise ValueError(f"failed post-write invariant: {key}")
                if cur.rowcount != 1:
                    raise ValueError("lost row lock")
            decision["status"] = (
                "unresolved"
                if not src
                else "would_apply"
                if not apply
                else "quarantined"
                if src == "quarantine_header"
                else "repaired"
            )
            decisions.append(decision)
    result = dict(
        applied=apply,
        counts=dict(Counter(x["status"] for x in decisions)),
        records=decisions,
    )
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(result["counts"])


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    for key in ("scope", "primary", "secondary", "output"):
        p.add_argument(key, type=Path)
    p.add_argument("--apply", action="store_true")
    a = p.parse_args()
    repair(a.scope, a.primary, a.secondary, a.output, a.apply)
