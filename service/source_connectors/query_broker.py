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
        max_cache_entries: int = 1024,
    ):
        if failure_threshold < 1:
            raise ValueError("failure_threshold must be positive")
        if max_cache_entries < 1:
            raise ValueError("max_cache_entries must be positive")
        self._max_cache_entries = max_cache_entries
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
        cache_ttl_seconds: int | None = None,
        required_fields: tuple[str, ...] = (),
        require_point_in_time: bool = False,
    ) -> ConnectorResult:
        endpoint = self._registry.get_endpoint(request.source_id, request.endpoint_key)
        if request.source_id != endpoint.source_id:
            request = ConnectorRequest(
                source_id=endpoint.source_id, endpoint_key=request.endpoint_key,
                acquisition_mode=request.acquisition_mode, parameters=request.parameters,
                requested_at=request.requested_at,
            )
        if request.acquisition_mode != AcquisitionMode.QUERY_THROUGH:
            raise ValueError("query broker only accepts query_through requests")
        if endpoint.acquisition_mode != request.acquisition_mode:
            raise ValueError("request mode does not match endpoint contract")
        # Validate requirements and arguments before cache/circuit/network activity.
        if cache_ttl_seconds is not None and cache_ttl_seconds < 0:
            raise ValueError("cache_ttl_seconds cannot be negative")
        from service.source_connectors.public_catalog import PARAMETER_MODELS, validate_public_request
        if (request.source_id, request.endpoint_key) in PARAMETER_MODELS:
            request = ConnectorRequest(
                source_id=request.source_id, endpoint_key=request.endpoint_key,
                acquisition_mode=request.acquisition_mode, requested_at=request.requested_at,
                parameters=validate_public_request(request.source_id, request.endpoint_key, request.parameters),
            )
        available = set(endpoint.capabilities.get("fields", ()))
        conditional = endpoint.capabilities.get("conditional_fields", {})
        if conditional:
            available -= {field for fields in conditional.values() for field in fields}
            available.update(conditional.get(request.parameters.get("kind"), ()))
        missing = set(required_fields) - available
        if missing:
            raise ValueError("endpoint cannot supply required fields: " + ", ".join(sorted(missing)))
        if require_point_in_time and endpoint.capabilities.get("point_in_time") is not True:
            raise ValueError("endpoint does not guarantee point-in-time data")
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
                        circuit.opened_until = self._clock() + self._cooldown
                    if allow_stale and cached and cached.stale_until > now:
                        return self._with_cache(cached.result, "stale")
                raise
            with self._lock:
                circuit.failures = 0
                circuit.opened_until = None
                ttl = (
                    endpoint.cache_ttl_seconds or 0
                    if cache_ttl_seconds is None
                    else cache_ttl_seconds
                )
                if ttl < 0:
                    raise ValueError("cache_ttl_seconds cannot be negative")
                if cache_key not in self._cache and len(self._cache) >= self._max_cache_entries:
                    self._cache.pop(next(iter(self._cache)))
                completed_at = self._clock()
                self._cache[cache_key] = _CacheEntry(
                    result=result,
                    expires_at=completed_at + timedelta(seconds=ttl),
                    stale_until=completed_at + timedelta(seconds=ttl) + self._stale_grace,
                )
            return self._with_cache(result, "miss")
