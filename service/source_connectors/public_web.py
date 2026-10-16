"""Bounded public queries with strict parsing, provenance and no silent fallback."""
from __future__ import annotations

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import json
import re
import time
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

import requests

from service.source_connectors import public_parsers as parsers
from service.source_connectors.contracts import AcquisitionMode, ConnectorResult
from service.source_connectors.public_catalog import validate_public_request, QUOTE_FIELDS, GREEKS_FIELDS

HOSTS = frozenset({"irm.cninfo.com.cn", "sns.sseinfo.com", "hq.sinajs.cn",
                  "stock.finance.sina.com.cn", "yield.chinabond.com.cn",
                  "www.chinamoney.com.cn", "www.pbc.gov.cn", "pbc.gov.cn"})


class BoundedTransport:
    """One query: <= 20 requests, 60 seconds, 12 MiB per response, fixed hosts."""
    def __init__(self):
        self.deadline = time.monotonic() + 60
        self.calls = 0
        self.urls = []

    def __call__(self, url, *, method="GET", params=None, data=None, headers=None):
        parsed = urlsplit(url)
        if parsed.scheme != "https" or parsed.hostname not in HOSTS or parsed.port not in (None, 443):
            raise RuntimeError("unapproved public source URL")
        remaining = self.deadline - time.monotonic()
        if remaining <= 0 or self.calls >= 20:
            raise RuntimeError("public query request/time budget exhausted")
        self.calls += 1
        with requests.request(method, url, params=params, data=data,
                              headers={"User-Agent": "Mozilla/5.0", **(headers or {})},
                              timeout=(min(5, remaining), min(15, remaining)),
                              allow_redirects=False, stream=True) as response:
            response.raise_for_status()
            if response.status_code != 200:
                raise RuntimeError("public source returned redirect or non-200 response")
            chunks, size = [], 0
            for chunk in response.iter_content(65536):
                size += len(chunk)
                if size > 12 * 1024 * 1024 or time.monotonic() > self.deadline:
                    raise RuntimeError("public response byte/time budget exhausted")
                chunks.append(chunk)
            response._content = b"".join(chunks)
            response._content_consumed = True
            self.urls.append(response.url)
            return response


def _object(response):
    value = parsers._v39_json(response)
    if not isinstance(value, dict):
        raise RuntimeError("source response must be an object")
    return value


def _rows(payload, key):
    value = payload.get(key)
    if not isinstance(value, list) or not all(isinstance(row, dict) for row in value):
        raise RuntimeError(f"source response missing {key} object array")
    return value


def _cninfo(http, p):
    base = "https://irm.cninfo.com.cn/newircs/"
    matches = _rows(_object(http(base + "index/queryKeyboardInfo", method="POST", data={"keyWord": p["code"]})), "data")
    # Exact identifier only; fuzzy keyboard matches must never select another company.
    matches = [r for r in matches if str(r.get("stockCode", r.get("code", ""))) == p["code"]]
    if not matches:
        raise RuntimeError("CNINFO lookup has no exact stock code match")
    org_id = matches[0].get("secid")
    if not org_id:
        raise RuntimeError("CNINFO lookup missing secid")
    payload = _object(http(base + "company/question", method="POST", params={
        "_t": 1, "stockcode": p["code"], "orgId": org_id, "pageSize": p["page_size"],
        "pageNum": p["page"], "keyWord": "", "startDay": "", "endDay": ""}))
    rows = []
    for raw in _rows(payload, "rows"):
        if str(raw.get("stockCode")) != p["code"] or not raw.get("mainContent"):
            raise RuntimeError("CNINFO returned wrong company or missing question")
        stamp = parsers._v39_req_num(raw.get("pubDate"), "pubDate")
        rows.append({"code": p["code"], "company": raw.get("companyShortName"),
                     "question": raw["mainContent"], "answer": raw.get("attachedContent"),
                     "answerer": raw.get("attachedAuthor"),
                     "question_time": datetime.fromtimestamp(stamp / 1000, ZoneInfo("Asia/Shanghai")).isoformat()})
    return rows


