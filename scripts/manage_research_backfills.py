#!/usr/bin/env python3
"""Queue and audit staged backfills required by research services.

The command is intentionally stage-gated. ``--group next`` only advances after
the preceding group has no active or failed durable jobs/campaigns.
"""

from __future__ import annotations

import argparse
from datetime import date, timedelta
import hashlib
import json
from pathlib import Path
import sys
from typing import Iterable

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from service.collection_jobs.fanout_campaigns import FanoutCampaignService
from service.collection_jobs.models import BatchChildSpec
from service.collection_jobs.registry import TASKS
from service.collection_jobs.repository import JobRepository
from service.collection_jobs.resolution import unresolved_failure_predicate
from service.clock import business_now
from service.db import query
from service.history_baselines import calendar_windows
from service.major_news import MAJOR_NEWS_HISTORY_START, MAJOR_NEWS_SOURCES


PREFIX = "research-backfill-v1"
NEWS_PREFIX = "research-backfill-v2"
GROUPS = ("news", "analyst", "ownership", "shareholder-return", "chips", "intraday")


def _digest(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()[:24]


def _quarter_ends(start: date, end: date) -> list[date]:
    values = []
    for year in range(start.year, end.year + 1):
        for month, day in ((3, 31), (6, 30), (9, 30), (12, 31)):
            value = date(year, month, day)
            if start <= value <= end:
                values.append(value)
    return values


def _daily_windows(start: date, end: date) -> Iterable[tuple[date, date]]:
    cursor = start
    while cursor <= end:
        yield cursor, cursor
        cursor += timedelta(days=1)


def _yearly_windows(start: date, end: date) -> Iterable[tuple[date, date]]:
    cursor = start
    while cursor <= end:
        window_end = min(date(cursor.year, 12, 31), end)
        yield cursor, window_end
        cursor = window_end + timedelta(days=1)


def queue_news(start: date, end: date) -> dict[str, int]:
    """Queue one resumable source leaf per year.

    Each leaf adaptively bisects capped ranges and persists every split and
    verified child window. A daily quota deferral therefore resumes at the
    first unfinished child. This reduces the base plan from 28k source/day
    jobs to roughly 80 source/year jobs without weakening completeness proof.
    """
    actual_start = max(start, MAJOR_NEWS_HISTORY_START)
    created = 0
    batches = 0
    for window_start, window_end in _yearly_windows(actual_start, end):
        children = []
        for source in MAJOR_NEWS_SOURCES:
            parameters = {
                "src": source,
                "start_date": window_start.strftime("%Y%m%d"),
                "end_date": window_end.strftime("%Y%m%d"),
            }
            task_parameters = {
                "api_name": "major_news",
                "parameters": parameters,
                "complete": True,
                "resume": True,
            }
            handler = TASKS.handler_metadata("tushare_interface", task_parameters)
            children.append(
                BatchChildSpec(
                    task_name="tushare_interface",
                    parameters=task_parameters,
                    idempotency_key=(
                        f"{NEWS_PREFIX}:news:job:major_news:{_digest(parameters)}"
                    ),
                    api_name="major_news",
                    cadence="backfill",
                    period_key=f"news:{window_start:%Y}:{source}",
                    expected_for=window_end,
                    handler=handler,
                    priority=30,
                    resource_class="news-backfill",
                )
            )
        batch_created = _create_news_batch(children, window_start, window_end)
        if batch_created:
            batches += 1
            created += len(children)
    return {
        "jobs_created": created,
        "campaigns_created": 0,
        "batches_created": batches,
    }


def _create_news_batch(
    children: list[BatchChildSpec], window_start: date, window_end: date
) -> bool:
    _, created = JobRepository().create_batch(
        {
            "group": "news",
            "api_name": "major_news",
            "start_date": window_start.isoformat(),
            "end_date": window_end.isoformat(),
            "partition": "source_adaptive_window",
        },
        children,
        idempotency_key=(
            f"{NEWS_PREFIX}:news:batch:{window_start:%Y%m%d}:{window_end:%Y%m%d}"
        ),
        api_name="major_news",
        cadence="backfill",
        period_key=f"news:{window_start:%Y}",
        expected_for=window_end,
        completion_evidence={
            "partition": "source_adaptive_window",
            "leaf_count": len(children),
        },
        priority=30,
        resource_class="news-backfill",
    )
    return created


def supersede_legacy_news_plan() -> dict[str, int]:
    return JobRepository().supersede_plan(
        f"{PREFIX}:news:",
        reason=(
            "replaced by resumable source/year plan with durable adaptive-window "
            "checkpoints"
        ),
    )


def _create_job(
    group: str,
    api_name: str,
    parameters: dict,
    *,
    period_key: str,
    expected_for: date,
    page_size: int | None = None,
    max_pages: int | None = None,
    priority: int = 20,
    resource_class: str = "backfill",
) -> bool:
    task_parameters = {
        "api_name": api_name,
        "parameters": parameters,
        "complete": True,
        "resume": True,
    }
    if page_size:
        task_parameters["page_size"] = page_size
    if max_pages:
        task_parameters["max_pages"] = max_pages
    handler = TASKS.handler_metadata("tushare_interface", task_parameters)
    _, created = JobRepository().create(
        "tushare_interface",
        task_parameters,
        max_attempts=3,
        idempotency_key=f"{PREFIX}:{group}:job:{api_name}:{_digest(parameters)}",
        api_name=api_name,
        cadence="backfill",
        period_key=period_key,
        expected_for=expected_for,
        handler_type=handler.handler_type,
        handler_key=handler.handler_key,
        handler_version=handler.handler_version,
        code_revision=handler.code_revision,
        priority=priority,
        resource_class=resource_class,
    )
    return created


def _create_campaign(
    group: str,
    api_name: str,
    request: dict,
    *,
    period_key: str,
    expected_for: date,
) -> bool:
    _, created = FanoutCampaignService().submit(
        request,
        idempotency_key=f"{PREFIX}:{group}:fanout:{api_name}:{_digest(request)}",
        cadence="backfill",
        period_key=period_key,
        expected_for=expected_for,
        reuse_scope=True,
    )
    return created


def queue_analyst(start: date, end: date) -> dict[str, int]:
    actual_start = max(start, date(2010, 1, 1))
    created = 0
    for window_start, window_end in _daily_windows(actual_start, end):
        created += _create_job(
            "analyst", "report_rc",
            {
                "start_date": window_start.strftime("%Y%m%d"),
                "end_date": window_end.strftime("%Y%m%d"),
            },
            period_key=f"report_rc:{window_start}:{window_end}",
            expected_for=window_end,
            page_size=5000,
            max_pages=100,
        )
    return {"jobs_created": created, "campaigns_created": 0}


def queue_ownership(start: date, end: date) -> dict[str, int]:
    jobs = 0
    for api_name, reliable_start in (
        ("stk_holdertrade", date(2010, 1, 1)),
        ("stk_holdernumber", date(2010, 1, 1)),
        ("hk_hold", date(2017, 3, 17)),
    ):
        for window_start, window_end in calendar_windows(
            max(start, reliable_start), end, monthly=True
        ):
            jobs += _create_job(
                "ownership", api_name,
                {
                    "start_date": window_start.strftime("%Y%m%d"),
                    "end_date": window_end.strftime("%Y%m%d"),
                },
                period_key=f"{api_name}:{window_start:%Y-%m}",
                expected_for=window_end,
                page_size=5000,
                max_pages=200,
            )

    periods = _quarter_ends(max(start, date(2010, 1, 1)), end)
    for period in periods:
        compact = period.strftime("%Y%m%d")
        jobs += _create_job(
            "ownership", "fund_portfolio", {"period": compact},
            period_key=f"fund_portfolio:{compact}", expected_for=period,
            page_size=5000, max_pages=500,
        )

    campaigns = 0
    holder_start = max(start, date(end.year - 5, 1, 1))
    for period in _quarter_ends(holder_start, end):
        for api_name in ("top10_holders", "top10_floatholders"):
            campaigns += _create_campaign(
                "ownership", api_name,
                {"api_name": api_name, "period": period, "page_size": 200},
                period_key=f"{api_name}:{period:%Y%m%d}", expected_for=period,
            )
    return {"jobs_created": jobs, "campaigns_created": campaigns}


def queue_shareholder_return(start: date, end: date) -> dict[str, int]:
    jobs = 0
    for api_name, reliable_start in (
        ("repurchase", date(2015, 1, 1)),
        ("share_float", date(2005, 1, 1)),
    ):
        for window_start, window_end in calendar_windows(
            max(start, reliable_start), end, monthly=True
        ):
            jobs += _create_job(
                "shareholder-return", api_name,
                {
                    "start_date": window_start.strftime("%Y%m%d"),
                    "end_date": window_end.strftime("%Y%m%d"),
                },
                period_key=f"{api_name}:{window_start:%Y-%m}",
                expected_for=window_end,
                page_size=5000,
                max_pages=200,
            )
    campaign = _create_campaign(
        "shareholder-return", "dividend",
        {"api_name": "dividend", "page_size": 200},
        period_key="dividend:all-listed-history", expected_for=end,
    )
    return {"jobs_created": jobs, "campaigns_created": int(campaign)}


def queue_chips(start: date, end: date, *, allow_high_cardinality: bool) -> dict[str, int]:
    if not allow_high_cardinality:
        raise SystemExit(
            "chips fan-out is high-cardinality; rerun with --allow-high-cardinality "
            "after earlier groups are complete"
        )
    campaigns = 0
    actual_start = max(start, date(2018, 1, 1))
    for window_start, window_end in calendar_windows(actual_start, end, monthly=True):
        for api_name in ("cyq_chips", "cyq_perf"):
            campaigns += _create_campaign(
                "chips", api_name,
                {
                    "api_name": api_name,
                    "start_date": window_start,
                    "end_date": window_end,
                    "page_size": 200,
                },
                period_key=f"{api_name}:{window_start:%Y-%m}", expected_for=window_end,
            )
    return {"jobs_created": 0, "campaigns_created": campaigns}


def queue_intraday(
    symbols: list[str], *, day: date, frequency: str
) -> dict[str, int]:
    if not symbols or len(symbols) > 2:
        raise SystemExit("intraday requires one or two --symbol values due to the 2 calls/day limit")
    jobs = 0
    for symbol in symbols:
        jobs += _create_job(
            "intraday", "stk_mins",
            {
                "ts_code": symbol.upper(),
                "freq": frequency,
                "start_date": f"{day.isoformat()} 09:00:00",
                "end_date": f"{day.isoformat()} 16:00:00",
            },
            period_key=f"stk_mins:{symbol.upper()}:{frequency}:{day}",
            expected_for=day,
        )
    return {"jobs_created": jobs, "campaigns_created": 0}


def group_status(group: str) -> dict[str, object]:
    prefix = NEWS_PREFIX if group == "news" else PREFIX
    unresolved_jobs = unresolved_failure_predicate("job")
    job_rows = query(
        """
        SELECT status, completion_status, count(*) AS count
        FROM sys_collection_job
        WHERE idempotency_key LIKE %s
        GROUP BY status, completion_status
        ORDER BY status, completion_status
        """,
        (f"{prefix}:{group}:job:%",),
    )
    campaign_rows = query(
        """
        SELECT status, completion_status, count(*) AS count
        FROM sys_collection_fanout_campaign
        WHERE idempotency_key LIKE %s
        GROUP BY status, completion_status
        ORDER BY status, completion_status
        """,
        (f"{prefix}:{group}:fanout:%",),
    )
    unresolved_row = query(
        f"""
        SELECT count(*) AS count
        FROM sys_collection_job AS job
        WHERE idempotency_key LIKE %s AND {unresolved_jobs}
        """,
        (f"{prefix}:{group}:job:%",),
    )
    active_states = {"queued", "running"}
    failed_jobs = int(unresolved_row[0]["count"] or 0)
    active_jobs = sum(
        int(row["count"])
        for row in job_rows
        if row["status"] in active_states
    )
    bad_campaigns = sum(
        int(row["count"])
        for row in campaign_rows
        if row["status"] in {"running", "paused", "attention"}
        or (
            row["completion_status"] == "incomplete"
            and row["status"] != "superseded"
        )
    )
    total = sum(int(row["count"]) for row in job_rows + campaign_rows)
    return {
        "group": group,
        "total": total,
        "complete": total > 0 and not (active_jobs or failed_jobs or bad_campaigns),
        "active_jobs": active_jobs,
        "failed_jobs": failed_jobs,
        "bad_or_active_campaigns": bad_campaigns,
        "jobs": job_rows,
        "campaigns": campaign_rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--group", choices=(*GROUPS, "next"))
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--start-date", type=date.fromisoformat, default=date(2010, 1, 1))
    parser.add_argument(
        "--end-date",
        type=date.fromisoformat,
        default=business_now().date() - timedelta(days=1),
    )
    parser.add_argument("--allow-high-cardinality", action="store_true")
    parser.add_argument("--symbol", action="append", default=[])
    parser.add_argument("--frequency", choices=("1min", "5min", "15min", "30min", "60min"), default="5min")
    parser.add_argument("--day", type=date.fromisoformat)
    args = parser.parse_args()
    if args.start_date > args.end_date:
        parser.error("--start-date must not be later than --end-date")

    if args.status:
        print(json.dumps([group_status(group) for group in GROUPS], ensure_ascii=False, default=str, indent=2))
        return 0
    if not args.group:
        parser.error("--group is required unless --status is used")

    group = args.group
    if group == "next":
        group = GROUPS[0]
        for index, candidate in enumerate(GROUPS[:-1]):
            state = group_status(candidate)
            if not state["complete"]:
                group = candidate
                break
            group = GROUPS[index + 1]
        preceding = GROUPS[: GROUPS.index(group)]
        incomplete = [item for item in preceding if not group_status(item)["complete"]]
        if incomplete:
            raise SystemExit(f"cannot advance; incomplete groups: {', '.join(incomplete)}")

    if group == "news":
        replaced = supersede_legacy_news_plan()
        result = queue_news(args.start_date, args.end_date)
        result = {**replaced, **result}
    elif group == "analyst":
        result = queue_analyst(args.start_date, args.end_date)
    elif group == "ownership":
        result = queue_ownership(args.start_date, args.end_date)
    elif group == "shareholder-return":
        result = queue_shareholder_return(args.start_date, args.end_date)
    elif group == "chips":
        result = queue_chips(
            args.start_date, args.end_date,
            allow_high_cardinality=args.allow_high_cardinality,
        )
    else:
        result = queue_intraday(
            args.symbol,
            day=args.day or args.end_date,
            frequency=args.frequency,
        )
    print(json.dumps({"group": group, **result}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
