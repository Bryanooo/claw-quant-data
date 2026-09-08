"""State-machine coordinator for installation-time initial collection."""

from __future__ import annotations

from datetime import date, datetime, timedelta
import hashlib
from typing import Any
from zoneinfo import ZoneInfo

from service.collection_jobs.registry import TASKS
from service.collection_jobs.repository import JobRepository
from service.collection_jobs.service import CollectionJobService
from service.collection_jobs.fanout_campaigns import FanoutCampaignService
from service.collection_jobs.models import (
    InvalidTaskParametersError,
    JobConflictError,
    JobNotFoundError,
)
from service.clock import business_now
from service.data_coverage.service import CoverageService
from service.initialization.repository import InitializationRepository
from service.history_baselines import (
    CATALOG_MONTHLY_WINDOW_HISTORY,
    CATALOG_WINDOW_HISTORY,
    LIBOR_CURRENCIES,
    INITIALIZATION_STRICT_COVERAGE_LOOKBACK_DAYS,
    INITIALIZATION_TRANSPORT_VERIFIED_DATASETS,
    FINANCIAL_ENTITY_REFERENCE_MAX_AGE_DAYS,
    catalog_history_partitions,
)
from service.config import (
    INITIALIZATION_AUTO_RECOVERY_COOLDOWN_SECONDS,
    INITIALIZATION_AUTO_RECOVERY_MAX_ROUNDS,
)


SHANGHAI = ZoneInfo("Asia/Shanghai")
PHASES = (
    "foundation",
    "core_history",
    "finance_history",
    "catalog_history",
    "latest_baseline",
    "fanout_baseline",
    "verification",
)
FULL_HISTORY_START = date(1990, 12, 19)
PROFILE_DAYS = {
    "quick": 30,
    "standard": 365,
    "research": 1095,
    "full": None,
}
PLANNING_BATCH_SIZE = 500
CORE_TASKS = ("stock_daily", "stock_daily_basic", "moneyflow", "stock_limit")
TRANSIENT_AUTO_RECOVERY_CATEGORIES = frozenset({"network", "timeout", "quota"})
FULL_HISTORY_DATASET_STARTS = {
    "stock_daily": FULL_HISTORY_START,
    "stock_daily_basic": FULL_HISTORY_START,
    # The upstream contract explicitly states that moneyflow begins in 2010.
    "moneyflow": date(2010, 1, 1),
    # Price limits existed earlier, but the Tushare ``stk_limit`` dataset does
    # not.  Live boundary probes with the production token return verified
    # empty responses through 2006 and a populated first trading day on
    # 2007-01-04.  Starting at the market-rule date (1996-12-16) made valid,
    # exhausted empty responses fail a full initialization forever.
    "stock_limit": date(2007, 1, 4),
    # First dated sample in the official KPL concept-constituent contract.
    "kpl_concept_cons": date(2024, 10, 14),
}
CORE_INTERFACE_HISTORY = ("index_daily", "kpl_concept_cons")
CORE_INTERFACE_PAGE_SIZES = {"index_daily": 5000, "kpl_concept_cons": 3000}
# KPL occasionally has no published concept constituents on an otherwise open
# SSE date.  An exhausted offset request is authoritative for that empty scope;
# other core datasets must still fail closed when an expected date is empty.
VERIFIED_EMPTY_CORE_INTERFACES = frozenset({"kpl_concept_cons"})
FINANCE_TASKS = (
    "income_period",
    "balancesheet_period",
    "cashflow_period",
    "financial_indicator_period",
)
AUXILIARY_FINANCE_INTERFACES = (
    "disclosure_date",
    "express",
    "forecast",
    "fina_mainbz",
)
VERIFICATION_DATASETS = (
    "stock_daily", "stock_daily_basic", "moneyflow", "stock_limit",
    "index_daily", "kpl_concept_cons", "income", "balancesheet", "cashflow",
    "financial_indicator",
)
FULL_FANOUT_BASELINES = (
    "cb_rate",
    "cb_rating",
    "ci_index_member",
    "fut_basic",
    "fut_index_daily",
    "index_member_all",
    "ths_member",
    "pledge_stat",
    # Parameterized interfaces that cannot be safely represented by one
    # market-wide request.  Full initialization freezes their local entity
    # universes and exhausts every page in the baseline scope.
    "top10_cb_holders",
    "cyq_chips",
    "cyq_perf",
    "fina_audit",
    "stk_rewards",
    "top10_floatholders",
    "top10_holders",
    "index_weight",
    "fut_weekly_monthly",
    "stk_week_month_adj",
)
FULL_INITIALIZATION_BASELINES = (
    *FULL_FANOUT_BASELINES,
    "fund_nav",
    "fund_portfolio",
)
_EMPTY_FANOUT_BASELINES = {
    "top10_cb_holders", "cyq_chips", "cyq_perf", "fina_audit",
    "stk_rewards", "top10_floatholders", "top10_holders", "index_weight",
    "fut_weekly_monthly",
    "stk_week_month_adj",
}


def _today() -> date:
    return datetime.now(SHANGHAI).date()


