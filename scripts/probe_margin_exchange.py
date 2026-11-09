"""Check residual exact identities against public exchange detail and a positive date control."""

import argparse
from datetime import date
import hashlib
import json
from pathlib import Path
import time

import requests


def probe(code, day, session):
    def get(url, params, referer):
        r = session.get(
            url, params=params, headers={"Referer": referer}, timeout=(4, 15)
        )
        r.raise_for_status()
        return r.json(), hashlib.sha256(r.content).hexdigest()

    if code.endswith(".SH"):
        url = "https://query.sse.com.cn/commonSoaQuery.do"
        ref = "https://www.sse.com.cn/market/othersdata/margin/sum/"
        params = {
            "beginDate": day,
            "endDate": day,
            "isPagination": "true",
            "pageHelp.pageSize": 25,
            "pageHelp.pageNo": 1,
            "pageHelp.beginPage": 1,
            "pageHelp.endPage": 1,
            "pageHelp.cacheSize": 1,
        }
        q = dict(params, preStockCode=code[:6], sqlId="RZRQ_MX_INFO")
        data, digest = get(url, q, ref)
        supply, control_digest = get(
            url, dict(params, stockCode="", sqlId="RZRQ_HZ_INFO"), ref
        )
        positive = any(str(r.get("opDate")) == day for r in supply.get("result", []))
        rows = data["result"]
        exact = data["pageHelp"]["total"] == len(rows) and all(
            str(r["opDate"]) == day and r["stockCode"] == code[:6] for r in rows
        )
    elif code.endswith(".SZ"):
        url = "https://www.szse.cn/api/report/ShowReport/data"
        ref = "https://www.szse.cn/market/trend/rzrq/index.html"
        params = {
            "SHOWTYPE": "JSON",
            "CATALOGID": "1837_xxpl",
            "TABKEY": "tab2",
            "txtDate": date.fromisoformat(day).isoformat(),
        }
        q = dict(params, txtZqdm=code[:6])
        data, digest = get(url, q, ref)
        supply, control_digest = get(url, params, ref)
        positive = bool(supply[0]["data"] and supply[0]["metadata"]["recordcount"] > 0)
        rows = data[0]["data"]
        echo = {
            x["name"]: x.get("defaultValue") for x in data[0]["metadata"]["conditions"]
        }
        exact = (
            echo.get("txtDate") == params["txtDate"]
            and echo.get("txtZqdm") == code[:6]
            and len(rows) == data[0]["metadata"]["recordcount"]
            and all(r["zqdm"] == code[:6] for r in rows)
        )
    else:
        raise ValueError("unsupported exchange")
    return dict(
        ts_code=code,
        trade_date=day,
        url=url,
        parameters=q,
        response_hash=digest,
        control_hash=control_digest,
        market_published=positive,
        exact=exact,
        rows=rows,
        status=(
            "unverified_response"
            if not (positive and exact)
            else "published_detail"
            if rows
            else "not_in_published_detail"
        ),
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("scope", type=Path)
    p.add_argument("output", type=Path)
    a = p.parse_args()
    done = (
        {
            (x["ts_code"], x["trade_date"])
            for x in (json.loads(l) for l in a.output.read_text().splitlines())
        }
        if a.output.exists()
        else set()
    )
    with requests.Session() as s, a.output.open("a", buffering=1) as f:
        for row in json.loads(a.scope.read_text()):
            key = row["ts_code"], row["trade_date"]
            if key not in done:
                f.write(json.dumps(probe(*key, s), ensure_ascii=False) + "\n")
                time.sleep(0.15)
