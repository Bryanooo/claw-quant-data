"""Bounded/resumable provider probes. Never writes business data."""

import argparse
from collections import defaultdict
from datetime import date, datetime, timezone
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import re
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pandas as pd
import requests

from collectors.stock.margin.margin import MarginDetailCollector
from service.margin_quality import balance_issues

EM_URL = "https://datacenter-web.eastmoney.com/api/data/v1/get"
FIELDS = ("rzye", "rqyl", "rqye", "rzrqye", "rzmre", "rzche", "rqmcl", "rqchl")


def windows(items):
    by_code = defaultdict(set)
    for r in items:
        by_code[r["ts_code"]].add(r["trade_date"])
    for code, days in sorted(by_code.items()):
        batch = []
        for day in sorted(days):
            if (
                batch
                and (date.fromisoformat(day) - date.fromisoformat(batch[0])).days > 365
            ):
                yield code, batch
                batch = []
            batch.append(day)
        if batch:
            yield code, batch


def clean(row):
    return {k: None if pd.isna(row.get(k)) else str(row[k]) for k in FIELDS}


def lookup(path):
    if not path.exists():
        return {}
    result = {}
    for line in path.read_text().splitlines():
        row = json.loads(line)
        key = row["ts_code"], row["trade_date"]
        if key in result:
            raise ValueError(f"duplicate evidence for {key}")
        result[key] = row
    return result


def run(args):
    items = json.loads(args.scope.read_text())["datasets"]["margin_detail"][
        "invalid_identities"
    ]
    if args.primary:
        primary = lookup(args.primary)
        # Also check other sources for valid primary values which disagree with
        # the frozen original; conflicts must not silently overwrite history.
        items = [r for r in items if (r["ts_code"], r["trade_date"]) in primary]
    done = lookup(args.output)
    client = MarginDetailCollector() if args.source == "tushare" else None
    session = requests.Session()
    batches = list(
        windows([r for r in items if (r["ts_code"], r["trade_date"]) not in done])
    )
    with args.output.open("a", buffering=1) as out:
        for i, (code, days) in enumerate(batches):
            from service.orchestration_v2.worker import historical_resume_at

            if historical_resume_at("repair") is not None:
                raise SystemExit(
                    "historical collection window closed; resume off hours"
                )
            if not re.fullmatch(r"[0-9]{6}\.(SH|SZ|BJ)", code):
                for day in days:
                    out.write(
                        json.dumps(
                            dict(
                                ts_code=code,
                                trade_date=day,
                                source=args.source,
                                checked_at=datetime.now(timezone.utc).isoformat(),
                                parameters={},
                                proof=None,
                                values=None,
                                issues=["malformed_security_identifier"],
                            )
                        )
                        + "\n"
                    )
                continue
            if client:
                params = dict(
                    ts_code=code, start_date=days[0], end_date=days[-1], limit=1000
                )
                frame = client.fetch(**params)
                rows = frame.to_dict("records")
                if len(rows) >= 1000:
                    raise ValueError("suspected truncation")
                proof = client._raw_archive_requests[-1]["request_id"]
            else:
                lo, hi = (
                    date.fromisoformat(d).isoformat() for d in (days[0], days[-1])
                )
                params = {
                    "reportName": "RPTA_WEB_RZRQ_GGMX",
                    "columns": "DATE,SECUCODE," + ",".join(k.upper() for k in FIELDS),
                    "filter": f"""(SECUCODE="{code}")(DATE>='{lo}')(DATE<='{hi}')""",
                    "pageSize": 500,
                    "pageNumber": 1,
                }
                response = session.get(EM_URL, params=params, timeout=(5, 20))
                response.raise_for_status()
                body = response.json(parse_float=Decimal)
                data = body.get("result")
                if not body.get("success") and body.get("code") != 9201:
                    raise ValueError(f"provider rejected request: {body.get('code')}")
                if not data and not (
                    body.get("code") == 9201
                    and body.get("message") in {"无数据", "返回数据为空"}
                ):
                    raise ValueError("unrecognized empty response")
                raw = (data or {}).get("data", [])
                if data and (data["count"] != len(raw) or data["pages"] > 1):
                    raise ValueError("incomplete alternative response")
                rows = [
                    dict(
                        ts_code=r["SECUCODE"],
                        trade_date=r["DATE"][:10].replace("-", ""),
                        **{k: r[k.upper()] for k in FIELDS},
                    )
                    for r in raw
                ]
                proof = hashlib.sha256(response.content).hexdigest()
                time.sleep(0.1)
            indexed = {}
            for row in rows:
                d = str(row["trade_date"])
                if (
                    row["ts_code"] != code
                    or not days[0] <= d <= days[-1]
                    or d in indexed
                ):
                    raise ValueError(f"response identity mismatch {code} {d}")
                indexed[d] = clean(row)
            for day in days:
                values = indexed.get(day)
                out.write(
                    json.dumps(
                        dict(
                            ts_code=code,
                            trade_date=day,
                            source=args.source,
                            checked_at=datetime.now(timezone.utc).isoformat(),
                            parameters=params,
                            proof=proof,
                            values=values,
                            issues=balance_issues(values) if values else ["no_row"],
                        ),
                        ensure_ascii=False,
                    )
                    + "\n"
                )
            if i % 50 == 0:
                print(args.source, i + 1, "/", len(batches), code, flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", choices=["tushare", "eastmoney"])
    parser.add_argument("scope", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--primary", type=Path)
    run(parser.parse_args())