def _sse(http, p):
    base = "https://sns.sseinfo.com"
    headers = {"Referer": base + "/"}
    kind = {"answered": 11, "questions": 10}[p["kind"]]
    if p["code"] is None:
        response = http(base + "/ajax/feeds.do", params={"type": kind, "pageSize": p["page_size"], "lastid": -1, "show": 1, "page": p["page"]}, headers=headers)
    else:
        # Request-local cache avoids stale company mappings and cross-query races.
        pages = {}
        def page(n):
            if n not in pages:
                content = _object(http(base + "/allcompany.do", method="POST", data={"code": "0", "order": "2", "areaId": "0", "page": n}, headers=headers)).get("content")
                if not isinstance(content, str):
                    raise RuntimeError("SSE company list missing content")
                pairs = [(code, uid) for uid, code in re.findall(r"uid=['\"]?(\d+)['\"]?[^>]*>\s*<img[^>]*company/(\d{6})\.png", content)]
                if not pairs and (n == 1 or "没有任何上市公司的信息" not in content):
                    raise RuntimeError("SSE company list format changed")
                if pairs != sorted(pairs):
                    raise RuntimeError("SSE company list order changed")
                pages[n] = pairs
            return pages[n]
        low, high = 1, 1
        while page(high) and page(high)[-1][0] < p["code"]:
            low, high = high, high * 2
            if high > 1024:
                raise RuntimeError("SSE company lookup exceeded page bound")
        uid = None
        while low <= high:
            mid = (low + high) // 2
            pairs = page(mid)
            if not pairs or p["code"] < pairs[0][0]:
                high = mid - 1
            elif p["code"] > pairs[-1][0]:
                low = mid + 1
            else:
                uid = dict(pairs).get(p["code"])
                break
        if uid is None:
            raise RuntimeError("SSE company not found in current directory")
        response = http(base + "/ajax/userfeeds.do", method="POST", data={"typeCode": "company", "type": kind, "pageSize": p["page_size"], "uid": uid, "page": p["page"]}, headers=headers)
    text = response.content.decode("utf-8", "strict")
    header_date = getattr(response, "headers", {}).get("Date")
    reference = parsedate_to_datetime(header_date) if header_date else datetime.now(timezone.utc)
    if reference.tzinfo is None:
        raise RuntimeError("SSE response Date lacks timezone")
    time_token = parsers.SSE_REFERENCE_TIME.set(reference)
    try:
        rows = parsers._sse_parse_feed(text)
    finally:
        parsers.SSE_REFERENCE_TIME.reset(time_token)
    for row in rows:
        row["time_reference"] = reference.isoformat()
        row["time_reference_basis"] = "http_date" if header_date else "fetched_at"
    if not rows and not re.search(r'class="m_feed_note"[^>]*>[^<]*(暂无|暂时没有)[^<]*<', text):
        raise RuntimeError("SSE page has neither questions nor an explicit empty marker")
    if p["code"] and any(r["code"] != p["code"] for r in rows):
        raise RuntimeError("SSE returned another company's questions")
    for row in rows:
        for key in ("question_time", "answer_time"):
            if row[key]:
                row[key] = datetime.fromisoformat(row[key]).replace(tzinfo=ZoneInfo("Asia/Shanghai")).isoformat()
    if len({r["id"] for r in rows}) != len(rows):
        raise RuntimeError("SSE duplicate question IDs")
    return rows


def _sina(http, endpoint, p):
    headers = {"Referer": "https://stock.finance.sina.com.cn/"}
    def values(symbol):
        response = http("https://hq.sinajs.cn/list=" + symbol, headers=headers)
        text = response.content.decode("gbk", "strict")
        match = re.fullmatch(r'\s*var hq_str_' + re.escape(symbol) + r'="([^"\r\n]*)";?\s*', text)
        if not match or not match[1]:
            raise RuntimeError("Sina quote missing or response format changed")
        return match[1].split(",")
    if endpoint == "option_contracts":
        cate = {"510050": "50ETF", "510300": "300ETF", "588000": "科创50ETF", "510500": "500ETF"}[p["underlying"]]
        payload = _object(http("https://stock.finance.sina.com.cn/futures/api/openapi.php/StockOptionService.getStockName", params={"exchange": "null", "cate": cate}, headers=headers))
        months = payload["result"]["data"]["contractMonth"]
        if not isinstance(months, list) or len(months) > 16:
            raise RuntimeError("Sina contract months malformed")
        months = sorted({m.replace("-", "")[2:] for m in months if isinstance(m, str) and re.fullmatch(r"\d{4}-\d{2}", m)})
        if not months:
            raise RuntimeError("Sina has no contract months")
        rows = []
        for month in months:
            flag = "OP_UP_" if p["side"] == "call" else "OP_DOWN_"
            codes = values(flag + p["underlying"] + month)
            for code in codes:
                if not code:
                    continue
                if not re.fullmatch(r"CON_OP_\d{8}", code):
                    raise RuntimeError("Sina contract identifier malformed")
                rows.append({**p, "month": month, "code": code[7:]})
        return rows
    v = values(("CON_OP_" if endpoint == "option_quote" else "CON_SO_") + p["code"])
    if endpoint == "option_quote":
        if len(v) < 43:
            raise RuntimeError("Sina option quote has fewer than 43 fields")
        raw = v[:12] + v[37:43]
        names = QUOTE_FIELDS[1:]
    else:
        if len(v) < 16 or any(v[1:4]):
            raise RuntimeError("Sina Greeks field layout changed")
        raw, names = [v[0]] + v[4:16], GREEKS_FIELDS[1:]
    row = {"code": p["code"]}
    for name, value in zip(names, raw, strict=True):
        row[name] = value if name in {"name", "trade_code"} else parsers._v39_num(value)
    if not row.get("name") or row.get("last") is None:
        raise RuntimeError("Sina option missing name or price")
    if endpoint == "option_greeks" and any(row[k] is None for k in ("delta", "gamma", "theta", "vega", "iv")):
        raise RuntimeError("Sina Greeks core fields missing")
    return [row]


