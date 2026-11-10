from datetime import date, datetime
from types import SimpleNamespace
from zoneinfo import ZoneInfo
import copy, io, subprocess, sys
import pytest
from service import announcements as a
from service.source_connectors.ant_checkpoint import resumable_transport
from service.source_connectors.ant_scheduled import SCHEDULED_ROUTES
from service.orchestration_v2.scheduling import dispatch_closed_calendar_events
from service.orchestration_v2.recovery_policy import A_SHARE_PAUSED_DATASETS
from service.orchestration_v2.automation_status import task_automation

DAY = date(2026, 11, 9)


def raw(i, code="300471"):
    return {
        "announcementId": str(i),
        "secCode": code,
        "announcementTime": int(
            datetime(2026, 11, 9, 12, tzinfo=ZoneInfo("Asia/Shanghai")).timestamp()
            * 1000
        ),
        "announcementTitle": "<em>测试</em>公告",
        "adjunctUrl": f"finalpage/2026-11-09/{i}.PDF",
    }


def http(pages):
    def send(*args, **kwargs):
        obj = (
            pages[kwargs["data"]["pageNum"] - 1]
            if kwargs["data"]["plate"] == "sz"
            else page(None, 0)
        )
        return SimpleNamespace(json=lambda: obj)

    return send


def page(rows, total, more=False):
    return {"announcements": rows, "totalAnnouncement": total, "hasMore": more}


def test_public_catalog_pagination_and_observation_versions(monkeypatch):
    monkeypatch.setattr(a.time, "sleep", lambda _: None)
    rows, evidence = a.collect_day(
        DAY,
        http([page([raw(i) for i in range(30)], 31, True), page([raw(30)], 31)]),
        store=lambda rows: len(rows),
    )
    assert (
        len(rows) == 31
        and a.parse_record(raw(30, "920001"), DAY)["ts_code"] == "920001.BJ"
    )
    assert (
        evidence["verified"]
        and evidence["pages"] == 4
        and not evidence["body_downloaded"]
    )
    assert rows[0]["title"] == "测试公告"
    revised = raw(0)
    revised["announcementTitle"] = "更正公告"
    assert a.parse_record(revised, DAY)["_record_hash"] != rows[0]["_record_hash"]


@pytest.mark.parametrize(
    "pages",
    [
        [page([raw(1)], 2)],
        [page([raw(1)] * 30, 30)],
        [page([raw(1)], 1, True)],
        [page([dict(raw(1), announcementTime=0)], 1)],
        [page([dict(raw(1), adjunctUrl="https://evil.example/test.PDF")], 1)],
    ],
)
def test_unverified_catalog_cannot_publish_success(pages):
    with pytest.raises(ValueError):
        a.collect_day(DAY, http(pages), store=lambda _: None)


def test_verified_empty_and_non_a_share_filter():
    rows, evidence = a.collect_day(DAY, http([page(None, 0)]), store=lambda _: None)
    assert rows == [] and evidence["verified"]
    rows, evidence = a.collect_day(
        DAY, http([page([raw(1, "200001")], 1)]), store=lambda _: None
    )
    assert not rows and evidence["non_a_share_filtered"] == 1


@pytest.mark.parametrize(
    "url",
    [
        "http://static.cninfo.com.cn/finalpage/2026-11-09/1.PDF",
        "https://evil.example/finalpage/2026-11-09/1.PDF",
        "https://static.cninfo.com.cn/private?url=evil",
    ],
)
def test_document_fetch_cannot_be_redirected(monkeypatch, url):
    monkeypatch.setattr(a, "query", lambda *_: [{"document_url": url}])
    with pytest.raises(ValueError):
        a.fetch_document("a" * 64, lambda *_: pytest.fail("unexpected network request"))


def test_document_only_downloads_when_explicitly_requested(monkeypatch):
    monkeypatch.setattr(
        a,
        "query",
        lambda *_: [
            {
                "document_url": a.document_url("finalpage/2026-11-09/1.PDF"),
                "published_at": "2026-11-09",
            }
        ],
    )
    data, meta = a.fetch_document(
        "a" * 64, lambda *_: SimpleNamespace(content=b"%PDF-1.7\n")
    )
    assert data.startswith(b"%PDF") and meta["persistent_body_storage"] is False


def test_pdf_extraction_runs_in_bounded_child():
    from pypdf import PdfWriter

    output = io.BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(100, 100)
    writer.write(output)
    result = subprocess.run(
        [sys.executable, "-m", "service.announcement_text", "0", "1"],
        input=output.getvalue(),
        capture_output=True,
        timeout=20,
    )
    assert result.returncode == 0, result.stderr.decode()
    assert b'"ocr_performed": false' in result.stdout
    bad = subprocess.run(
        [sys.executable, "-m", "service.announcement_text", "2", "1"],
        input=output.getvalue(),
        capture_output=True,
        timeout=20,
    )
    assert bad.returncode != 0


def test_calendar_events_include_weekends_and_catch_up():
    class Store:
        requests = []

        def active_task_keys(self):
            return {"cninfo_announcements", "stk_seasoned"}

        def create_execution(self, r):
            self.requests.append(r)
            return {}, True

    store = Store()
    result = dispatch_closed_calendar_events(date(2026, 11, 9), repository=store)
    assert result["created"] == 14
    assert {r.observation_start for r in store.requests} == {
        date(2026, 11, i) for i in range(2, 9)
    }
    assert all(r.observation_start == r.observation_end for r in store.requests)


