"""Application service for collection, analysis, persistence and reads."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from service.intraday.analyzer import analyze_instrument, analyze_market
from service.intraday.collector import AntIntradayCollector, INDEX_PROXIES, PROXIES
from service.intraday.replay import replay_day
from service.source_connectors.ant_budget import budget_scope


CST = timezone(timedelta(hours=8))


class IntradayObservationService:
    def __init__(self, repository, collector_factory=AntIntradayCollector):
        self._repository = repository
        self._collector_factory = collector_factory

    @staticmethod
    def slot(now: datetime) -> datetime:
        local = now.astimezone(CST).replace(second=0, microsecond=0)
        return local.replace(minute=(local.minute // 15) * 15)

    def run(self, *, now: datetime | None = None, trigger_source: str = "manual") -> dict:
        now = now or datetime.now(CST)
        scheduled_for = self.slot(now)
        run_id = self._repository.claim_run(scheduled_for, trigger_source)
        if run_id is None:
            return {"status": "already_collected", "scheduled_for": scheduled_for}
        collector = self._collector_factory()
        try:
            watchlist = self._repository.observed_watchlist()
            with budget_scope('intraday'):
                batch = collector.collect(now=now, watchlist=watchlist)
            snapshots_by_symbol = {str(row.get("symbol")): row for row in batch["snapshots"]}
            proxies = [snapshots_by_symbol[symbol] for symbol in PROXIES if symbol in snapshots_by_symbol]
            sectors = [
                snapshots_by_symbol[symbol]
                for symbol in batch["industry_symbols"] if symbol in snapshots_by_symbol
            ]
            market = analyze_market(
                as_of=batch["as_of"], proxies=proxies, sectors=sectors,
                flows=batch["flow_source"], expected_proxies=batch["expected_proxies"],
                expected_sectors=batch["expected_sectors"],
                timestamp_fresh=batch["timestamp_fresh"],
            )
            analyses = [market]
            for symbol in PROXIES:
                if symbol in snapshots_by_symbol:
                    analyses.append(analyze_instrument(
                        as_of=batch["as_of"], row=snapshots_by_symbol[symbol],
                        market=market, scope_type="etf",
                    ))
            for symbol in INDEX_PROXIES:
                if symbol in snapshots_by_symbol:
                    analyses.append(analyze_instrument(
                        as_of=batch["as_of"], row=snapshots_by_symbol[symbol],
                        market=market, scope_type="index",
                    ))
            for symbol in batch["watch_symbols"]:
                if symbol in snapshots_by_symbol:
                    analyses.append(analyze_instrument(
                        as_of=batch["as_of"], row=snapshots_by_symbol[symbol],
                        market=market, scope_type="stock",
                    ))
            evidence = {
                "missing_symbols": batch["missing_symbols"],
                "hot_plates": batch["hot_plates"],
                "collection_cadence_minutes": 15,
                "provider_period": "P_Min1",
                "provider_period_reason": "场内基金分钟K仅支持P_Min1；按15分钟轮次批量采集并持久化",
            }
            self._repository.persist(
                run_id=run_id, quote_rows=batch["quote_rows"],
                flow_rows=batch["flow_rows"], analyses=analyses,
                usage=batch["usage"], evidence=evidence,
            )
            return {
                "status": "success", "run_id": run_id,
                "scheduled_for": scheduled_for, "analysis_count": len(analyses),
                "usage": batch["usage"], "market": market,
            }
        except Exception as exc:
            self._repository.fail_run(run_id, exc, collector.usage)
            raise

    def overview(self, *, history_limit: int = 120) -> dict:
        return self._repository.overview(history_limit=history_limit)

    def backfill_day(
        self,
        day: date,
        *,
        watchlist: list[dict],
        collector: AntIntradayCollector | None = None,
    ) -> dict:
        collector = collector or self._collector_factory()
        with budget_scope('backfill'):
            batch = collector.collect_history_day(day=day, watchlist=watchlist)
        # Fetch first, then replace derived replay rows.  A provider failure
        # therefore cannot erase the last successful validation result.
        self._repository.clear_historical_replay(day)
        return self._persist_replay_batch(batch)

    def backfill_days(
        self,
        days: list[date],
        *,
        watchlist: list[dict],
        collector: AntIntradayCollector | None = None,
    ) -> list[dict]:
        collector = collector or self._collector_factory()
        with budget_scope('backfill'):
            batches = collector.collect_history_days(days=days, watchlist=watchlist)
        reports = []
        for batch in batches:
            self._repository.clear_historical_replay(batch["day"])
            reports.append(self._persist_replay_batch(batch))
        return reports

    def replay_stored_day(self, day: date, *, watchlist: list[dict]) -> dict:
        batch = self._repository.load_history_day(day, watchlist)
        if not batch["quote_rows"]:
            raise ValueError(f"no stored intraday facts for {day}")
        self._repository.clear_historical_replay(day)
        return self._persist_replay_batch(batch)

    def _persist_replay_batch(self, batch: dict) -> dict:
        day: date = batch["day"]
        checkpoints = replay_day(batch)
        completed = 0
        facts_pending = True
        for checkpoint in checkpoints:
            run_id = self._repository.claim_run(checkpoint["as_of"], "historical_backfill")
            if run_id is None:
                continue
            self._repository.persist(
                run_id=run_id,
                quote_rows=batch["quote_rows"] if facts_pending else [],
                flow_rows=batch["flow_rows"] if facts_pending else [],
                analyses=checkpoint["analyses"],
                usage=batch["usage"] if facts_pending else {"outer_calls": 0, "subrequests": 0, "fetched_rows": 0},
                evidence={
                    "historical_replay": True,
                    "source_day": day.isoformat(),
                    "checkpoint": checkpoint["as_of"].isoformat(),
                    "missing_symbols": batch["missing_symbols"],
                    "sample_stocks": sorted(batch["watch_symbols"]),
                },
            )
            facts_pending = False
            completed += 1
        return {
            "day": day.isoformat(), "checkpoints": completed,
            "quote_rows": len(batch["quote_rows"]),
            "flow_rows": len(batch["flow_rows"]),
            "missing_symbols": batch["missing_symbols"],
            "usage": batch["usage"],
        }

    def set_watchlist_observation(self, symbol: str, *, enabled: bool, profile: str) -> dict:
        row = self._repository.set_watchlist_observation(
            symbol.upper(), enabled=enabled, profile=profile,
        )
        if row is None:
            raise LookupError("stock must be in the watchlist before observation can be enabled")
        return {"item": row}
