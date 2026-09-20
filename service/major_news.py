"""Complete, source-aware collection for the Tushare ``major_news`` API."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Any, Iterable, Protocol

from collectors.base import classify_tushare_error
from collectors.tushare_raw import IncompleteCollectionError
from service.db import get_conn


MAJOR_NEWS_HISTORY_START = date(2018, 1, 1)
MAJOR_NEWS_ROW_LIMIT = 400
MAJOR_NEWS_SOURCES = (
    "新华网",
    "凤凰财经",
    "同花顺",
    "新浪财经",
    "华尔街见闻",
    "中证网",
    "财新网",
    "第一财经",
    "财联社",
)


class MajorNewsCheckpointStore(Protocol):
    """Durable proof for an adaptively partitioned source/time window."""

    def get(self, source: str, start: datetime, end: datetime) -> dict[str, Any] | None: ...

    def mark_split(self, source: str, start: datetime, end: datetime) -> None: ...

    def mark_complete(
        self,
        source: str,
        start: datetime,
        end: datetime,
        *,
        rows_fetched: int,
        rows_stored: int,
    ) -> None: ...


class MajorNewsCheckpointRepository:
    """PostgreSQL-backed checkpoint store.

    A completed leaf is immutable proof that the upstream returned fewer than
    its documented row cap for that exact source/time scope. Split nodes are
    stored as well, so a daily quota deferral resumes at unfinished children
    instead of repeating the whole year or month.
    """

    def __init__(self, connection_factory=get_conn):
        self._connection_factory = connection_factory

    def get(self, source: str, start: datetime, end: datetime) -> dict[str, Any] | None:
        connection = self._connection_factory()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT status, rows_fetched, rows_stored
                    FROM sys_major_news_window_checkpoint
                    WHERE source=%s AND window_start=%s AND window_end=%s
                    """,
                    (source, start, end),
                )
                row = cursor.fetchone()
                if not row:
                    return None
                return {
                    "status": row[0],
                    "rows_fetched": int(row[1] or 0),
                    "rows_stored": int(row[2] or 0),
                }
        finally:
            connection.close()

    def mark_split(self, source: str, start: datetime, end: datetime) -> None:
        self._upsert(source, start, end, status="split")

    def mark_complete(
        self,
        source: str,
        start: datetime,
        end: datetime,
        *,
        rows_fetched: int,
        rows_stored: int,
    ) -> None:
        self._upsert(
            source,
            start,
            end,
            status="complete",
            rows_fetched=rows_fetched,
            rows_stored=rows_stored,
        )

    def _upsert(
        self,
        source: str,
        start: datetime,
        end: datetime,
        *,
        status: str,
        rows_fetched: int = 0,
        rows_stored: int = 0,
    ) -> None:
        connection = self._connection_factory()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO sys_major_news_window_checkpoint(
                        source, window_start, window_end, status,
                        rows_fetched, rows_stored, updated_at
                    ) VALUES (%s,%s,%s,%s,%s,%s,NOW())
                    ON CONFLICT (source, window_start, window_end) DO UPDATE
                    SET status=EXCLUDED.status,
                        rows_fetched=EXCLUDED.rows_fetched,
                        rows_stored=EXCLUDED.rows_stored,
                        updated_at=NOW()
                    """,
                    (source, start, end, status, rows_fetched, rows_stored),
                )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()


def _parse_boundary(value: Any, *, end: bool) -> datetime:
    text = str(value or "").strip()
    if not text:
        raise ValueError("major_news requires both start_date and end_date")
    if len(text) == 8 and text.isdigit():
        parsed = datetime.strptime(text, "%Y%m%d").date()
        return datetime.combine(parsed, time.max.replace(microsecond=0) if end else time.min)
    if len(text) == 10 and text[4] == "-":
        parsed = date.fromisoformat(text)
        return datetime.combine(parsed, time.max.replace(microsecond=0) if end else time.min)
    try:
        return datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(
            "major_news dates must use YYYYMMDD, YYYY-MM-DD, or ISO date-time"
        ) from exc


def _format_boundary(value: datetime) -> str:
    return value.strftime("%Y-%m-%d %H:%M:%S")


def collect_major_news_window(
    collector,
    parameters: dict[str, Any],
    *,
    fields: str,
    sources: Iterable[str] = MAJOR_NEWS_SOURCES,
    checkpoints: MajorNewsCheckpointStore | None = None,
) -> dict[str, Any]:
    """Collect every requested source and split capped time ranges recursively.

    ``major_news`` has no offset contract.  The only reliable completeness
    proof is therefore a bounded source/time request returning fewer than the
    documented 400-row limit.  A capped response is never accepted; its time
    range is bisected until both children are demonstrably exhausted.
    """

    request = dict(parameters)
    start = _parse_boundary(request.pop("start_date", None), end=False)
    end = _parse_boundary(request.pop("end_date", None), end=True)
    if start > end:
        raise ValueError("major_news start_date must not be later than end_date")

    explicit_source = request.pop("src", None)
    selected_sources = (explicit_source,) if explicit_source else tuple(sources)
    if not selected_sources:
        raise ValueError("major_news requires at least one news source")

    fetched_total = 0
    stored_total = 0
    split_count = 0
    resumed_splits = 0
    resumed_leaves = 0
    resumed_rows_fetched = 0
    resumed_rows_stored = 0
    source_results: list[dict[str, Any]] = []

    for source in selected_sources:
        source_fetched = 0
        source_stored = 0
        source_resumed_fetched = 0
        source_resumed_stored = 0
        leaf_windows = 0
        stack = [(start, end)]
        while stack:
            window_start, window_end = stack.pop()
            checkpoint = (
                checkpoints.get(source, window_start, window_end)
                if checkpoints is not None
                else None
            )
            if checkpoint and checkpoint["status"] == "complete":
                resumed_leaves += 1
                checkpoint_fetched = int(checkpoint.get("rows_fetched") or 0)
                checkpoint_stored = int(checkpoint.get("rows_stored") or 0)
                resumed_rows_fetched += checkpoint_fetched
                resumed_rows_stored += checkpoint_stored
                source_resumed_fetched += checkpoint_fetched
                source_resumed_stored += checkpoint_stored
                leaf_windows += 1
                continue
            if checkpoint and checkpoint["status"] == "split":
                midpoint, right_start = _split_window(window_start, window_end)
                stack.append((right_start, window_end))
                stack.append((window_start, midpoint))
                resumed_splits += 1
                continue
            scoped = {
                **request,
                "src": source,
                "start_date": _format_boundary(window_start),
                "end_date": _format_boundary(window_end),
                "fields": fields,
            }
            try:
                frame = collector.fetch(**scoped)
            except Exception as error:
                classified = classify_tushare_error(error)
                if classified is not None:
                    raise classified from error
                raise
            fetched = 0 if frame is None else len(frame)
            if fetched >= MAJOR_NEWS_ROW_LIMIT:
                if window_start >= window_end:
                    raise IncompleteCollectionError(
                        f"major_news source={source} still returned the {MAJOR_NEWS_ROW_LIMIT}-row "
                        "cap for a one-second partition"
                    )
                midpoint, right_start = _split_window(window_start, window_end)
                if checkpoints is not None:
                    checkpoints.mark_split(source, window_start, window_end)
                stack.append((right_start, window_end))
                stack.append((window_start, midpoint))
                split_count += 1
                continue

            if fetched and "src" in frame.columns:
                returned_sources = {
                    str(item) for item in frame["src"].dropna().unique().tolist()
                }
                if returned_sources - {source}:
                    raise IncompleteCollectionError(
                        f"major_news source filter was ignored: requested={source}, "
                        f"returned={sorted(returned_sources)}"
                    )
            stored = collector.store(frame) if fetched else 0
            if checkpoints is not None:
                checkpoints.mark_complete(
                    source,
                    window_start,
                    window_end,
                    rows_fetched=fetched,
                    rows_stored=stored,
                )
            fetched_total += fetched
            stored_total += stored
            source_fetched += fetched
            source_stored += stored
            leaf_windows += 1

        source_results.append(
            {
                "source": source,
                "rows_fetched": source_fetched,
                "rows_stored": source_stored,
                "checkpoint_rows_fetched": source_resumed_fetched,
                "checkpoint_rows_stored": source_resumed_stored,
                "verified_windows": leaf_windows,
            }
        )

    return {
        "verified": True,
        "verification_type": "source_time_partition_exhaustion",
        "documented_row_limit": MAJOR_NEWS_ROW_LIMIT,
        "requested_start": _format_boundary(start),
        "requested_end": _format_boundary(end),
        "sources": list(selected_sources),
        "source_results": source_results,
        "adaptive_splits": split_count,
        "resumed_splits": resumed_splits,
        "resumed_verified_windows": resumed_leaves,
        "rows_fetched": fetched_total + resumed_rows_fetched,
        "rows_stored": stored_total,
        "rows_stored_previously": resumed_rows_stored,
        "normalization": dict(collector.normalization_evidence),
    }


def _split_window(start: datetime, end: datetime) -> tuple[datetime, datetime]:
    seconds = int((end - start).total_seconds())
    midpoint = start + timedelta(seconds=max(seconds // 2, 0))
    if midpoint >= end:
        midpoint = start
    return midpoint, midpoint + timedelta(seconds=1)
