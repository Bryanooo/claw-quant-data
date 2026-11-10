"""A-share announcement metadata; documents are fetched only on explicit demand."""

from datetime import date, datetime, timedelta, timezone
import hashlib
import html
import json
import math
import time
import re
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from psycopg2.extras import Json, execute_values
from service.db import get_conn, query
from service.source_connectors.contracts import AcquisitionMode, ConnectorResult

CST = ZoneInfo("Asia/Shanghai")
A_SHARE_CODE = re.compile(r"^(?:[03648]\d{5}|92\d{4})$")


def document_url(path):
    if not isinstance(path, str) or not re.fullmatch(
        r"finalpage/\d{4}-\d{2}-\d{2}/\d+\.PDF", path, re.I
    ):
        raise ValueError("Unsupported official document path")
    return "https://static.cninfo.com.cn/" + path


def parse_record(row, day):
    code = str(row.get("secCode") or "")
    if not A_SHARE_CODE.fullmatch(code):
        return None
    identity = str(row.get("announcementId") or "")
    if not identity.isdecimal():
        raise ValueError("Announcement identity missing")
    published = datetime.fromtimestamp(
        int(row["announcementTime"]) / 1000, timezone.utc
    )
    if published.astimezone(CST).date() != day:
        raise ValueError("Provider ignored requested announcement date")
    title = html.unescape(
        re.sub("<[^>]*>", "", str(row.get("announcementTitle") or ""))
    ).strip()
    if not title:
        raise ValueError("Announcement title missing")
    suffix = ".SZ" if code[0] in "03" else ".SH" if code[0] == "6" else ".BJ"
    values = {
        "source": "cninfo",
        "announcement_id": identity,
        "ts_code": code + suffix,
        "ann_date": day.isoformat(),
        "published_at": published.isoformat(),
        "title": title,
        "document_url": document_url(row["adjunctUrl"]),
    }
    values["_record_hash"] = hashlib.sha256(
        json.dumps(values, sort_keys=True).encode()
    ).hexdigest()
    return values


def store_metadata(rows):
    if not rows:
        return 0
    names = (
        "_record_hash",
        "source",
        "announcement_id",
        "ts_code",
        "ann_date",
        "published_at",
        "title",
        "document_url",
    )
    with get_conn() as conn, conn.cursor() as cur:
        execute_values(
            cur,
            "INSERT INTO stock_announcements (" + ",".join(names) + ") VALUES %s "
            "ON CONFLICT(_record_hash) DO UPDATE SET last_seen_at=now()",
            [tuple(row[k] for k in names) for row in rows],
            page_size=500,
        )
    return len(rows)


