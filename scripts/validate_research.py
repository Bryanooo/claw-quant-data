#!/usr/bin/env python3
"""Execute the representative research acceptance set over HTTP."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from service.research.validation import (
    RESEARCH_VALIDATION_CASES,
    validate_research_response,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--timeout", type=float, default=120.0)
    args = parser.parse_args()

    results = []
    for case in RESEARCH_VALIDATION_CASES:
        url = args.base_url.rstrip("/") + case["path"]
        status = 0
        payload = None
        transport_error = None
        try:
            with urlopen(Request(url, headers={"Accept": "application/json"}), timeout=args.timeout) as response:
                status = response.status
                payload = json.load(response)
        except HTTPError as exc:
            status = exc.code
            try:
                payload = json.load(exc)
            except Exception:
                payload = None
        except (URLError, TimeoutError) as exc:
            transport_error = str(exc)
        errors = (
            [f"transport error: {transport_error}"]
            if transport_error
            else validate_research_response(case, status, payload)
        )
        results.append({
            "id": case["id"],
            "subject": case["subject"],
            "path": case["path"],
            "status_code": status,
            "status": "passed" if not errors else "failed",
            "errors": errors,
        })

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "base_url": args.base_url,
        "summary": {
            "cases": len(results),
            "passed": sum(item["status"] == "passed" for item in results),
            "failed": sum(item["status"] == "failed" for item in results),
        },
        "results": results,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    return 1 if report["summary"]["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
