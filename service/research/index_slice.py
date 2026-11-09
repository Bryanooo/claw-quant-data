"""Frozen one-session research matrices; never substitute today's constituents."""

from __future__ import annotations

from contextlib import closing
from datetime import date, datetime, time, timedelta
from hashlib import sha256
import json
import math
import re
from zoneinfo import ZoneInfo

import psycopg2
from psycopg2.extras import RealDictCursor

from service.config import DB_CONFIG
from .local_factors.catalog import FACTOR_BY_NAME, FACTOR_SCHEMA_VERSION
from .local_factors.issue import issue_category


INDEX = "000300.SH"
VERSION = "csi300-factor-slice/v1"
MODES = ("known_then", "reconstructed")


class EvidenceUnavailable(Exception):
    """A required trading session or exact index composition is not evidenced."""


def canonical(obj):
    return json.dumps(
        obj, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":")
    ).encode()


def content_hash(obj):
    return sha256(canonical(obj)).hexdigest()


def request_factors(names):
    if not 1 <= len(names) <= 32 or len(set(names)) != len(names):
        raise ValueError("supply between 1 and 32 distinct local factor names")
    if unknown := sorted(set(names) - FACTOR_BY_NAME.keys()):
        raise ValueError(f"unknown local factors: {unknown}")
    return tuple(names)


def factor_cell(name, value, bit, evidence, missing_snapshot):
    if missing_snapshot:
        return dict(value=None, available=False, reason="no_eligible_snapshot")
    category = issue_category(name, value is not None, evidence)
    if value is not None and not math.isfinite(value):
        category = "non_finite_value"
    elif (value is not None) != bool(bit):
        category = "value_mask_conflict"
    detail = (evidence.get("unresolved") or {}).get(name) or (
        evidence.get("excluded") or {}
    ).get(name)
    ok = bit == 1 and value is not None and category == "calculated" and not detail
    return dict(
        value=value if ok else None,
        available=bool(ok),
        reason=None if ok else (detail or category),
    )


def build_slice(day: date, names, mode="known_then"):
    names = request_factors(names)
    if mode not in MODES:
        raise ValueError("unknown knowledge mode")
    cutoff = datetime.combine(
        day + timedelta(days=1), time.min, ZoneInfo("Asia/Shanghai")
    )
    if day >= datetime.now(ZoneInfo("Asia/Shanghai")).date():
        raise ValueError("only completed historical dates are supported")
    strict = mode == "known_then"
    # All SQL fragments are generated from the versioned local factor catalog, never user SQL.
    positions = [FACTOR_BY_NAME[n].position for n in names]
    values = ",".join(f"f.factor_values[{pos}]" for pos in positions)
    bits = ",".join(f"get_bit(f.ready_mask,{pos - 1})" for pos in positions)
    conn = psycopg2.connect(**{**DB_CONFIG, "connect_timeout": 5})
    with closing(conn), conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        conn.set_session(isolation_level="REPEATABLE READ", readonly=True)
        cur.execute("SET LOCAL statement_timeout='15s'")
        cur.execute("SET LOCAL TIME ZONE 'UTC'")
        cur.execute(
            "SELECT is_open FROM trade_cal WHERE exchange='SSE' AND cal_date=%s",
            (day.strftime("%Y%m%d"),),
        )
        session = cur.fetchone()
        if not session or not session["is_open"]:
            raise EvidenceUnavailable("trade calendar missing or not a trading session")
        cur.execute(
            f"""
            WITH members AS (
              SELECT con_code, array_agg(DISTINCT weight ORDER BY weight) weights,
                     max(_first_seen_at) last_first_seen,
                     array_agg(_record_hash ORDER BY _record_hash) hashes
              FROM tushare_norm_index_weight WHERE index_code=%s AND trade_date=%s
                AND (NOT %s OR _first_seen_at < %s)
              GROUP BY con_code
            )
            SELECT m.*, f.audit_status, f.audit_evidence, f.computed_at, f.input_revision_digest,
                   f.formula_digest, ARRAY[{values}] vals, ARRAY[{bits}] bits
            FROM members m LEFT JOIN local_factor_snapshot f ON f.ts_code=m.con_code
              AND f.trade_date=%s AND f.schema_version=%s AND (NOT %s OR f.computed_at < %s)
            ORDER BY m.con_code
        """,
            (INDEX, day, strict, cutoff, day, FACTOR_SCHEMA_VERSION, strict, cutoff),
        )
        records = cur.fetchall()
        if len(records) != 300 or any(
            not re.fullmatch(r"[0-9]{6}\.(SH|SZ)", r["con_code"] or "") for r in records
        ):
            raise EvidenceUnavailable(
                f"expected 300 distinct same-date CSI300 members, observed {len(records)} in {mode}; no carry-forward"
            )
        cur.execute(
            """SELECT dataset_name,status,audit_id FROM sys_data_coverage_partition
            WHERE partition_date=%s AND dataset_name IN ('local_factor_snapshot','index_weight')
            ORDER BY dataset_name""",
            (day,),
        )
        audits = {
            r["dataset_name"]: dict(status=r["status"], audit_id=r["audit_id"])
            for r in cur.fetchall()
        }
    rows = []
    for r in records:
        if (
            len(r["weights"]) != 1
            or r["weights"][0] is None
            or not r["weights"][0].is_finite()
            or not 0 <= r["weights"][0] <= 100
        ):
            raise EvidenceUnavailable(
                f"ambiguous or invalid index weight: {r['con_code']}"
            )
        cells = {
            name: factor_cell(
                name, value, bit, r["audit_evidence"] or {}, r["computed_at"] is None
            )
            for name, value, bit in zip(names, r["vals"], r["bits"], strict=True)
        }
        rows.append(
            dict(
                ts_code=r["con_code"],
                weight=str(r["weights"][0]),
                membership_hashes=r["hashes"],
                membership_first_seen=r["last_first_seen"].isoformat(),
                factors=cells,
                audit_status=r["audit_status"],
                computed_at=r["computed_at"].isoformat() if r["computed_at"] else None,
                input_digest=r["input_revision_digest"],
                formula_digest=r["formula_digest"],
            )
        )
    manifest = dict(
        contract=VERSION,
        trade_date=day.isoformat(),
        index_code=INDEX,
        knowledge_mode=mode,
        cutoff_exclusive=cutoff.isoformat(),
        factor_schema=FACTOR_SCHEMA_VERSION,
        factors=list(names),
        member_count=len(rows),
        coverage_at_export=audits,
        available_counts={
            n: sum(r["factors"][n]["available"] for r in rows) for n in names
        },
        rows_sha256=content_hash(rows),
    )
    return dict(manifest=manifest, rows=rows, slice_id=content_hash(manifest))
