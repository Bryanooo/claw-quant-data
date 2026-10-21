"""Reviewed ETF source evidence, separate from vendor observations."""
import hashlib
import json
from pathlib import Path


def etf_rotation_contract():
    path = Path(__file__).resolve().parents[2] / "config/etf_rotation_events.json"
    content = path.read_bytes()
    return {
        "contract": "cn-etf-rotation-source-v1",
        "served_from": "local_config",
        "sha256": hashlib.sha256(content).hexdigest(),
        "evidence": json.loads(content),
        "daily_facts": {
            "endpoint": "/api/v1/data/etf-rotation/daily-facts",
            "contract": "etf-daily-facts-v1",
            "total_return": "gross_ex_date_close_reinvestment",
            "limits": "exchange_rule_derived_0.001_tick",
            "state": "daily_observed_or_reviewed_suspension; intraday partial evidence only",
            "reviewed_through": json.loads(content).get("limit_rules", {}).get("end"),
        },
        "capabilities": {
            "complete_corporate_actions": False,
            "complete_intraday_suspensions": False,
            "complete_historical_limits": False,
        },
    }
