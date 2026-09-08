"""Conservative recurring recipes for complete fan-out collection."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
import logging
from typing import Literal

from service.collection_jobs.fanout_campaigns import FanoutCampaignService
from service.tushare_scheduling import _latest_trade_date


logger = logging.getLogger(__name__)
Cadence = Literal["daily", "weekly", "monthly"]
ScopeStrategy = Literal["none", "trade_date", "ann_date"]


@dataclass(frozen=True, slots=True)
class ScheduledFanoutRecipe:
    api_name: str
    cadence: Cadence
    scope_strategy: ScopeStrategy
    page_size: int
    reason: str
    plan_version: int = 1


# This allow-list intentionally excludes high-cardinality daily factor and fund
# jobs. They remain available through explicit campaigns until a dedicated
# quota/resource-class worker is configured.
SCHEDULED_FANOUT_RECIPES = (
    ScheduledFanoutRecipe(
        "bc_otcqt", "daily", "trade_date", 100,
        "fan out the complete locally observed OTC bond universe by trade date",
    ),
    ScheduledFanoutRecipe(
        "dc_index", "daily", "trade_date", 1,
        "one static concept-board partition for the latest closed trade date",
    ),
    ScheduledFanoutRecipe(
        "dc_concept_cons", "daily", "trade_date", 200,
        "fan out every listed stock so capped concept memberships are complete",
    ),
    ScheduledFanoutRecipe(
        "etf_sh_cons", "daily", "trade_date", 200,
        "fan out the complete Shanghai ETF reference universe",
    ),
    ScheduledFanoutRecipe(
        "etf_sz_cons", "daily", "trade_date", 200,
        "fan out the complete Shenzhen ETF reference universe",
    ),
    ScheduledFanoutRecipe(
        "factor_value", "daily", "trade_date", 200,
        "fan out the observed factor-name universe within the daily call allowance",
        2,
    ),
    ScheduledFanoutRecipe(
        "moneyflow_dc", "daily", "trade_date", 200,
        "fan out the listed-stock universe to avoid the market-wide row cap",
    ),
    ScheduledFanoutRecipe(
        "tdx_member", "daily", "trade_date", 200,
        "fan out the locally collected TDX board universe",
    ),
    ScheduledFanoutRecipe(
        "opt_daily", "daily", "trade_date", 6,
        "partition option quotes by the documented exchange universe",
    ),
    ScheduledFanoutRecipe(
        "fut_holding", "daily", "trade_date", 6,
        "partition futures holdings by the documented exchange universe",
    ),
    ScheduledFanoutRecipe(
        "fut_index_daily", "daily", "trade_date", 56,
        "fan out the complete static South China futures index universe from doc 468",
    ),
    ScheduledFanoutRecipe(
        "cb_share", "daily", "ann_date", 200,
        "convertible-bond codes are safely grouped by announcement date",
    ),
    ScheduledFanoutRecipe(
        "cb_rate", "weekly", "none", 200,
        "low-change convertible-bond reference snapshot",
    ),
    ScheduledFanoutRecipe(
        "cb_rating", "weekly", "none", 200,
        "low-change convertible-bond rating snapshot",
    ),
    ScheduledFanoutRecipe(
        "ci_index_member", "weekly", "none", 200,
        "weekly refresh of the complete CITIC L3 dependency universe",
    ),
    ScheduledFanoutRecipe(
        "index_member_all", "weekly", "none", 200,
        "weekly refresh of the complete SW L3 dependency universe",
    ),
    ScheduledFanoutRecipe(
        "ths_member", "weekly", "none", 200,
        "fan out every locally known THS board to avoid the 6,000-row cap",
        2,
    ),
    ScheduledFanoutRecipe(
        "fut_basic", "weekly", "none", 6,
        "small static exchange universe",
    ),
    ScheduledFanoutRecipe(
        "pledge_stat", "monthly", "none", 200,
        "large stock snapshot runs as low-priority monthly fan-out",
    ),
)


def _closed_week(today: date) -> tuple[str, date]:
    end = today - timedelta(days=today.weekday() + 1)
    iso = end.isocalendar()
    return f"{iso.year}-W{iso.week:02d}", end


def _closed_month(today: date) -> tuple[str, date]:
    end = today.replace(day=1) - timedelta(days=1)
    return end.strftime("%Y-%m"), end


def _recipe_scope(
    recipe: ScheduledFanoutRecipe,
    today: date,
    *,
    include_current_daily: bool = False,
) -> tuple[dict, str, date]:
    if recipe.cadence == "weekly":
        period_key, expected_for = _closed_week(today)
    elif recipe.cadence == "monthly":
        period_key, expected_for = _closed_month(today)
    elif recipe.scope_strategy == "trade_date":
        scope_day = today if include_current_daily else today - timedelta(days=1)
        compact = _latest_trade_date(scope_day)
        expected_for = date.fromisoformat(
            f"{compact[:4]}-{compact[4:6]}-{compact[6:]}"
        )
        period_key = expected_for.isoformat()
    else:
        expected_for = today if include_current_daily else today - timedelta(days=1)
        period_key = expected_for.isoformat()

    request: dict = {
        "api_name": recipe.api_name,
        "page_size": recipe.page_size,
    }
    if recipe.scope_strategy == "trade_date":
        request["trade_date"] = expected_for
    elif recipe.scope_strategy == "ann_date":
        request["ann_date"] = expected_for
    return request, period_key, expected_for


def submit_scheduled_fanouts(
    cadence: Cadence,
    *,
    today: date,
    include_current_daily: bool = False,
    service: FanoutCampaignService | None = None,
) -> dict[str, int]:
    """Create at most one campaign per recipe and closed business scope."""
    from service.initialization.repository import routine_collection_enabled

    if not routine_collection_enabled():
        return {"created": 0, "existing": 0, "failed": 0}
    campaign_service = service or FanoutCampaignService()
    counts = {"created": 0, "existing": 0, "failed": 0}
    for recipe in SCHEDULED_FANOUT_RECIPES:
        if recipe.cadence != cadence:
            continue
        request, period_key, expected_for = _recipe_scope(
            recipe,
            today,
            include_current_daily=include_current_daily,
        )
        try:
            _, created = campaign_service.submit(
                request,
                idempotency_key=(
                    f"scheduled-fanout:{recipe.api_name}:{cadence}:{period_key}"
                    + (f":v{recipe.plan_version}" if recipe.plan_version > 1 else "")
                ),
                cadence=cadence,
                period_key=period_key,
                expected_for=expected_for,
                plan_version=recipe.plan_version,
                reuse_scope=True,
            )
            counts["created" if created else "existing"] += 1
        except Exception:
            counts["failed"] += 1
            logger.exception(
                "scheduled fan-out submission failed: %s/%s",
                recipe.api_name,
                period_key,
            )
    return counts


def submit_latest_scheduled_fanouts(
    *,
    today: date,
    include_current_daily: bool = False,
) -> dict[str, dict[str, int]]:
    return {
        cadence: submit_scheduled_fanouts(
            cadence,
            today=today,
            include_current_daily=(include_current_daily and cadence == "daily"),
        )
        for cadence in ("daily", "weekly", "monthly")
    }
