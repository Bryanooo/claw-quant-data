"""限售股解禁采集器（share_float）。

Most dates are safely exhausted by ordinary offset pagination.  A few IPO
unlock dates contain more than Tushare's hard 100,000-offset ceiling because
one company can publish thousands of holder rows.  Those dates are completed
inside the same acquisition node by a frozen, point-in-time stock universe;
they are not split into scheduler-visible child tasks.
"""

from datetime import datetime
import json

from collectors.base import (
    BaseCollector,
    CollectorError,
    PartialCollectionError,
    get_db_conn,
)
from collectors.contracts import CollectorResult


class ShareFloatCollector(BaseCollector):
    API_NAME = "share_float"
    table_name = "share_float"
    # The same release lot can be announced more than once.  ``ann_date`` is
    # part of the upstream row identity: on 2026-09-07, omitting it collapsed
    # 22,248 distinct rows into 13,275 keys.
    pk_columns = [
        "ts_code",
        "ann_date",
        "float_date",
        "holder_name",
        "share_type",
    ]

    _OFFSET_CEILING = 100_000

    def _stored_partition_rows(self, compact_date: str) -> int:
        connection = get_db_conn()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT count(*) FROM share_float WHERE float_date=%s::DATE",
                    (datetime.strptime(compact_date, "%Y%m%d").date(),),
                )
                return int(cursor.fetchone()[0])
        finally:
            connection.close()

    def _stock_universe(self, compact_date: str) -> list[str]:
        connection = get_db_conn()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT ts_code FROM stock_basic
                    WHERE ts_code IS NOT NULL
                      AND (NULLIF(list_date, '') IS NULL OR list_date <= %s)
                      AND (NULLIF(delist_date, '') IS NULL OR delist_date >= %s)
                    ORDER BY ts_code
                    """,
                    (compact_date, compact_date),
                )
                return [str(row[0]) for row in cursor.fetchall()]
        finally:
            connection.close()

    def _completed_stock_codes(
        self, compact_date: str, *, page_size: int
    ) -> set[str]:
        """Return only entity scopes with a continuous exhausted page chain."""
        connection = get_db_conn()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT request_params->>'ts_code' AS ts_code,
                           COALESCE((request_params->>'offset')::INTEGER,0) AS offset,
                           COALESCE((request_params->>'limit')::INTEGER,%s) AS page_limit,
                           row_count
                    FROM tushare_raw_request
                    WHERE api_name='share_float'
                      AND status IN ('success','empty')
                      AND request_params @> %s::jsonb
                      AND request_params ? 'ts_code'
                    ORDER BY request_id
                    """,
                    (
                        page_size,
                        json.dumps({
                            "start_date": compact_date,
                            "end_date": compact_date,
                        }),
                    ),
                )
                pages: dict[str, dict[int, tuple[int, int]]] = {}
                for ts_code, offset, limit, row_count in cursor.fetchall():
                    pages.setdefault(str(ts_code), {})[int(offset)] = (
                        int(limit), int(row_count)
                    )
        finally:
            connection.close()

        completed: set[str] = set()
        for ts_code, offsets in pages.items():
            terminal_offsets = [
                offset
                for offset, (limit, count) in offsets.items()
                if count < limit
            ]
            for terminal in sorted(terminal_offsets, reverse=True):
                expected = set(range(0, terminal + page_size, page_size))
                if expected <= offsets.keys():
                    completed.add(ts_code)
                    break
        return completed

    @staticmethod
    def _is_offset_ceiling(error: Exception) -> bool:
        message = str(error).lower()
        return (
            "offset" in message and "100000" in message
        ) or "reached max_pages" in message

    def _run_stock_partitioned(
        self,
        *,
        page_size: int,
        max_pages: int,
        skip_store: bool,
        compact_date: str,
        fallback_reason: str,
        **params,
    ) -> CollectorResult:
        universe = self._stock_universe(compact_date)
        if not universe:
            raise CollectorError(
                f"share_float cannot freeze stock universe for {compact_date}"
            )
        resumed = self._completed_stock_codes(compact_date, page_size=page_size)
        fetched = stored = requests = 0
        completed = sum(code in resumed for code in universe)
        empty = 0
        raw_request_ids: list[int] = []
        logical_request_hashes: set[str] = set()
        for ts_code in universe:
            if ts_code in resumed:
                continue
            result = BaseCollector.run_offset_paginated(
                self,
                page_size=page_size,
                max_pages=max_pages,
                skip_store=skip_store,
                **params,
                ts_code=ts_code,
            )
            fetched += result.fetched_rows
            stored += result.stored_rows
            requests += result.request_count
            completed += 1
            empty += int(result.fetched_rows == 0)
            raw = result.evidence.get("raw_archive", {})
            raw_request_ids.extend(raw.get("request_ids", ()))
            logical_request_hashes.update(raw.get("logical_request_hashes", ()))

        spec = self.spec()
        return CollectorResult(
            collector_name=spec.qualified_name,
            collector_version=spec.version,
            api_name=spec.api_name,
            table_name=spec.table_name,
            fetched_rows=fetched,
            stored_rows=stored,
            request_count=requests,
            partitions=(compact_date,),
            empty_reason="upstream_returned_no_rows" if fetched == 0 else None,
            warnings=(
                "market-wide offset ceiling reached; completed by point-in-time "
                "stock fan-out inside acquire node",
            ),
            evidence={
                "verified": True,
                "verification_type": "stock_fanout_offset_exhaustion",
                "mode": "stock_fanout_offset",
                "fallback_reason": fallback_reason,
                "partition_date": compact_date,
                "universe_source": "stock_basic_as_of_date",
                "universe_total": len(universe),
                "entities_completed": completed,
                "entities_resumed": len(resumed & set(universe)),
                "entities_empty": empty,
                "rows_fetched": fetched,
                "rows_stored": stored,
                "exhausted": completed == len(universe),
                "raw_archive": {
                    "request_ids": raw_request_ids,
                    "logical_request_hashes": sorted(logical_request_hashes),
                },
            },
        )

    def run_offset_paginated(
        self,
        *,
        page_size: int = 1000,
        max_pages: int = 100,
        skip_store: bool = False,
        **params,
    ) -> CollectorResult:
        start = params.get("start_date")
        end = params.get("end_date")
        exact_date = str(start) if start and start == end else None
        if exact_date and self._stored_partition_rows(exact_date) >= self._OFFSET_CEILING:
            return self._run_stock_partitioned(
                page_size=page_size,
                max_pages=max_pages,
                skip_store=skip_store,
                compact_date=exact_date,
                fallback_reason="existing_partition_reached_provider_offset_ceiling",
                **params,
            )
        try:
            return BaseCollector.run_offset_paginated(
                self,
                page_size=page_size,
                max_pages=max_pages,
                skip_store=skip_store,
                **params,
            )
        except (CollectorError, PartialCollectionError) as error:
            if not exact_date or not self._is_offset_ceiling(error):
                raise
            return self._run_stock_partitioned(
                page_size=page_size,
                max_pages=max_pages,
                skip_store=skip_store,
                compact_date=exact_date,
                fallback_reason=str(error),
                **params,
            )