class PublicWebConnector:
    def __init__(self, source, *, transport_factory=BoundedTransport, archive=None):
        self.source = source
        self.transport_factory = transport_factory
        self.archive = archive

    def query(self, request):
        if request.source_id != self.source.source_id or request.acquisition_mode != AcquisitionMode.QUERY_THROUGH:
            raise ValueError("public connector source/mode mismatch")
        p = validate_public_request(request.source_id, request.endpoint_key, request.parameters)
        http = self.transport_factory()
        started = datetime.now(timezone.utc)
        token = parsers.TRANSPORT.set(http)
        warnings = []
        try:
            try:
                if request.source_id == "cninfo":
                    rows = _cninfo(http, p)
                elif request.source_id == "sse":
                    rows = _sse(http, p)
                elif request.source_id == "sina":
                    rows = _sina(http, request.endpoint_key, p)
                else:
                    function = {"chinabond": parsers.chinabond_yield_curve,
                                "chinamoney": parsers.repo_fixing_rates,
                                "pboc": parsers.pboc_social_financing}[request.source_id]
                    frame = function(**p)
                    rows = json.loads(frame.to_json(orient="records", force_ascii=False))
            except (KeyError, TypeError, ValueError, IndexError) as exc:
                raise RuntimeError(f"{request.source_id} upstream structure or data invalid") from exc
            if len(rows) > 10000:
                raise RuntimeError("public query row budget exceeded")
        except Exception as exc:
            if self.archive is not None:
                try:
                    self.archive.archive_failure(endpoint_key=request.endpoint_key, parameters=p, collector_name="public_query", error=exc, requested_at=started)
                except Exception:
                    pass
            raise
        finally:
            parsers.TRANSPORT.reset(token)
        if self.archive is not None:
            try:
                self.archive.archive_response(endpoint_key=request.endpoint_key, parameters=p, collector_name="public_query", records=rows, persist_records=False, requested_at=started)
            except Exception as exc:
                warnings.append(f"query audit unavailable: {type(exc).__name__}")
        dates = sorted(str(r.get("date") or (r.get("month") if request.source_id == "pboc" else None) or r.get("question_time")) for r in rows if r.get("date") or (r.get("month") and request.source_id == "pboc") or r.get("question_time"))
        paged = request.endpoint_key == "investor_questions"
        warnings.append("No point-in-time/revision guarantee; fetched_at is not business time.")
        if paged:
            warnings.append("Only the requested page; no full-history completeness claim.")
        return ConnectorResult(source_id=request.source_id, endpoint_key=request.endpoint_key,
            acquisition_mode=request.acquisition_mode, records=tuple(rows), fetched_rows=len(rows),
            status="page" if paged and rows else "observed" if rows else "empty",
            evidence={"fetched_at": datetime.now(timezone.utc).isoformat(), "source_urls": getattr(http, "urls", []),
                      "parser_version": "1", "schema_validated": True, "point_in_time": False,
                      "completeness": "page_only" if paged else "calendar_unverified",
                      "page": p.get("page"), "possibly_more": len(rows) >= p["page_size"] if paged else None,
                      "observed_start": dates[0] if dates else None, "observed_end": dates[-1] if dates else None,
                      "history_verified": False}, warnings=tuple(warnings))

    execute = query
