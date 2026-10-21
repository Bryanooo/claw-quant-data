"""Capture independent dividend/split evidence without silently approving it.

Run with --output DIRECTORY. Compare events.json with fund_div and issuer notices
before extending config/etf_rotation_events.json reviewed coverage.
"""
import argparse
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import re

import requests


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    config = json.loads((Path(__file__).resolve().parents[1] /
                         "config/etf_rotation_events.json").read_text())
    result = []
    for reviewed in config["cash_crosscheck"]["symbols"]:
        symbol = reviewed["symbol"]
        url = f"https://fundf10.eastmoney.com/fhsp_{symbol[:6]}.html"
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        response.encoding = "utf-8"
        text = response.text
        if symbol[:6] not in text or "每10份分红" not in text:
            raise ValueError("Dividend source identity/schema changed")
        (args.output / f"{symbol}.html").write_bytes(response.content)
        cash, splits = [], []
        for table in re.findall(r"<table[\s\S]*?</table>", text):
            for tr in re.findall(r"<tr>([\s\S]*?)</tr>", table):
                cells = [re.sub("<[^>]+>", "", c).strip()
                         for c in re.findall(r"<td[^>]*>([\s\S]*?)</td>", tr)]
                if "每10份分红" in table and len(cells) == 5:
                    amount = re.search(r"现金([\d.]+)", cells[3])
                    if amount is None:
                        raise ValueError("Unrecognized cash distribution")
                    cash.append({"record_date": cells[1], "ex_date": cells[2],
                                 "div_cash": float(Decimal(amount[1]) / 10),
                                 "pay_date": cells[4]})
                elif "拆分折算比例" in table and len(cells) == 4:
                    splits.append(cells)
        no_cash = "暂无分红信息" in text
        if not cash and not no_cash:
            raise ValueError("Empty source is not proof of no dividends")
        result.append({
            "symbol": symbol, "source_url": url,
            "sha256": hashlib.sha256(response.content).hexdigest(),
            "collected_at": datetime.now(timezone.utc).isoformat(),
            "cash": cash, "splits": splits, "no_cash_explicit": no_cash,
        })
        print(symbol, len(cash), len(splits), flush=True)
    (args.output / "events.json").write_text(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
