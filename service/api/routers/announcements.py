"""Read-only metadata and explicit on-demand document access."""

import json, subprocess, sys
from datetime import date, datetime, time, timedelta
from typing import Literal
from zoneinfo import ZoneInfo
from fastapi import APIRouter, HTTPException, Query, Response
from service.db import query
from service.announcements import fetch_document

router = APIRouter(prefix="/v1/research", tags=["research"])


@router.get("/stocks/{ts_code}/announcements")
def announcements(
    ts_code: str,
    as_of: date | None = None,
    limit: int = Query(50, ge=1, le=200),
    knowledge: Literal["known_then", "reconstructed"] = "known_then",
):
    import re

    if not re.fullmatch(r"\d{6}\.(SH|SZ|BJ)", ts_code):
        raise HTTPException(422, "Invalid stock code")
    cutoff = datetime.combine(
        (as_of or datetime.now(ZoneInfo("Asia/Shanghai")).date()) + timedelta(days=1),
        time(),
        ZoneInfo("Asia/Shanghai"),
    )
    rows = query(
        "SELECT * FROM stock_announcements WHERE ts_code=%s AND published_at<%s "
        "AND (%s OR first_observed_at<%s) ORDER BY published_at DESC,_record_hash LIMIT %s",
        (ts_code, cutoff, knowledge == "reconstructed", cutoff, limit),
    )
    return {
        "data": rows,
        "meta": {
            "knowledge": knowledge,
            "as_of": as_of,
            "limit": limit,
            "body_policy": "on_demand_only",
            "coverage": "observed_catalog_records_not_global_certification",
        },
    }


@router.get("/announcements/{record_hash}/document")
def document(
    record_hash: str,
    response: Response,
    format: Literal["pdf", "text"] = "text",
    page_start: int = Query(0, ge=0),
    page_count: int = Query(10, ge=1, le=25),
):
    try:
        data, meta = fetch_document(record_hash)
    except LookupError as e:
        raise HTTPException(404, str(e)) from e
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    except Exception as e:
        raise HTTPException(502, "Official document is unavailable") from e
    response.headers["Cache-Control"] = "no-store"
    if format == "pdf":
        return Response(
            data,
            media_type="application/pdf",
            headers={"X-Document-SHA256": meta["sha256"], "Cache-Control": "no-store"},
        )
    try:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "service.announcement_text",
                str(page_start),
                str(page_count),
            ],
            input=data,
            capture_output=True,
            timeout=20,
            check=True,
        )
        body = json.loads(result.stdout)
    except (subprocess.SubprocessError, ValueError) as e:
        raise HTTPException(
            422,
            "PDF text unavailable or resource budget exceeded; request the PDF directly",
        ) from e
    return {"data": body, "meta": meta}
