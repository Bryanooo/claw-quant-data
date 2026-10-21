"""Auditable ETF research facts; no assertion of intraday executability."""
from decimal import Decimal, ROUND_HALF_UP
import hashlib
import json

from service.data_service.etf_contract import etf_rotation_contract
from service.db import query


VERSION = "etf-daily-facts-v1"


def number(value):
    result = Decimal(str(value))
    if not result.is_finite():
        raise ValueError("Non-finite input")
    return result


def build_facts(symbol, bars, dividends, calendar, evidence, start, end):
    """Compute gross ex-date-close reinvested return, separately from price factors."""
    cross = evidence["cash_crosscheck"]
    rules = evidence["limit_rules"]
    if start < max(cross["start"], rules["start"]) or end > min(cross["end"], rules["end"]):
        raise ValueError("Requested period exceeds reviewed source/rule coverage")
    verified = next((x for x in cross["symbols"] if x["symbol"] == symbol), None)
    if verified is None:
        raise ValueError("ETF is outside reviewed universe")
    expected_cash = {r["ex_date"]: r for r in verified["cash"] if start <= r["ex_date"] <= end}
    if not verified["cash"] and not verified["no_cash_explicit"]:
        raise ValueError("Empty dividend source without explicit no-distribution evidence")
    cash = {}
    for r in dividends:
        day = str(r.get("ex_date") or "")
        if r.get("div_proc") != "实施" or not start <= day <= end:
            continue
        value = (number(r["div_cash"]), str(r.get("pay_date") or ""))
        if day in cash and cash[day] != value:
            raise ValueError("Conflicting dividend records")
        cash[day] = value
    if set(cash) != set(expected_cash):
        raise ValueError("Independent dividend history dates differ")
    for day, (value, pay) in cash.items():
        other = expected_cash[day]
        if abs(value - number(other["div_cash"])) > Decimal("0.00000001") or pay != other["pay_date"]:
            raise ValueError("Independent dividend amount/payment date differs")
    shares = {}
    for event in evidence["share_transformations"]:
        day = event["price_effective_date"]
        if event["symbol"] == symbol and start <= day <= end:
            if day in shares or not event.get("source_url"):
                raise ValueError("Ambiguous share transformation")
            shares[day] = event
    halts = {e["date"]: e for e in evidence["events"] if e["symbol"] == symbol}
    intraday = {e["date"]: e for e in evidence.get("intraday_events", [])
                if e["symbol"] == symbol and start <= e["date"] <= end}
    indexed = {}
    for row in bars:
        day = str(row["trade_date"])
        if day in indexed:
            raise ValueError("Duplicate daily bar")
        indexed[day] = row
    if not indexed:
        raise ValueError("No observed bars")
    if set(cash).difference(indexed) or set(shares).difference(indexed):
        raise ValueError("Corporate action on a day without a priced observation")
    first = min(indexed)
    if first in cash or first in shares:
        raise ValueError("Initial observation is an action date; previous close is required")
    output, previous, level = [], None, Decimal("100")
    for day in calendar:
        if day < first:
            continue
        row = indexed.get(day)
        if row is None:
            if day not in halts:
                raise ValueError(f"Unexplained missing bar: {symbol} {day}")
            output.append({
                "trade_date": day, "daily_state": "full_day_suspended",
                "state_source": halts[day]["source_url"], "intraday_state": "unknown",
                "up_limit": None, "down_limit": None, "limit_rate": None,
                "total_return_index": float(level), "total_return": 0.0,
                "cash_per_old_unit": 0.0, "share_multiplier": 1.0,
                "payment_date": None, "valuation": "last_observed_close",
            })
            continue
        if day in halts or number(row["vol"]) <= 0:
            raise ValueError("Daily activity conflicts with reviewed state")
        rate = number(rules["default_rate"])
        rule_source = rules["source_urls"]
        for override in rules["overrides"]:
            if override["symbol"] == symbol and day >= override["start"]:
                rate = number(override["rate"])
                rule_source = [override["source_url"]]
        reference = number(row["pre_close"])
        close = number(row["close"])
        if reference <= 0 or close <= 0:
            raise ValueError("Invalid reference/close")
        tick = number(rules["tick"])
        up = (reference * (1 + rate)).quantize(tick, rounding=ROUND_HALF_UP)
        down = (reference * (1 - rate)).quantize(tick, rounding=ROUND_HALF_UP)
        if number(row["high"]) > up or number(row["low"]) < down:
            raise ValueError(f"Observed price outside reconstructed limits: {symbol} {day}")
        multiplier = number(shares[day]["new_shares_per_old_share"]) if day in shares else Decimal(1)
        dividend, pay = cash.get(day, (Decimal(0), None))
        if day in shares and day in cash:
            raise ValueError("Simultaneous cash/split needs explicit event ordering")
        gross = (close * multiplier + dividend) / previous if previous else None
        if gross is not None:
            level *= gross
        output.append({
            "trade_date": day, "daily_state": "traded",
            "state_source": "tushare.fund_daily:positive_volume",
            "intraday_state": "reviewed_partial_suspension" if day in intraday else "unknown",
            "intraday_event": intraday.get(day),
            "reference_price": float(reference), "limit_rate": float(rate),
            "up_limit": float(up), "down_limit": float(down),
            "limit_source": "exchange_rule_derived", "limit_rule_sources": rule_source,
            "total_return_index": float(level),
            "total_return": float(gross - 1) if gross is not None else None,
            "cash_per_old_unit": float(dividend), "share_multiplier": float(multiplier),
            "payment_date": pay, "valuation": "observed_close",
            "source_record_hash": row.get("_record_hash"),
            "share_source": shares.get(day, {}).get("source_url"),
        })
        previous = close
    return {
        "contract": VERSION, "symbol": symbol, "data": output,
        "audit": {"sessions": len(output), "cash_events": len(cash),
                  "share_events": len(shares), "unknown_daily_states": 0,
                  "reviewed_intraday_events": len(intraday),
                  "limit_method": "exchange_rule_derived",
                  "tr_method": "gross_ex_date_close_reinvestment",
                  "dividend_crosscheck": verified["source_url"],
                  "dividend_crosscheck_sha256": verified["sha256"]},
        "limitations": [
            "Total return is a gross theoretical index: cash is reinvested at ex-date close, before payment; fractional units, no tax/fees.",
            "First observed close is indexed to 100; first-day return is unavailable.",
            "Daily traded means observed positive volume, not uninterrupted trading or guaranteed fills.",
            "Intraday suspensions/order-book availability remain unknown.",
            "Limit prices are reconstructed from vendor reference prices and exchange rules, not an exchange historical price feed.",
        ],
    }


def daily_facts(symbol, start, end):
    if end < start:
        raise ValueError("Invalid date range")
    envelope = etf_rotation_contract()
    if symbol not in {r["symbol"] for r in envelope["evidence"]["cash_crosscheck"]["symbols"]}:
        raise ValueError("ETF is outside reviewed universe")
    bars = query(
        "SELECT * FROM tushare_norm_fund_daily WHERE ts_code=%s "
        "AND trade_date BETWEEN %s AND %s ORDER BY trade_date", (symbol, start, end))
    dividends = query("SELECT * FROM tushare_norm_fund_div WHERE ts_code=%s", (symbol,))
    calendar = [str(r["cal_date"]) for r in query(
        "SELECT cal_date FROM trade_cal WHERE exchange='SSE' AND is_open=1 "
        "AND cal_date BETWEEN %s AND %s ORDER BY cal_date", (start, end))]
    result = build_facts(symbol, bars, dividends, calendar, envelope["evidence"], start, end)
    result["evidence_sha256"] = envelope["sha256"]
    result["input_sha256"] = hashlib.sha256(json.dumps(
        {"bars": bars, "dividends": dividends, "calendar": calendar},
        sort_keys=True, default=str).encode()).hexdigest()
    return result
