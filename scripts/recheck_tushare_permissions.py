#!/usr/bin/env python3
"""Recheck every denied Tushare contract without rebuilding the catalog."""

from __future__ import annotations

import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import time
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONTRACTS_PATH = PROJECT_ROOT / "docs" / "tushare" / "contracts.json"
API_URL = "http://api.tushare.pro"
SHANGHAI = ZoneInfo("Asia/Shanghai")


def load_token() -> str:
    value = os.getenv("TUSHARE_TOKEN", "").strip()
    if value:
        return value
    for line in (PROJECT_ROOT / ".env").read_text(encoding="utf-8").splitlines():
        if line.startswith("TUSHARE_TOKEN="):
            value = line.split("=", 1)[1].strip()
            if value:
                return value
    raise RuntimeError("TUSHARE_TOKEN is not configured")


def call(token: str, contract: dict[str, Any]) -> dict[str, Any]:
    fields = ",".join(
        item["name"] for item in contract.get("output_parameters", [])[:1]
        if item.get("name")
    )
    body = json.dumps({
        "api_name": contract["api_name"],
        "token": token,
        "params": contract.get("example_parameters") or {},
        "fields": fields,
    }).encode()
    request = Request(
        API_URL,
        data=body,
        headers={
            "Content-Type": "application/json",
            "User-Agent": "claw-quant-data-permission-recheck/1.0",
        },
    )
    try:
        with urlopen(request, timeout=45) as response:
            return json.loads(response.read().decode())
    except (URLError, TimeoutError, json.JSONDecodeError) as exc:
        return {"code": "transport_error", "msg": str(exc)}


def classify(response: dict[str, Any]) -> str:
    code = response.get("code")
    message = str(response.get("msg") or "")
    if code == 40203 and ("没有接口" in message or "访问权限" in message):
        return "denied"
    if code == 0 or code == 50101 or "参数校验失败" in message:
        return "accessible"
    if "频率超限" in message or "访问频率" in message:
        return "accessible_rate_limited"
    if code == 40101 or "正确的接口名" in message:
        return "invalid"
    return "inconclusive"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempts", type=int, choices=range(1, 4), default=2)
    parser.add_argument("--delay", type=float, default=0.2)
    parser.add_argument("--output-dir", type=Path, default=PROJECT_ROOT / "reports")
    args = parser.parse_args()

    payload = json.loads(CONTRACTS_PATH.read_text(encoding="utf-8"))
    contracts = [
        item for item in payload["interfaces"]
        if item["permission"]["status"] == "无权限"
    ]
    token = load_token()
    results = []
    for index, contract in enumerate(contracts, start=1):
        probes = []
        for attempt in range(args.attempts):
            response = call(token, contract)
            probes.append({
                "attempt": attempt + 1,
                "classification": classify(response),
                "code": response.get("code"),
                "message": str(response.get("msg") or ""),
            })
            if attempt + 1 < args.attempts:
                time.sleep(args.delay)
        classifications = {probe["classification"] for probe in probes}
        results.append({
            "api_name": contract["api_name"],
            "official_url": contract["official_urls"][0],
            "documented_permission": contract["permission"]["status"],
            "confirmed": classifications == {"denied"},
            "probes": probes,
        })
        print(f"[{index}/{len(contracts)}] {contract['api_name']}: "
              f"{','.join(sorted(classifications))}", flush=True)

    generated_at = datetime.now(SHANGHAI).isoformat()
    confirmed = sum(bool(item["confirmed"]) for item in results)
    report = {
        "generated_at": generated_at,
        "probe_attempts": args.attempts,
        "total": len(results),
        "confirmed_denied": confirmed,
        "changed_or_inconclusive": len(results) - confirmed,
        "interfaces": results,
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    json_path = args.output_dir / "tushare_permission_recheck.json"
    md_path = args.output_dir / "tushare_permission_recheck.md"
    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    lines = [
        "# Tushare 无权限接口复核",
        "",
        f"- 复核时间：`{generated_at}`",
        "- Token：从运行环境读取，报告不保存 Token 或其派生值",
        f"- 双重探测：每个接口 `{args.attempts}` 次",
        f"- 契约标记无权限：`{len(results)}`",
        f"- 仍明确返回无权限：`{confirmed}`",
        f"- 权限变化或无法确认：`{len(results) - confirmed}`",
        "",
        "| 接口 | 结论 | 返回码 | 官方文档 |",
        "|---|---|---|---|",
    ]
    for item in results:
        codes = ", ".join(str(probe["code"]) for probe in item["probes"])
        conclusion = "确认无权限" if item["confirmed"] else "需人工复核"
        lines.append(
            f"| `{item['api_name']}` | {conclusion} | `{codes}` | "
            f"[文档]({item['official_url']}) |"
        )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"report: {md_path}")
    return 0 if confirmed == len(results) else 2


if __name__ == "__main__":
    raise SystemExit(main())
