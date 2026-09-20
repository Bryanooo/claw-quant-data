from __future__ import annotations

import pandas as pd
import pytest

from collectors.base import CollectorRateLimitError
from collectors.tushare_raw import IncompleteCollectionError
from service.major_news import collect_major_news_window


class FakeCollector:
    def __init__(self, responder):
        self.responder = responder
        self.requests = []
        self.stored = []
        self.normalization_evidence = {"complete": True, "normalized_rows": 0}

    def fetch(self, **parameters):
        self.requests.append(parameters)
        return self.responder(parameters)

    def store(self, frame):
        self.stored.append(frame.copy())
        count = len(frame)
        self.normalization_evidence["normalized_rows"] += count
        return count


class FakeCheckpoints:
    def __init__(self):
        self.values = {}

    def get(self, source, start, end):
        return self.values.get((source, start, end))

    def mark_split(self, source, start, end):
        self.values[(source, start, end)] = {"status": "split"}

    def mark_complete(
        self, source, start, end, *, rows_fetched, rows_stored
    ):
        self.values[(source, start, end)] = {
            "status": "complete",
            "rows_fetched": rows_fetched,
            "rows_stored": rows_stored,
        }


def test_major_news_fans_out_every_source_and_requests_content():
    collector = FakeCollector(
        lambda request: pd.DataFrame(
            [{"title": request["src"], "src": request["src"]}]
        )
    )

    evidence = collect_major_news_window(
        collector,
        {"start_date": "20260918", "end_date": "20260918"},
        fields="title,content,pub_time,src",
        sources=("新浪财经", "财联社"),
    )

    assert evidence["verified"] is True
    assert evidence["sources"] == ["新浪财经", "财联社"]
    assert evidence["rows_fetched"] == 2
    assert evidence["rows_stored"] == 2
    assert len(collector.stored) == 2
    assert all(
        request["fields"] == "title,content,pub_time,src"
        for request in collector.requests
    )
    assert collector.requests[0]["start_date"] == "2026-09-18 00:00:00"
    assert collector.requests[0]["end_date"] == "2026-09-18 23:59:59"


def test_major_news_splits_capped_windows_without_storing_the_parent_page():
    def responder(request):
        if request["start_date"].endswith("00:00:00") and request[
            "end_date"
        ].endswith("23:59:59"):
            return pd.DataFrame(
                [{"title": str(index), "src": "新浪财经"} for index in range(400)]
            )
        return pd.DataFrame([{"title": request["start_date"], "src": "新浪财经"}])

    collector = FakeCollector(responder)
    evidence = collect_major_news_window(
        collector,
        {"start_date": "20260918", "end_date": "20260918", "src": "新浪财经"},
        fields="title,content,pub_time,src",
    )

    assert evidence["adaptive_splits"] == 1
    assert evidence["rows_fetched"] == 2
    assert len(collector.requests) == 3
    assert len(collector.stored) == 2
    assert collector.requests[1]["end_date"] == "2026-09-18 11:59:59"
    assert collector.requests[2]["start_date"] == "2026-09-18 12:00:00"


def test_major_news_resumes_only_unfinished_adaptive_windows():
    checkpoints = FakeCheckpoints()
    calls = {"count": 0}

    def responder(request):
        calls["count"] += 1
        if request["start_date"].endswith("00:00:00") and request[
            "end_date"
        ].endswith("23:59:59"):
            return pd.DataFrame(
                [{"title": str(index), "src": "新浪财经"} for index in range(400)]
            )
        if request["start_date"].endswith("12:00:00") and calls["count"] == 3:
            raise CollectorRateLimitError("daily quota exhausted", 60)
        return pd.DataFrame([{"title": request["start_date"], "src": "新浪财经"}])

    collector = FakeCollector(responder)
    with pytest.raises(CollectorRateLimitError):
        collect_major_news_window(
            collector,
            {"start_date": "20260918", "end_date": "20260918", "src": "新浪财经"},
            fields="title,content,pub_time,src",
            checkpoints=checkpoints,
        )

    first_attempt_calls = calls["count"]
    evidence = collect_major_news_window(
        collector,
        {"start_date": "20260918", "end_date": "20260918", "src": "新浪财经"},
        fields="title,content,pub_time,src",
        checkpoints=checkpoints,
    )

    assert first_attempt_calls == 3
    assert calls["count"] == 4
    assert evidence["resumed_splits"] == 1
    assert evidence["resumed_verified_windows"] == 1
    assert evidence["rows_fetched"] == 2
    assert evidence["rows_stored"] == 1
    assert evidence["rows_stored_previously"] == 1
    assert evidence["verified"] is True


def test_major_news_rejects_an_ignored_source_filter():
    collector = FakeCollector(
        lambda _request: pd.DataFrame([{"title": "x", "src": "其他来源"}])
    )

    with pytest.raises(IncompleteCollectionError, match="source filter was ignored"):
        collect_major_news_window(
            collector,
            {"start_date": "20260918", "end_date": "20260918", "src": "新浪财经"},
            fields="title,content,pub_time,src",
        )


def test_major_news_requires_a_closed_time_range():
    collector = FakeCollector(lambda _request: pd.DataFrame())

    with pytest.raises(ValueError, match="both start_date and end_date"):
        collect_major_news_window(
            collector,
            {"start_date": "20260918"},
            fields="title,content,pub_time,src",
        )


def test_major_news_classifies_daily_provider_quota_as_retryable():
    collector = FakeCollector(
        lambda _request: (_ for _ in ()).throw(
            Exception("频率超限(40次/天)")
        )
    )

    with pytest.raises(CollectorRateLimitError) as raised:
        collect_major_news_window(
            collector,
            {
                "src": "新浪财经",
                "start_date": "20260918",
                "end_date": "20260918",
            },
            fields="title,content,pub_time,src",
        )

    assert raised.value.retry_after_seconds >= 60
