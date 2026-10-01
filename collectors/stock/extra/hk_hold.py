"""
沪深港股通持股明细采集器（hk_hold）
"""

from datetime import date, datetime, timedelta

from collectors.base import BaseCollector
from collectors.contracts import CollectorResult


_MAX_SAFE_WINDOW_DAYS = 7


def _scope_date(value) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    return datetime.strptime(text, "%Y%m%d" if "-" not in text else "%Y-%m-%d").date()


class HkHoldCollector(BaseCollector):
    API_NAME = "hk_hold"
    table_name = "hk_hold"
    pk_columns = ["ts_code", "trade_date"]

    def run_offset_paginated(
        self,
        *,
        page_size: int = 1000,
        max_pages: int = 100,
        skip_store: bool = False,
        **params,
    ) -> CollectorResult:
        """Exhaust wide history scopes as bounded seven-day windows.

        Tushare rejects offsets above 100,000. A monthly ``hk_hold`` scope can
        legitimately cross that boundary, so retrying a legacy monthly job
        must not repeat the same unsafe request. Each bounded child scope is
        still independently proven by normal offset exhaustion.
        """
        raw_start = params.get("start_date")
        raw_end = params.get("end_date")
        if not raw_start or not raw_end:
            return super().run_offset_paginated(
                page_size=page_size,
                max_pages=max_pages,
                skip_store=skip_store,
                **params,
            )

        start = _scope_date(raw_start)
        end = _scope_date(raw_end)
        if end < start:
            raise ValueError("end_date must not be before start_date")
        if (end - start).days < _MAX_SAFE_WINDOW_DAYS:
            return super().run_offset_paginated(
                page_size=page_size,
                max_pages=max_pages,
                skip_store=skip_store,
                **params,
            )

        results: list[CollectorResult] = []
        cursor = start
        while cursor <= end:
            chunk_end = min(cursor + timedelta(days=_MAX_SAFE_WINDOW_DAYS - 1), end)
            chunk_params = {
                **params,
                "start_date": cursor.strftime("%Y%m%d"),
                "end_date": chunk_end.strftime("%Y%m%d"),
            }
            results.append(
                super().run_offset_paginated(
                    page_size=page_size,
                    max_pages=max_pages,
                    skip_store=skip_store,
                    **chunk_params,
                )
            )
            cursor = chunk_end + timedelta(days=1)

        spec = self.spec()
        fetched = sum(item.fetched_rows for item in results)
        stored = sum(item.stored_rows for item in results)
        return CollectorResult(
            collector_name=spec.qualified_name,
            collector_version=spec.version,
            api_name=spec.api_name,
            table_name=spec.table_name,
            fetched_rows=fetched,
            stored_rows=stored,
            request_count=sum(item.request_count for item in results),
            partitions=tuple(
                dict.fromkeys(
                    partition
                    for item in results
                    for partition in item.partitions
                )
            ),
            empty_reason="upstream_returned_no_rows" if fetched == 0 else None,
            warnings=tuple(
                dict.fromkeys(
                    warning
                    for item in results
                    for warning in item.warnings
                )
            ),
            evidence={
                "verified": all(
                    item.evidence.get("verified") is True for item in results
                ),
                "verification_type": "bounded_date_windows_with_offset_exhaustion",
                "mode": "bounded_offset",
                "requested_start": start.isoformat(),
                "requested_end": end.isoformat(),
                "max_window_days": _MAX_SAFE_WINDOW_DAYS,
                "rows_fetched": fetched,
                "rows_stored": stored,
                "chunks": [
                    {
                        "start_date": (
                            start + timedelta(days=index * _MAX_SAFE_WINDOW_DAYS)
                        ).isoformat(),
                        "end_date": min(
                            start + timedelta(
                                days=(index + 1) * _MAX_SAFE_WINDOW_DAYS - 1
                            ),
                            end,
                        ).isoformat(),
                        "rows_fetched": item.fetched_rows,
                        "rows_stored": item.stored_rows,
                        "evidence": dict(item.evidence),
                    }
                    for index, item in enumerate(results)
                ],
            },
        )
