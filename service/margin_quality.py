"""Margin balance semantics shared by research and independent row audits."""

from collections import defaultdict
from datetime import date
from decimal import Decimal, InvalidOperation

BALANCE_FIELDS = ("rzye", "rqye", "rzrqye")


def balance_issues(row):
    values, issues = {}, []
    for field in BALANCE_FIELDS:
        try:
            value = Decimal(str(row.get(field)))
            if not value.is_finite() or value < 0:
                raise ValueError()
            values[field] = value
        except (InvalidOperation, ValueError):
            issues.append("missing_or_invalid:" + field)
    if not issues and abs(values["rzrqye"] - values["rzye"] - values["rqye"]) > Decimal(
        "0.01"
    ):
        issues.append("balance_sum_mismatch")
    return issues


def valid_balance_sql():
    # Code-owned SQL, no interpolated input; numeric bounds also reject NaN.
    return (
        " AND ".join(
            f"{field} IS NOT NULL AND {field} >= 0 AND {field} < 'Infinity'::numeric"
            for field in BALANCE_FIELDS
        )
        + " AND abs(rzrqye-rzye-rqye)<=0.01"
    )


def market_balances(rows, days):
    grouped = defaultdict(list)
    for row in rows:
        raw = str(row.get("trade_date", ""))
        try:
            observed = date.fromisoformat(
                raw if "-" in raw else f"{raw[:4]}-{raw[4:6]}-{raw[6:8]}"
            )
        except ValueError:
            continue
        grouped[observed].append(row)
    series = {field: [] for field in BALANCE_FIELDS}
    incomplete = []
    for observed in sorted(grouped)[-days:]:
        members = grouped[observed]
        expected = {"SSE", "SZSE"} | (
            {"BSE"} if observed >= date(2023, 2, 13) else set()
        )
        actual = [row.get("exchange_id") for row in members]
        bad = [
            dict(exchange_id=row.get("exchange_id"), issues=balance_issues(row))
            for row in members
            if balance_issues(row)
        ]
        if set(actual) != expected or len(actual) != len(expected) or bad:
            incomplete.append(
                dict(
                    date=str(observed),
                    missing_exchanges=sorted(expected - set(actual)),
                    unexpected_exchanges=sorted(set(actual) - expected, key=str),
                    duplicate_exchanges=len(actual) != len(set(actual)),
                    invalid_rows=bad,
                )
            )
            # Do not chart a partial exchange sum or replace a missing value by zero.
            continue
        for field in BALANCE_FIELDS:
            total = sum(Decimal(str(row[field])) for row in members)
            series[field].append(
                (
                    str(observed),
                    float((total / Decimal("1e8")).quantize(Decimal(".01"))),
                )
            )
    return dict(
        series=series,
        incomplete_dates=incomplete,
        status="partial" if incomplete else "ready" if grouped else "missing",
    )
