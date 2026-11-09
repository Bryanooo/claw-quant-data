"""Recover uninstantiated, date-addressable daily Tushare deliveries after an outage.

Dry run by default. Existing executions (including attention) require separate
diagnosis; never turn an undated provider snapshot into a historical observation.
"""

import argparse
from collections import Counter
from datetime import date, time, timedelta
import json
from pathlib import Path
import sys
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from service.clock import business_now
from service.db import query
from service.orchestration_v2.catalog import acquisition_task_blueprints
from service.orchestration_v2.contracts import (
    NEXT_MORNING_TASKS,
    US_COMPLETED_SESSION_TASKS,
    TaskDefinitionDocument,
)
from service.orchestration_v2.gap_repair import create_repair_executions
from service.orchestration_v2.repair_planning import RepairInstanceProposal
from service.orchestration_v2.recovery_policy import DEFERRED_RESEARCH_DATASETS
from service.orchestration_v2.repository import OrchestrationV2Repository
from service.orchestration_v2.runtime import OrchestrationV2Runtime


def dated_request(spec, day):
    p = spec.parameters.get("parameters", {})
    stamp = day.strftime("%Y%m%d")
    if "start_date" in p or "end_date" in p:
        return p.get("start_date") == p.get("end_date") and p.get("end_date") in (
            stamp,
            str(day),
        )
    return any(
        p.get(k) == stamp
        for k in (
            "trade_date",
            "ann_date",
            "nav_date",
            "cal_date",
            "date",
            "curve_date",
            "surv_date",
        )
    )


def recover(start, end, apply=False):
    now = business_now()
    if not 0 <= (end - start).days <= 7 or end >= now.date():
        raise ValueError("recover at most eight calendar dates, strictly before today")
    r = OrchestrationV2Repository()
    runtime = OrchestrationV2Runtime(r)
    days = {
        x["cal_date"]
        for x in query(
            "SELECT cal_date FROM trade_cal WHERE exchange='SSE' AND is_open=1 AND cal_date BETWEEN %s AND %s",
            (start, end),
        )
    }
    us_days = {
        x["cal_date"]
        for x in query(
            "SELECT DISTINCT cal_date FROM tushare_norm_us_tradecal WHERE is_open=1 AND cal_date BETWEEN %s AND %s",
            (start, end),
        )
    }
    existing = {
        (x["task_key"], x["observation_key"])
        for x in query(
            "SELECT DISTINCT task_key,observation_key FROM orchestration_v2.task_execution WHERE observation_start BETWEEN %s AND %s AND status NOT IN ('cancelled','superseded')",
            (start, end),
        )
    }
    ready = {
        (x["dataset_name"], x["observation_key"])
        for x in query(
            "SELECT dataset_name,observation_key FROM orchestration_v2.dataset_state WHERE ready AND scope='{}' AND observation_start BETWEEN %s AND %s",
            (start, end),
        )
    }
    candidates = []
    review = []
    counts = Counter()
    for task in acquisition_task_blueprints():
        k = task.task_key
        if task.cadence != "daily" or k in DEFERRED_RESEARCH_DATASETS:
            continue
        definition = r.get_active_definition(k)
        if not definition:
            continue
        doc = TaskDefinitionDocument.model_validate(definition["definition"])
        for d in sorted(us_days if k in US_COMPLETED_SESSION_TASKS else days):
            key = str(d)
            if (
                k in US_COMPLETED_SESSION_TASKS
                and d >= now.astimezone(ZoneInfo("America/New_York")).date()
            ):
                counts["us_session_not_closed_and_published"] += 1
                continue
            if (k, key) in existing or all(
                (n, key) in ready for n in task.output_datasets
            ):
                counts["already_tracked_or_certified"] += 1
                continue
            if (
                k in NEXT_MORNING_TASKS
                and d + timedelta(days=1) == now.date()
                and now.time() < time(9, 15)
            ):
                counts["not_due"] += 1
                continue
            explanation = None
            if not any(e.source_id in {"tushare", "chinabond"} for e in task.endpoints):
                explanation = "other_source_not_replayed"
            elif any(
                a.period_granularity not in ("day", "snapshot")
                for a in doc.validation_contract.dataset_audits
            ):
                explanation = "validated by a different logical period; do not create a daily repair"
            elif k == "share_float":
                explanation = "upstream rejects unqualified date window; needs announcement/security scope"
            elif k == "stock_basic":
                explanation = "current-only security master"
            else:
                try:
                    specs = runtime._plan_acquisition(
                        doc,
                        dict(
                            task_execution_id=0,
                            task_key=k,
                            purpose="repair",
                            observation_key=key,
                            observation_start=d,
                            observation_end=d,
                            frozen_scope={},
                        ),
                    )
                    if not specs or not all(dated_request(s, d) for s in specs):
                        explanation = "no exact-date historical request"
                except (ValueError, RuntimeError, KeyError) as exc:
                    explanation = type(exc).__name__ + ": " + str(exc)[:120]
            if explanation:
                review.append((key, k, explanation))
                continue
            candidates.append(
                RepairInstanceProposal(
                    k,
                    key,
                    d,
                    d,
                    key,
                    tuple(task.output_datasets),
                    ("missed_daily_delivery",),
                )
            )
    out = dict(
        candidates=[(p.observation_key, p.task_key) for p in candidates],
        review=review,
        counts=dict(counts),
    )
    if apply:
        out["dispatch"] = create_repair_executions(r, proposals=candidates)
    return out


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("start", type=date.fromisoformat)
    p.add_argument("end", type=date.fromisoformat)
    p.add_argument("--apply", action="store_true")
    a = p.parse_args()
    print(json.dumps(recover(a.start, a.end, a.apply), ensure_ascii=False))