def _published_quarter_ends(start: date, end: date) -> list[date]:
    periods = []
    for year in range(start.year - 1, end.year + 1):
        candidates = (
            (date(year, 3, 31), date(year, 4, 30)),
            (date(year, 6, 30), date(year, 8, 31)),
            (date(year, 9, 30), date(year, 10, 31)),
            (date(year, 12, 31), date(year + 1, 4, 30)),
        )
        periods.extend(
            period
            for period, publication_deadline in candidates
            if start <= period <= end and publication_deadline <= end
        )
    return sorted(set(periods))


def _safe_key(value: str) -> str:
    if len(value) <= 128:
        return value
    return f"initialization-{hashlib.sha256(value.encode()).hexdigest()}"


class InitializationService:
    def __init__(
        self,
        repository: InitializationRepository | None = None,
        job_service: CollectionJobService | None = None,
        coverage_service: CoverageService | None = None,
        fanout_service: FanoutCampaignService | None = None,
    ):
        self._repository = repository or InitializationRepository()
        self._job_service = job_service or CollectionJobService(JobRepository(), TASKS)
        self._coverage_service = coverage_service or CoverageService()
        self._fanout_service = fanout_service or FanoutCampaignService()

    def overview(self) -> dict:
        runtime = self._repository.runtime_state()
        active = self._repository.active()
        latest = self._repository.latest()
        if active:
            active = self._decorate(active)
        if latest and active and (
            latest.get("initialization_id") == active.get("initialization_id")
        ):
            # Avoid loading the full trading calendar twice for the same active
            # campaign when computing its stable logical phase denominator.
            latest = dict(active)
        elif latest:
            latest = self._decorate(latest)
        return {
            "runtime": runtime,
            "active": active,
            "latest": latest,
            "profiles": self.profiles(),
        }

    @staticmethod
    def profiles() -> list[dict[str, Any]]:
        return [
            {
                "name": name,
                "history_days": days,
                "description": {
                    "quick": "最近 30 天，用于功能验证与轻量研究",
                    "standard": "最近 1 年，推荐的默认初始化范围",
                    "research": "最近 3 年，任务量和耗时显著增加",
                    "full": "全部可靠历史，按各数据集可用起点回填",
                }[name],
                **(
                    {"history_start": FULL_HISTORY_START.isoformat()}
                    if name == "full" else {}
                ),
            }
            for name, days in PROFILE_DAYS.items()
        ]

    def start(
        self,
        *,
        profile: str,
        history_start: date | None,
        history_end: date | None,
        auto_activate: bool,
        idempotency_key: str | None,
    ) -> tuple[dict, bool]:
        if profile not in PROFILE_DAYS:
            raise InvalidTaskParametersError(f"unsupported initialization profile: {profile}")
        resolved_end = history_end or (_today() - timedelta(days=1))
        profile_days = PROFILE_DAYS[profile]
        resolved_start = history_start or (
            FULL_HISTORY_START
            if profile == "full"
            else resolved_end - timedelta(days=profile_days - 1)
        )
        if resolved_end >= _today():
            raise InvalidTaskParametersError(
                "initialization history_end must be an already completed day"
            )
        if resolved_start > resolved_end:
            raise InvalidTaskParametersError("history_start must not be later than history_end")
        if profile == "full" and resolved_start < FULL_HISTORY_START:
            raise InvalidTaskParametersError(
                f"full initialization cannot start before {FULL_HISTORY_START.isoformat()}"
            )
        if profile != "full" and (resolved_end - resolved_start).days > 3660:
            raise InvalidTaskParametersError("initialization history cannot exceed 10 years")
        key = idempotency_key or (
            f"initialize-{profile}-{resolved_start.isoformat()}-{resolved_end.isoformat()}"
        )
        try:
            campaign, created = self._repository.create(
                profile=profile,
                history_start=resolved_start,
                history_end=resolved_end,
                auto_activate=auto_activate,
                idempotency_key=key,
                options={"core_tasks": list(CORE_TASKS)},
            )
        except ValueError as exc:
            raise JobConflictError(str(exc)) from exc
        if not created and (
            campaign["profile"] != profile
            or campaign["history_start"] != resolved_start
            or campaign["history_end"] != resolved_end
            or campaign["auto_activate"] != auto_activate
        ):
            raise JobConflictError(
                "idempotency key is already associated with another initialization plan"
            )
        if created:
            self.reconcile(campaign["initialization_id"])
        return self.get(campaign["initialization_id"]), created

    def get(self, initialization_id: int) -> dict:
        campaign = self._repository.get(initialization_id)
        if not campaign:
            raise JobNotFoundError(f"initialization not found: {initialization_id}")
        return self._decorate(campaign)

    def list_steps(self, initialization_id: int, *, limit: int = 500) -> list[dict]:
        self.get(initialization_id)
        return [self._decorate_step(item) for item in self._repository.list_steps(
            initialization_id, limit=limit
        )]

    def pause(self, initialization_id: int) -> dict:
        campaign = self.get(initialization_id)
        if campaign["status"] != "running":
            raise JobConflictError("only a running initialization can be paused")
        self._repository.set_status(initialization_id, "paused")
        return self.get(initialization_id)

    def resume(self, initialization_id: int) -> dict:
        campaign = self.get(initialization_id)
        failed = [
            step for step in self._repository.phase_steps(
                initialization_id, campaign["current_phase"]
            )
            if self._step_state(step) == "failed"
        ]
        missing_fanout_steps = (
            campaign["status"] == "running"
            and campaign["phase_name"] == "fanout_baseline"
            and campaign["materialized_steps"] < campaign["logical_total_steps"]
        )
        if campaign["status"] not in {"paused", "attention"} and not (
            campaign["status"] == "running" and (failed or missing_fanout_steps)
        ):
            raise JobConflictError(
                "only a paused/attention initialization or a running "
                "initialization with failed steps can resume"
            )
        if failed:
            # Repair only settled failures. Other fan-outs in this phase can
            # keep running safely while corrected jobs are rebuilt in a new
            # verification round; successful work is never discarded.
            self._repository.increment_round(initialization_id)
            for step in failed:
                self._repository.delete_step(step["step_id"])
        self._repository.set_status(initialization_id, "running")
        if failed or missing_fanout_steps:
            # ``reconcile`` intentionally waits for a materialized batch to
            # settle. Repair planning is different: missing fanout-baseline
            # steps must be recreated immediately so independent workers can
            # make progress instead of waiting hours for sibling campaigns.
            self._plan_phase(self._repository.get(initialization_id))
        return self.reconcile(initialization_id)

    def activate(self, initialization_id: int) -> dict:
        try:
            self._repository.activate(initialization_id)
        except ValueError as exc:
            raise JobConflictError(str(exc)) from exc
        return self.get(initialization_id)

    def reconcile_active(self) -> dict | None:
        campaign = self._repository.active()
        if not campaign:
            return campaign
        if campaign["status"] == "attention":
            # A deployment can make an old attention classification resolvable
            # (for example, a newly recognized but strictly verified empty
            # partition). Re-evaluate the durable steps before requiring an
            # operator retry; no task is deleted or duplicated on this path.
            steps = self._repository.phase_steps(
                campaign["initialization_id"], campaign["current_phase"]
            )
            states = [self._step_state(step) for step in steps]
            if states and "running" not in states and "failed" not in states:
                self._repository.set_status(campaign["initialization_id"], "running")
                return self.reconcile(campaign["initialization_id"])
            recovered = self._auto_recover_transient_attention(campaign)
            if recovered is not None:
                return recovered
        if campaign["status"] != "running":
            return self._decorate(campaign)
        return self.reconcile(campaign["initialization_id"])

    def _auto_recover_transient_attention(self, campaign: dict) -> dict | None:
        """Resume only a settled phase made up solely of transient failures.

        Completeness, permission, request, deployment and verification failures
        remain fail-closed in ``attention``. This narrowly scoped recovery is
        intended for incidents such as a temporary DNS outage, where requiring
        a human click leaves most of a deterministic history plan unmaterialized.
        """
        steps = self._repository.phase_steps(
            campaign["initialization_id"], campaign["current_phase"]
        )
        states = [self._step_state(step) for step in steps]
        if not states or "running" in states:
            return None
        failed = [
            step for step, state in zip(steps, states, strict=True)
            if state == "failed"
        ]
        if not failed or any(step.get("resource_type") != "collection" for step in failed):
            return None
        failures = [
            (step.get("completion_evidence") or {}).get("failure") or {}
            for step in failed
        ]
        if any(
            evidence.get("retryable") is not True
            or evidence.get("category") not in TRANSIENT_AUTO_RECOVERY_CATEGORIES
            for evidence in failures
        ):
            return None
        finished = [
            step.get("collection_finished_at")
            for step in failed
            if step.get("collection_finished_at") is not None
        ]
        if len(finished) != len(failed):
            return None
        latest_failure = max(finished)
        if latest_failure.tzinfo is None:
            latest_failure = latest_failure.replace(tzinfo=SHANGHAI)
        age_seconds = (datetime.now(SHANGHAI) - latest_failure).total_seconds()
        if age_seconds < INITIALIZATION_AUTO_RECOVERY_COOLDOWN_SECONDS:
            return None
        claimed = self._repository.claim_transient_auto_recovery(
            campaign["initialization_id"],
            max_recoveries=INITIALIZATION_AUTO_RECOVERY_MAX_ROUNDS,
        )
        if claimed is None:
            return None
        return self.resume(campaign["initialization_id"])

    def reconcile(self, initialization_id: int) -> dict:
        campaign = self._repository.get(initialization_id)
        if not campaign:
            raise JobNotFoundError(f"initialization not found: {initialization_id}")
        if campaign["status"] != "running":
            return self._decorate(campaign)

        # Keep at most one bounded planning batch active. Evaluating failures
        # while sibling collection/verification jobs are still running caused
        # campaigns to enter attention on the first early result, even though
        # the rest of the batch continued in the queue. It also allowed another
        # 500 jobs to be added every scheduler tick. Wait for the current batch
        # to settle, then either retry it or plan the next batch.
        steps = self._repository.phase_steps(initialization_id, campaign["current_phase"])
        states = [self._step_state(step) for step in steps]
        if "running" in states:
            self._update_phase_progress(initialization_id, states)
            return self.get(initialization_id)
        if "failed" in states:
            failed = states.count("failed")
            self._update_phase_progress(initialization_id, states)
            self._repository.set_status(
                initialization_id,
                "attention",
                error_message=f"{failed} initialization step(s) require attention",
            )
            return self.get(initialization_id)

        try:
            plan_complete = self._plan_phase(campaign)
        except Exception as exc:
            self._repository.set_status(
                initialization_id,
                "attention",
                error_message=f"planning failed: {type(exc).__name__}: {exc}"[:4000],
            )
            return self.get(initialization_id)
        steps = self._repository.phase_steps(initialization_id, campaign["current_phase"])
        states = [self._step_state(step) for step in steps]
        self._update_phase_progress(initialization_id, states)
        completed = states.count("complete")
        failed = states.count("failed")
        if not states and plan_complete:
            if campaign["current_phase"] == len(PHASES) - 1:
                self._repository.set_status(initialization_id, "ready")
                if campaign["auto_activate"]:
                    self._repository.activate(initialization_id)
            else:
                next_phase = campaign["current_phase"] + 1
                self._repository.advance(
                    initialization_id, next_phase, PHASES[next_phase]
                )
        elif failed and "running" not in states:
            self._repository.set_status(
                initialization_id,
                "attention",
                error_message=f"{failed} initialization step(s) require attention",
            )
        elif states and completed == len(states) and plan_complete:
            if campaign["current_phase"] == len(PHASES) - 1:
                self._repository.set_status(initialization_id, "ready")
                ready = self._repository.get(initialization_id)
                if ready["auto_activate"]:
                    self._repository.activate(initialization_id)
            else:
                next_phase = campaign["current_phase"] + 1
                self._repository.advance(
                    initialization_id, next_phase, PHASES[next_phase]
                )
        return self.get(initialization_id)

    def _update_phase_progress(self, initialization_id: int, states: list[str]) -> None:
        failed = states.count("failed")
        self._repository.update_progress(
            initialization_id,
            planned=len(states),
            completed=states.count("complete"),
            failed=failed,
            error_message=(
                f"{failed} initialization step(s) require attention" if failed else None
            ),
        )

    def _plan_phase(self, campaign: dict) -> bool:
        planners = (
            self._plan_foundation,
            self._plan_core_history,
            self._plan_finance_history,
            self._plan_catalog_history,
            self._plan_latest_baseline,
            self._plan_fanout_baseline,
            self._plan_verification,
        )
        existing_steps = self._repository.step_keys(
            campaign["initialization_id"], campaign["current_phase"]
        )
        return planners[campaign["current_phase"]](campaign, existing_steps)

    def _submit_collection(
        self,
        campaign: dict,
        step_key: str,
        task_name: str,
        parameters: dict,
        *,
        allow_empty: bool,
        require_verified: bool,
        period_key: str | None = None,
        expected_for: date | None = None,
        existing_steps: set[str],
    ) -> bool:
        initialization_id = campaign["initialization_id"]
        if step_key in existing_steps:
            return False
        round_number = campaign["verification_round"]
        api_name = None
        if task_name == "scheduled_collector":
            from service.tushare_scheduling import DEDICATED_API_BY_RUN_ID

            api_name = DEDICATED_API_BY_RUN_ID.get(parameters.get("schedule_id"))
        job, _ = self._job_service.submit(
            task_name,
            parameters,
            max_attempts=3,
            idempotency_key=_safe_key(
                f"init-{initialization_id}-r{round_number}-{step_key}"
            ),
            api_name=api_name,
            cadence="initialization",
            period_key=period_key,
            expected_for=expected_for,
            priority=30,
            resource_class="initialization",
        )
        self._repository.add_collection_step(
            initialization_id,
            campaign["current_phase"],
            step_key,
            job["job_id"],
            allow_empty=allow_empty,
            require_verified=require_verified,
        )
        existing_steps.add(step_key)
        return True

    def _plan_foundation(self, campaign: dict, existing_steps: set[str]) -> bool:
        start = campaign["history_start"]
        end = campaign["history_end"]
        self._submit_collection(
            campaign, "foundation:trade_calendar", "trade_calendar",
            {
                "start_date": start.isoformat(),
                "end_date": (end + timedelta(days=366)).isoformat(),
                "exchanges": ["SSE", "SZSE"],
            },
            allow_empty=False, require_verified=True,
            existing_steps=existing_steps,
        )
        self._submit_collection(
            campaign, "foundation:stock_basic", "stock_basic", {},
            allow_empty=False, require_verified=False,
            existing_steps=existing_steps,
        )
        self._submit_collection(
            campaign,
            "foundation:cb_basic",
            "tushare_interface",
            {"api_name": "cb_basic", "parameters": {}, "complete": True, "resume": True},
            allow_empty=False,
            require_verified=True,
            existing_steps=existing_steps,
        )
        # fund_basic defaults to the exchange market and its OTC live-fund
        # scope exceeds the documented 15,000-row cap. The gateway supports
        # offset pagination, but E/O remain two distinct logical universes.
        for market in ("E", "O"):
            self._submit_collection(
                campaign,
                f"foundation:fund_basic:{market}",
                "tushare_interface",
                {
                    "api_name": "fund_basic",
                    "parameters": {"market": market},
                    "complete": True,
                    "resume": True,
                },
                allow_empty=False,
                require_verified=True,
                existing_steps=existing_steps,
            )
        if campaign["profile"] == "full":
            for source in ("SW2014", "SW2021"):
                self._submit_collection(
                    campaign,
                    f"foundation:index_classify:{source}:L3",
                    "tushare_interface",
                    {
                        "api_name": "index_classify",
                        "parameters": {"level": "L3", "src": source},
                        "complete": True,
                        "resume": True,
                    },
                    allow_empty=False,
                    require_verified=True,
                    existing_steps=existing_steps,
                )
        scheduled_for = datetime.combine(end, datetime.min.time(), SHANGHAI).replace(hour=20)
        for schedule_id in ("index_basic_weekly",):
            self._submit_collection(
                campaign,
                f"foundation:{schedule_id}",
                "scheduled_collector",
                {"schedule_id": schedule_id, "scheduled_for": scheduled_for.isoformat()},
                allow_empty=True,
                require_verified=False,
                existing_steps=existing_steps,
            )
        return True

    def _plan_fanout_baseline(
        self, campaign: dict, existing_steps: set[str]
    ) -> bool:
        if campaign["profile"] != "full":
            return True
        initialization_id = campaign["initialization_id"]
        round_number = campaign["verification_round"]
        for api_name in FULL_FANOUT_BASELINES:
            step_key = f"fanout:{api_name}"
            if step_key in existing_steps:
                continue
            fanout, _ = self._fanout_service.submit(
                self._fanout_baseline_request(api_name, campaign),
                idempotency_key=_safe_key(
                    f"init-{initialization_id}-r{round_number}-{step_key}"
                ),
                initialization_id=initialization_id,
                cadence="initialization",
                period_key=f"initial-{campaign['history_end'].isoformat()}",
                expected_for=campaign["history_end"],
                reuse_scope=True,
            )
            self._repository.add_fanout_step(
                initialization_id,
                campaign["current_phase"],
                step_key,
                fanout["campaign_id"],
                allow_empty=api_name in _EMPTY_FANOUT_BASELINES,
            )
            existing_steps.add(step_key)

        # These two fund interfaces accept a whole-market date/period scope
        # and reliable limit/offset pagination. Querying that bounded scope is
        # equivalent to per-fund fan-out but reduces tens of thousands of HTTP
        # requests to a few hundred exhaustively paginated partitions.
        end = campaign["history_end"]
        nav_start = max(campaign["history_start"], end - timedelta(days=365))
        cursor = nav_start
        while cursor <= end:
            compact = cursor.strftime("%Y%m%d")
            step_key = f"market:fund_nav:{compact}"
            if step_key not in existing_steps:
                self._submit_collection(
                    campaign,
                    step_key,
                    "tushare_interface",
                    {
                        "api_name": "fund_nav",
                        "parameters": {"nav_date": compact},
                        "complete": True,
                        "page_size": 5000,
                        "max_pages": 100,
                        "resume": True,
                    },
                    allow_empty=True,
                    require_verified=True,
                    period_key=compact,
                    expected_for=cursor,
                    existing_steps=existing_steps,
                )
            cursor += timedelta(days=1)

        periods = _published_quarter_ends(FULL_HISTORY_START, end)
        if not periods:
            raise JobConflictError("no published fund portfolio period exists")
        period = periods[-1]
        compact_period = period.strftime("%Y%m%d")
        self._submit_collection(
            campaign,
            f"market:fund_portfolio:{compact_period}",
            "tushare_interface",
            {
                "api_name": "fund_portfolio",
                "parameters": {"period": compact_period},
                "complete": True,
                "page_size": 5000,
                "max_pages": 500,
                "resume": True,
            },
            allow_empty=False,
            require_verified=True,
            period_key=compact_period,
            expected_for=period,
            existing_steps=existing_steps,
        )
        return True

    @staticmethod
    def _fanout_baseline_request(api_name: str, campaign: dict) -> dict:
        """Build one bounded, reproducible scope for an initial fan-out."""
        from service.collection_jobs.fanout import FANOUT_DEFINITIONS

        definition = FANOUT_DEFINITIONS[api_name]
        end = campaign["history_end"]
        request: dict[str, Any] = {"api_name": api_name, "page_size": 200}
        if definition.scope == "trade_date":
            from service.tushare_scheduling import _latest_trade_date

            compact = _latest_trade_date(end)
            request["trade_date"] = date(
                int(compact[:4]), int(compact[4:6]), int(compact[6:])
            ).isoformat()
        elif definition.scope == "ann_date":
            request["ann_date"] = end.isoformat()
        elif definition.scope == "period":
            periods = _published_quarter_ends(FULL_HISTORY_START, end)
            if not periods:
                raise JobConflictError(
                    f"no published report period exists for {api_name} baseline"
                )
            request["period"] = periods[-1].isoformat()
        elif definition.scope == "date_window":
            window_start = max(
                campaign["history_start"],
                end - timedelta(days=definition.max_window_days - 1),
            )
            request.update(
                start_date=window_start.isoformat(),
                end_date=end.isoformat(),
            )
        return request

    def _plan_core_history(self, campaign: dict, existing_steps: set[str]) -> bool:
        dates = self._repository.trade_dates(
            campaign["history_start"], campaign["history_end"]
        )
        if not dates:
            raise JobConflictError(
                "trade calendar has no open dates in the initialization range"
            )
        tasks = CORE_TASKS if campaign["profile"] != "quick" else CORE_TASKS[:2]
        created = 0
        for trade_date in dates:
            compact = trade_date.strftime("%Y%m%d")
            for task_name in tasks:
                if (
                    campaign["profile"] == "full"
                    and trade_date < FULL_HISTORY_DATASET_STARTS[task_name]
                ):
                    continue
                step_key = f"core:{task_name}:{compact}"
                if step_key in existing_steps:
                    continue
                if created >= PLANNING_BATCH_SIZE:
                    return False
                self._submit_collection(
                    campaign,
                    step_key,
                    task_name,
                    {"trade_date": compact},
                    allow_empty=False,
                    require_verified=True,
                    period_key=compact,
                    expected_for=trade_date,
                    existing_steps=existing_steps,
                )
                created += 1
            if campaign["profile"] != "quick":
                for api_name in CORE_INTERFACE_HISTORY:
                    if (
                        campaign["profile"] == "full"
                        and trade_date < FULL_HISTORY_DATASET_STARTS.get(
                            api_name, FULL_HISTORY_START
                        )
                    ):
                        continue
                    step_key = f"core:{api_name}:{compact}"
                    if step_key in existing_steps:
                        continue
                    if created >= PLANNING_BATCH_SIZE:
                        return False
                    self._submit_collection(
                        campaign,
                        step_key,
                        "tushare_interface",
                        {
                            "api_name": api_name,
                            "parameters": {"trade_date": compact},
                            "complete": True,
                            "page_size": CORE_INTERFACE_PAGE_SIZES[api_name],
                            "resume": True,
                        },
                        allow_empty=api_name in VERIFIED_EMPTY_CORE_INTERFACES,
                        require_verified=True,
                        period_key=compact,
                        expected_for=trade_date,
                        existing_steps=existing_steps,
                    )
                    created += 1
        return True

    def _plan_finance_history(self, campaign: dict, existing_steps: set[str]) -> bool:
        created = 0
        for period in _published_quarter_ends(
            campaign["history_start"], campaign["history_end"]
        ):
            compact = period.strftime("%Y%m%d")
            for task_name in FINANCE_TASKS:
                step_key = f"finance:{task_name}:{compact}"
                if step_key in existing_steps:
                    continue
                if created >= PLANNING_BATCH_SIZE:
                    return False
                self._submit_collection(
                    campaign,
                    step_key,
                    task_name,
                    {"period": compact},
                    allow_empty=(
                        period
                        < business_now().date()
                        - timedelta(
                            days=FINANCIAL_ENTITY_REFERENCE_MAX_AGE_DAYS - 1
                        )
                    ),
                    require_verified=True,
                    period_key=compact,
                    expected_for=period,
                    existing_steps=existing_steps,
                )
                created += 1
            for api_name in AUXILIARY_FINANCE_INTERFACES:
                step_key = f"finance:{api_name}:{compact}"
                if step_key in existing_steps:
                    continue
                if created >= PLANNING_BATCH_SIZE:
                    return False
                self._submit_collection(
                    campaign,
                    step_key,
                    "tushare_interface",
                    {
                        "api_name": api_name,
                        "parameters": {"period": compact},
                        "complete": True,
                        "resume": True,
                    },
                    allow_empty=True,
                    require_verified=True,
                    period_key=compact,
                    expected_for=period,
                    existing_steps=existing_steps,
                )
                created += 1
        return True

    def _plan_catalog_history(self, campaign: dict, existing_steps: set[str]) -> bool:
        """Backfill historically missed automatic catalog families.

        Low-volume macro series use annual windows. High-volume securities
        lending series use monthly, offset-paginated windows. Every job is
        independently resumable and must prove a bounded, exhausted response.
        """
        if campaign["profile"] == "quick":
            return True
        created = 0
        history_start = campaign["history_start"]
        history_end = campaign["history_end"]
        for partition in catalog_history_partitions(history_start, history_end):
            step_key = f"catalog-history:{partition.key}"
            if step_key in existing_steps:
                continue
            if created >= PLANNING_BATCH_SIZE:
                return False
            self._submit_collection(
                campaign,
                step_key,
                "tushare_interface",
                {
                    "api_name": partition.api_name,
                    "parameters": partition.parameters,
                    "complete": True,
                    "page_size": 1000,
                    "max_pages": 100,
                    "resume": True,
                },
                allow_empty=True,
                require_verified=True,
                period_key=partition.key,
                expected_for=partition.end_date,
                existing_steps=existing_steps,
            )
            created += 1
        return True

    def _plan_latest_baseline(self, campaign: dict, existing_steps: set[str]) -> bool:
        from service.tushare_catalog import TushareInterfaceCatalog
        from service.tushare_policy import TusharePolicyRegistry
        from service.tushare_scheduling import (
            DEDICATED_SCHEDULED_APIS,
            _latest_trade_date,
            parameters_for_policy,
        )

        end = campaign["history_end"]
        trade_date = _latest_trade_date(end)
        catalog = TushareInterfaceCatalog()
        policies = TusharePolicyRegistry()
        for contract in catalog.list():
            if (
                not contract.collectable
                or contract.api_name in DEDICATED_SCHEDULED_APIS
                or contract.api_name in FULL_INITIALIZATION_BASELINES
            ):
                continue
            policy = policies.get(contract.api_name)
            if not policy.automatic_safe:
                continue
            target = end - timedelta(days=7) if policy.cadence == "weekly" else end
            parameters = parameters_for_policy(
                policy,
                {item["name"] for item in contract.input_parameters},
                today=target,
                trade_date=trade_date if policy.cadence == "daily" else None,
            )
            self._submit_collection(
                campaign,
                f"catalog:{contract.api_name}",
                "tushare_interface",
                {
                    "api_name": contract.api_name,
                    "parameters": parameters,
                    "complete": True,
                    "resume": True,
                },
                allow_empty=True,
                require_verified=True,
                period_key=f"initial-{end.isoformat()}",
                expected_for=end,
                existing_steps=existing_steps,
            )

        from collectors.scheduler import scheduled_collection_ids

        excluded = {
            "trade_cal_daily", "stock_basic_daily", "index_basic_weekly",
            "index_daily_finalize",
            "daily_daily", "bak_basic_daily",
            "stk_limit_daily", "income_quarterly", "income_annual_update",
            "balancesheet_quarterly", "balancesheet_annual",
            "cashflow_quarterly", "cashflow_annual",
            "fina_indicator_quarterly", "fina_indicator_annual",
        }
        scheduled_for = datetime.combine(end, datetime.min.time(), SHANGHAI).replace(hour=20)
        for schedule_id in sorted(scheduled_collection_ids() - excluded):
            self._submit_collection(
                campaign,
                f"dedicated:{schedule_id}",
                "scheduled_collector",
                {"schedule_id": schedule_id, "scheduled_for": scheduled_for.isoformat()},
                allow_empty=True,
                require_verified=False,
                period_key=f"initial-{end.isoformat()}",
                expected_for=end,
                existing_steps=existing_steps,
            )
        return True

    def _plan_verification(self, campaign: dict, existing_steps: set[str]) -> bool:
        initialization_id = campaign["initialization_id"]
        round_number = campaign["verification_round"]
        dataset_names = (
            VERIFICATION_DATASETS
            if campaign["profile"] != "quick"
            else VERIFICATION_DATASETS[:2]
        )
        for dataset_name in dataset_names:
            step_key = f"verify:{dataset_name}"
            if step_key in existing_steps:
                continue
            verification_start = campaign["history_start"]
            if campaign["profile"] == "full":
                verification_start = max(
                    verification_start,
                    FULL_HISTORY_DATASET_STARTS.get(
                        dataset_name, campaign["history_start"]
                    ),
                )
                if dataset_name in INITIALIZATION_TRANSPORT_VERIFIED_DATASETS:
                    verification_start = max(
                        verification_start,
                        campaign["history_end"] - timedelta(
                            days=INITIALIZATION_STRICT_COVERAGE_LOOKBACK_DAYS - 1
                        ),
                    )
            result = self._coverage_service.submit_audits(
                [dataset_name],
                start_date=verification_start,
                end_date=campaign["history_end"],
                idempotency_key=(
                    f"initialization-{initialization_id}-r{round_number}"
                ),
            )
            self._repository.add_coverage_step(
                initialization_id,
                campaign["current_phase"],
                step_key,
                result["jobs"][0]["job_id"],
            )
            existing_steps.add(step_key)
        return True

    @staticmethod
    def _step_state(step: dict) -> str:
        if step["resource_type"] == "fanout":
            status = step.get("fanout_status")
            completion = step.get("fanout_completion_status")
            if status in {"running", "paused"}:
                return "running"
            if status != "success" or completion == "incomplete":
                return "failed"
            if completion == "empty" and not step["allow_empty"]:
                return "failed"
            return "complete"
        if step["resource_type"] == "collection":
            status = step.get("collection_status")
            completion = step.get("completion_status")
            evidence = step.get("completion_evidence") or {}
            verification = evidence.get("verification") or {}
            verified = (
                evidence.get("verified") is True
                or verification.get("verified") is True
            )
            if status in {"queued", "running"} or completion in {
                "pending", "running", "retrying", "verifying",
            }:
                return "running"
            if status != "success" or completion in {"failed", "incomplete"}:
                return "failed"
            if completion == "empty":
                accepts_verified_empty = (
                    step.get("collection_api_name")
                    in VERIFIED_EMPTY_CORE_INTERFACES
                )
                if not step["allow_empty"] and not accepts_verified_empty:
                    return "failed"
                if step["require_verified"] and not verified:
                    return "failed"
                return "complete"
            if completion == "unverified" and step["require_verified"]:
                return "failed"
            if completion == "complete" and step["require_verified"]:
                if not verified:
                    return "failed"
            return "complete"
        coverage_status = step.get("coverage_status")
        if coverage_status in {"queued", "running"} or not step.get("audit_status"):
            return "running"
        if coverage_status != "success":
            return "failed"
        # Historical completion is an acceptance decision, not merely proof
        # that some rows exist.  ``observed_only`` means no strict expected
        # partition contract was available, so it must remain visible instead
        # of activating daily mode as if coverage had been proven.
        return "complete" if step["audit_status"] == "complete" else "failed"

    def _decorate(self, campaign: dict) -> dict:
        result = dict(campaign)
        materialized = int(result.get("planned_steps") or 0)
        logical_total = self._phase_logical_total(result)
        # The coordinator intentionally materializes large phases in bounded
        # batches. ``planned_steps`` is therefore the number already written
        # to the queue, not the stable denominator for phase progress.
        total = max(materialized, logical_total or 0)
        completed = int(result.get("completed_steps") or 0)
        result["materialized_steps"] = materialized
        result["logical_total_steps"] = total
        result["remaining_steps"] = max(total - completed, 0)
        result["progress_ratio"] = (
            completed / total if total else 0.0
        )
        result["progress_basis"] = (
            "logical_total" if logical_total is not None else "materialized"
        )
        result["phase_index"] = result["current_phase"] + 1
        result["phase_total"] = len(PHASES)
        completed_campaign = result.get("status") == "completed"
        final_phase_reached = (
            int(result.get("current_phase") or 0) == len(PHASES) - 1
        )
        current_phase_settled = (
            int(result.get("failed_steps") or 0) == 0
            and completed == total
        )
        result["completion_gate"] = {
            "complete": completed_campaign,
            "requirements": [
                {
                    "key": "all_phases_executed",
                    "met": final_phase_reached and current_phase_settled,
                    "description": "七个初始化阶段均已执行且没有待处理步骤",
                },
                {
                    "key": "strict_coverage_verified",
                    "met": completed_campaign,
                    "description": "最终覆盖审计全部为 complete，无缺失或部分分区",
                },
                {
                    "key": "daily_mode_activated",
                    "met": completed_campaign,
                    "description": "验收通过后已原子切换到日常采集模式",
                },
            ],
        }
        work_window = getattr(self._repository, "phase_work_window", None)
        result["work_window"] = (
            work_window(result["initialization_id"], result["current_phase"])
            if callable(work_window)
            else None
        )
        return result

    def _phase_logical_total(self, campaign: dict) -> int | None:
        """Return a stable top-level work count for the active phase.

        Large history phases are generated 500 jobs at a time.  Counting only
        rows already present in ``sys_collection_initialization_step`` makes a
        batch look almost complete while most dates have not been planned yet.
        The phase definitions below are deterministic, so their logical size
        can be computed without creating jobs or calling an upstream service.

        ``latest_baseline`` is catalog-driven and planned atomically rather
        than in batches; its materialized count remains the honest denominator.
        """
        phase = int(campaign.get("current_phase") or 0)
        profile = campaign.get("profile")
        start = campaign.get("history_start")
        end = campaign.get("history_end")
        if not isinstance(start, date) or not isinstance(end, date):
            return None
        if phase == 0:
            # Calendar, stock/cb/fund universes, two scheduled foundations,
            # plus two index-classification universes for the full profile.
            return 9 if profile == "full" else 7
        if phase == 1:
            dates = self._repository.trade_dates(start, end)
            if not dates:
                return None
            if profile == "quick":
                return len(dates) * 2
            if profile != "full":
                return len(dates) * (len(CORE_TASKS) + len(CORE_INTERFACE_HISTORY))
            logical_tasks = (*CORE_TASKS, *CORE_INTERFACE_HISTORY)
            return sum(
                trade_date >= FULL_HISTORY_DATASET_STARTS.get(task, FULL_HISTORY_START)
                for trade_date in dates
                for task in logical_tasks
            )
        if phase == 2:
            return len(_published_quarter_ends(start, end)) * (
                len(FINANCE_TASKS) + len(AUXILIARY_FINANCE_INTERFACES)
            )
        if phase == 3:
            return 0 if profile == "quick" else len(
                catalog_history_partitions(start, end)
            )
        if phase == 5:
            if profile != "full":
                return 0
            nav_start = max(start, end - timedelta(days=365))
            fund_partitions = (end - nav_start).days + 2  # daily NAV + one portfolio
            return len(FULL_FANOUT_BASELINES) + fund_partitions
        if phase == 6:
            return len(VERIFICATION_DATASETS) if profile != "quick" else 2
        return None

    def _decorate_step(self, step: dict) -> dict:
        result = dict(step)
        result["state"] = self._step_state(step)
        return result
