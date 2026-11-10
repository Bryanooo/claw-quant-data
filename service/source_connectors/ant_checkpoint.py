"""Durable successful scheduled subrequests; never a quota bypass or freshness claim."""

import hashlib, json
from psycopg2.extras import Json
from service.db import get_conn, query


class ScheduledCheckpoint:
    def key(self, route, period, request):
        return hashlib.sha256(
            json.dumps([route, period, request], sort_keys=True).encode()
        ).hexdigest()

    def get(self, route, period, request):
        rows = query(
            "SELECT result FROM ant_scheduled_checkpoint WHERE request_hash=%s "
            "AND observed_at>now()-interval '7 days'",
            (self.key(route, period, request),),
        )
        return rows[0]["result"] if rows else None

    def put(self, route, period, request, result):
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute(
                "INSERT INTO ant_scheduled_checkpoint(request_hash,route,period_key,result) "
                "VALUES(%s,%s,%s,%s) ON CONFLICT(request_hash) DO NOTHING",
                (self.key(route, period, request), route, period, Json(result)),
            )
            cur.execute(
                "DELETE FROM ant_scheduled_checkpoint WHERE observed_at<now()-interval '14 days'"
            )


def resumable_transport(spec, transport, checkpoint, period):
    def send(payload):
        original = payload["requests"]
        results = [checkpoint.get(spec.route, period, r) for r in original]
        missing = [i for i, r in enumerate(results) if r is None]
        for offset in range(0, len(missing), 10):
            batch = missing[offset : offset + 10]
            response = transport({**payload, "requests": [original[i] for i in batch]})
            fresh = response.get("results")
            if (
                response.get("status") != "SUCCESS"
                or not isinstance(fresh, list)
                or len(fresh) != len(batch)
            ):
                raise RuntimeError("Incomplete scheduled checkpoint response")
            for i, result in zip(batch, fresh):
                if (
                    not isinstance(result, dict)
                    or result.get("status", "SUCCESS") != "SUCCESS"
                ):
                    raise RuntimeError("Failed scheduled subrequest cannot be cached")
                # Decode and persist observed rows before caching transport success.
                # An interrupted later batch leaves usable observations, never ready certification.
                from service.source_connectors.financial_data_protocol import (
                    tabular_rows,
                )
                from service.source_connectors.ant_scheduled import (
                    _row_from_record,
                    store_rows,
                )
                from datetime import datetime
                from zoneinfo import ZoneInfo

                records = tabular_rows(
                    {"status": "SUCCESS", "results": [result]}, route=spec.route
                )
                allowed = set(original[i].get("params", {}).get("symbols", []))
                if allowed and any(r.get("symbol") not in allowed for r in records):
                    raise ValueError("Scheduled response contains unrequested symbols")
                if records:
                    day = datetime.now(ZoneInfo("Asia/Shanghai")).date()
                    store_rows(spec, [_row_from_record(spec, r, day) for r in records])
                checkpoint.put(spec.route, period, original[i], result)
                results[i] = result
        return {"status": "SUCCESS", "results": results}

    return send
