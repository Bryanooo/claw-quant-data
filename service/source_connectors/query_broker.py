"""Bounded read-through broker for sources that must be queried on demand."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
from threading import Lock, RLock
from typing import Callable

from service.source_connectors.contracts import (
    AcquisitionMode,
    ConnectorRequest,
    ConnectorResult,
    QueryThroughConnector,
)
from service.source_connectors.registry import SourceRegistry


class QueryCircuitOpenError(RuntimeError):
    pass


@dataclass(slots=True)
class _CacheEntry:
    result: ConnectorResult
    expires_at: datetime
    stale_until: datetime


@dataclass(slots=True)
class _Circuit:
    failures: int = 0
    opened_until: datetime | None = None


class QueryBroker:
    """Allow-listed cache/circuit-breaker boundary for query-through sources."""

    def __init__(
        self,
        *,
        registry: SourceRegistry,
        connector_resolver: Callable[[str], QueryThroughConnector],
        failure_threshold: int = 3,
        circuit_cooldown_seconds: int = 30,
        stale_grace_seconds: int = 300,
        clock: Callable[[], datetime] | None = None,
    ):
        if failure_threshold < 1:
            raise ValueError("failure_threshold must be positive")
        self._registry = registry
        self._connector_resolver = connector_resolver
        self._failure_threshold = failure_threshold
        self._cooldown = timedelta(seconds=circuit_cooldown_seconds)
        self._stale_grace = timedelta(seconds=stale_grace_seconds)
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._cache: dict[str, _CacheEntry] = {}
        self._circuits: dict[tuple[str, str], _Circuit] = {}
        self._key_locks = tuple(Lock() for _ in range(64))
        self._lock = RLock()

    @staticmethod
    def _key(request: ConnectorRequest) -> str:
        return json.dumps(
            [request.source_id, request.endpoint_key, dict(request.parameters)],
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
            default=str,
        )

    @staticmethod
    def _with_cache(result: ConnectorResult, state: str) -> ConnectorResult:
        return ConnectorResult(
            source_id=result.source_id,
            endpoint_key=result.endpoint_key,
            acquisition_mode=result.acquisition_mode,
            records=result.records,
            fetched_rows=result.fetched_rows,
            stored_rows=result.stored_rows,
            status=result.status,
            evidence={**dict(result.evidence), "cache": state},
            warnings=result.warnings,
        )

    def query(
        self,
        request: ConnectorRequest,
        *,
        allow_stale: bool = True,
    ) -> ConnectorResult:
        endpoint = self._registry.get_endpoint(request.source_id, request.endpoint_key)
        if request.acquisition_mode != AcquisitionMode.QUERY_THROUGH:
            raise ValueError("query broker only accepts query_through requests")
        if endpoint.acquisition_mode != request.acquisition_mode:
            raise ValueError("request mode does not match endpoint contract")
        cache_key = self._key(request)
        circuit_key = (request.source_id, request.endpoint_key)
        key_lock = self._key_locks[hash(cache_key) % len(self._key_locks)]

        # Identical normalized requests share a striped lock. Unrelated keys
        # remain concurrent except for rare stripe collisions, while memory
        # stays bounded under untrusted query cardinality.
        with key_lock:
            now = self._clock()
            with self._lock:
                cached = self._cache.get(cache_key)
                if cached and cached.expires_at > now:
                    return self._with_cache(cached.result, "hit")
                circuit = self._circuits.setdefault(circuit_key, _Circuit())
                if circuit.opened_until and circuit.opened_until > now:
                    if allow_stale and cached and cached.stale_until > now:
                        return self._with_cache(cached.result, "stale")
                    raise QueryCircuitOpenError(
                        "query circuit is open for "
                        f"{request.source_id}/{request.endpoint_key}"
                    )
                if circuit.opened_until and circuit.opened_until <= now:
                    circuit.opened_until = None

            # Query connectors must implement their own transport timeout.
            try:
                result = self._connector_resolver(request.source_id).query(request)
            except Exception:
                with self._lock:
                    circuit.failures += 1
                    if circuit.failures >= self._failure_threshold:
                        circuit.opened_until = now + self._cooldown
                    if allow_stale and cached and cached.stale_until > now:
                        return self._with_cache(cached.result, "stale")
                raise
            with self._lock:
                circuit.failures = 0
                circuit.opened_until = None
                ttl = endpoint.cache_ttl_seconds or 0
                self._cache[cache_key] = _CacheEntry(
                    result=result,
                    expires_at=now + timedelta(seconds=ttl),
                    stale_until=now + timedelta(seconds=ttl) + self._stale_grace,
                )
            return self._with_cache(result, "miss")
