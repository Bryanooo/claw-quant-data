"""Bounded public quote-page fallback for exact residual securities/dates."""

from datetime import date
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import time
from bs4 import BeautifulSoup


def probe(code, day):
    if not re.fullmatch(r"[0-9]{6}\.(SH|SZ)", code):
        raise ValueError("bad exchange/code")
    iso = date.fromisoformat(day).isoformat()
    url = (
        f"https://q.stock.sohu.com/app2/mpssTrade.up?code={code[:6]}&sd={iso}&ed={iso}"
    )
    response = subprocess.run(
        [
            "curl",
            "--fail",
            "--silent",
            "--show-error",
            "--max-time",
            "8",
            "--max-filesize",
            "1000000",
            url,
        ],
        capture_output=True,
    )
    out = dict(ts_code=code, trade_date=day, url=url, values=None)
    if response.returncode:
        return dict(out, status=f"transport_error_{response.returncode}")
    html = BeautifulSoup(response.stdout.decode("gb18030", "replace"), "html.parser")
    proof = hashlib.sha256(response.stdout).hexdigest()
    echoed = {n.get("name"): n.get("value") for n in html.select("input[name]")}
    if any(
        echoed.get(k) != v for k, v in {"code": code[:6], "sd": iso, "ed": iso}.items()
    ):
        return dict(out, proof=proof, status="unverified_filter")
    if html.find(
        string=lambda s: s is not None and s.strip() == "无符合查询条件的结果"
    ):
        return dict(out, proof=proof, status="explicit_no_result")
    for table in html.select("table"):
        headings = [node.get_text(strip=True) for node in table.select("thead th")]
        if headings != [
            "交易日期",
            "标的证券代码",
            "标的证券名称",
            "融资",
            "融券",
            "融资融券余额(元)",
            "融资买入额(元)",
            "融资偿还额(元)",
            "融资余额(元)",
            "融券卖出量(股)",
            "融券偿还量(股)",
            "融券余量(股)",
            "融券余额(元)",
        ]:
            continue
        rows = [
            [n.get_text(strip=True) for n in tr.select("td")]
            for tr in table.select("tbody tr")
        ]
        matches = [r for r in rows if len(r) == 11 and r[:2] == [iso, code[:6]]]
        vals = (
            None
            if len(matches) != 1
            else dict(
                zip(
                    (
                        "rzmre",
                        "rzche",
                        "rzye",
                        "rqmcl",
                        "rqchl",
                        "rqyl",
                        "rqye",
                        "rzrqye",
                    ),
                    [
                        v.replace(",", "") if re.fullmatch(r"[-\d,.]+", v) else None
                        for v in matches[0][3:]
                    ],
                    strict=True,
                )
            )
        )
        return dict(
            out,
            proof=proof,
            values=vals,
            status="published_detail" if vals else "no_exact_row",
        )
    return dict(out, proof=proof, status="unverified_schema")


if __name__ == "__main__":
    scope, out = map(Path, sys.argv[1:])
    with out.open("x", buffering=1) as f:
        for row in json.loads(scope.read_text()):
            f.write(
                json.dumps(probe(row["ts_code"], row["trade_date"]), ensure_ascii=False)
                + "\n"
            )
            time.sleep(0.1)