def collect_day(day, transport, store=store_metadata):
    """Exhaust each exchange catalog separately; the combined feed can overlap pages."""
    all_rows, seen = [], set()
    raw_count = page_count = 0
    partitions = {}
    for plate, suffix in (("sz", ".SZ"), ("sh", ".SH"), ("bj", ".BJ")):
        total = None
        fetched = 0
        for page in range(1, 701):
            if page_count >= 700:
                raise ValueError("Announcement page budget exhausted")
            if page_count:
                time.sleep(0.15)
            page_count += 1
            response = transport(
                "https://www.cninfo.com.cn/new/hisAnnouncement/query",
                method="POST",
                data={
                    "pageNum": page,
                    "pageSize": 30,
                    "column": "szse",
                    "tabName": "fulltext",
                    "seDate": f"{day}~{day}",
                    "sortName": "",
                    "sortType": "",
                    "plate": plate,
                },
                headers={"Referer": "https://www.cninfo.com.cn/"},
            )
            obj = response.json()
            batch = obj.get("announcements")
            number = obj.get("totalAnnouncement")
            if (
                not isinstance(number, int)
                or isinstance(number, bool)
                or number < 0
                or (not isinstance(batch, list) and not (number == 0 and batch is None))
            ):
                raise ValueError("Announcement pagination contract missing")
            batch = batch or []
            if total is None:
                total = number
            if total != number or total > 21000 or len(batch) > 30:
                raise ValueError(
                    "Announcement total changed or exceeded request budget"
                )
            if len(batch) != min(30, max(0, total - fetched)):
                raise ValueError("Announcement page is incomplete")
            parsed = []
            for row in batch:
                key = (str(row.get("announcementId")), str(row.get("secCode")))
                if key in seen:
                    raise ValueError("Repeated announcement identity/page")
                seen.add(key)
                record = parse_record(row, day)
                if record is not None:
                    if not record["ts_code"].endswith(suffix):
                        raise ValueError(
                            "Provider ignored requested announcement exchange"
                        )
                    parsed.append(record)
            # Persist observations, but publish readiness only after every partition exhausts.
            store(parsed)
            all_rows.extend(parsed)
            fetched += len(batch)
            raw_count += len(batch)
            if fetched == total:
                if obj.get("hasMore") is True:
                    raise ValueError(
                        "Provider reports more pages beyond declared total"
                    )
                partitions[plate] = {"total": total, "fetched": fetched, "pages": page}
                break
        else:
            raise ValueError("Announcement page budget exhausted")
    return all_rows, {
        "verified": True,
        "verification_type": "cninfo_exchange_day_pagination_v1",
        "requested_day": day.isoformat(),
        "catalog_total": sum(p["total"] for p in partitions.values()),
        "catalog_fetched": raw_count,
        "partitions": partitions,
        "fetched_rows": len(all_rows),
        "stored_rows": len(all_rows),
        "pages": page_count,
        "non_a_share_filtered": raw_count - len(all_rows),
        "body_downloaded": False,
        "scope": "exhausted public exchange catalogs; no regulatory completeness guarantee",
    }


def collect_announcements(request):
    from service.source_connectors.public_web import BoundedTransport

    if (
        request.source_id != "cninfo"
        or request.endpoint_key != "announcements"
        or request.acquisition_mode != AcquisitionMode.SCHEDULED_PULL
    ):
        raise ValueError("Unsupported announcement request")
    params = request.parameters.get("parameters", request.parameters)
    if set(params) != {"start_date", "end_date"}:
        raise ValueError("Announcement collection requires an exact date window")
    start = date.fromisoformat(params["start_date"])
    end = date.fromisoformat(params["end_date"])
    if start != end or end >= datetime.now(CST).date():
        raise ValueError("Collect one closed calendar day per execution")
    rows, evidence = collect_day(end, BoundedTransport(max_calls=700, seconds=600))
    return ConnectorResult(
        source_id="cninfo",
        endpoint_key="announcements",
        acquisition_mode=request.acquisition_mode,
        records=tuple(rows),
        fetched_rows=len(rows),
        stored_rows=len(rows),
        status="complete" if rows else "empty",
        evidence=evidence,
    )


def fetch_document(record_hash, transport=None):
    if not re.fullmatch("[a-f0-9]{64}", record_hash):
        raise ValueError("Invalid announcement identity")
    rows = query(
        "SELECT * FROM stock_announcements WHERE _record_hash=%s", (record_hash,)
    )
    if not rows:
        raise LookupError("Announcement not found")
    row = rows[0]
    url = row["document_url"]
    parsed = urlsplit(url)
    if (
        parsed.scheme != "https"
        or parsed.hostname != "static.cninfo.com.cn"
        or parsed.port not in (None, 443)
        or parsed.username
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("Unapproved document URL")
    document_url(parsed.path.lstrip("/"))
    if transport is None:
        from service.source_connectors.public_web import BoundedTransport

        transport = BoundedTransport()
    response = transport(url)
    data = response.content
    if not data.startswith(b"%PDF-") or len(data) > 12 * 1024 * 1024:
        raise ValueError("Document is not a bounded PDF")
    return data, {
        "source_url": url,
        "sha256": hashlib.sha256(data).hexdigest(),
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "published_at": str(row["published_at"]),
        "persistent_body_storage": False,
        "historical_body_version_guaranteed": False,
    }