@pytest.mark.parametrize("key", sorted(A_SHARE_PAUSED_DATASETS))
def test_paused_tasks_report_policy_instead_of_weekly_refresh(key):
    assert (
        task_automation(key, {"schedule": {"mode": "cron"}}, [])["state"]
        == "paused_policy"
    )


class MemoryCheckpoint:
    def __init__(self):
        self.data = {}

    def get(self, route, period, request):
        return copy.deepcopy(self.data.get((route, period, str(request))))

    def put(self, route, period, request, result):
        self.data[(route, period, str(request))] = copy.deepcopy(result)


def response(spec, symbol):
    return {
        "url": spec.route,
        "meta": {"fields": ["symbol", "end_date"]},
        "data": [[symbol, "2026-09-30"]],
    }


def test_ant_resume_skips_successes_but_retries_failed_child(monkeypatch):
    spec = SCHEDULED_ROUTES["stock_fnd.equity-structure"]
    checkpoint = MemoryCheckpoint()
    calls = []
    monkeypatch.setattr(
        "service.source_connectors.ant_scheduled.store_rows", lambda _, rows: len(rows)
    )
    payload = {
        "requests": [
            {"url": spec.route, "params": {"symbols": [code]}}
            for code in ("000001.SZ", "000002.SZ")
        ]
    }

    def first(p):
        calls.append(p)
        return {
            "status": "SUCCESS",
            "results": [response(spec, "000001.SZ"), {"status": "FAILED"}],
        }

    with pytest.raises(RuntimeError):
        resumable_transport(spec, first, checkpoint, "2026-W46")(payload)

    def retry(p):
        calls.append(p)
        return {"status": "SUCCESS", "results": [response(spec, "000002.SZ")]}

    result = resumable_transport(spec, retry, checkpoint, "2026-W46")(payload)
    assert [len(c["requests"]) for c in calls] == [2, 1] and len(result["results"]) == 2
    assert len(checkpoint.data) == 2


def test_new_week_does_not_reuse_stale_ant_snapshot(monkeypatch):
    spec = SCHEDULED_ROUTES["stock_fnd.equity-structure"]
    checkpoint = MemoryCheckpoint()
    monkeypatch.setattr(
        "service.source_connectors.ant_scheduled.store_rows", lambda _, rows: len(rows)
    )
    payload = {"requests": [{"url": spec.route, "params": {"symbols": ["000001.SZ"]}}]}
    calls = []

    def send(p):
        calls.append(p)
        return {"status": "SUCCESS", "results": [response(spec, "000001.SZ")]}

    for period in ("2026-W45", "2026-W45", "2026-W46"):
        resumable_transport(spec, send, checkpoint, period)(payload)
    assert len(calls) == 2


def test_acquisition_handler_unwraps_calendar_request(monkeypatch):
    from service.acquisition_runtime.registry import TASKS

    # The neutral acquisition handler wraps endpoint arguments in parameters.
    seen = []
    monkeypatch.setattr(
        a,
        "collect_day",
        lambda day, transport: (seen.append(day) or [], {"verified": True}),
    )
    from service.source_connectors.contracts import ConnectorRequest, AcquisitionMode

    result = a.collect_announcements(
        ConnectorRequest(
            source_id="cninfo",
            endpoint_key="announcements",
            acquisition_mode=AcquisitionMode.SCHEDULED_PULL,
            parameters={
                "parameters": {"start_date": str(DAY), "end_date": str(DAY)},
                "complete": True,
            },
        )
    )
    assert seen == [DAY] and result.status == "empty"


def test_each_exchange_is_exhausted_without_cross_exchange_rows(monkeypatch):
    monkeypatch.setattr(a.time, "sleep", lambda _: None)
    records = {"sz": raw(1), "sh": raw(2, "600001"), "bj": raw(3, "920001")}

    def send(*args, **kwargs):
        params = kwargs["data"]
        assert params["sortName"] == "" and params["sortType"] == ""
        return SimpleNamespace(json=lambda: page([records[params["plate"]]], 1))

    rows, evidence = a.collect_day(DAY, send, store=lambda _: None)
    assert evidence["catalog_total"] == 3 and set(evidence["partitions"]) == {
        "sz",
        "sh",
        "bj",
    }
    assert {r["ts_code"] for r in rows} == {"300471.SZ", "600001.SH", "920001.BJ"}
    records["bj"] = raw(4, "600002")
    with pytest.raises(ValueError, match="exchange"):
        a.collect_day(DAY, send, store=lambda _: None)


def test_discovery_includes_events_supplements_and_paused_collection():
    from service.data_service.dependencies import interface_inventory, interface_detail

    inventory = {(row["source"], row["key"]): row for row in interface_inventory()}
    issuance = inventory["tushare", "stk_seasoned"]
    assert issuance["field_count"] == 69 and issuance["status"] == "active"
    notice = inventory["cninfo", "cninfo/announcements"]
    assert (
        notice["datasets"] == ["stock_announcements"]
        and notice["acquisition_kind"] == "scheduled"
    )
    assert (
        len(interface_detail("cninfo", "cninfo/announcements")["output_parameters"])
        == 8
    )
    assert all(
        inventory["tushare", key]["status"] == "paused"
        for key in A_SHARE_PAUSED_DATASETS
    )
