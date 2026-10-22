"""In-process TTL cache for read-only aggregate endpoints.

The dashboard polls several aggregate endpoints every 30 seconds.  Most of the
cost inside those endpoints is recomputing registry-level summaries (catalog,
capability matrix, coverage roll-up, health roll-up) that only change when a
collection cycle writes data — typically once per day.  Recomputing them on
every poll wastes seconds of CPU per request.

The cache follows a stale-while-revalidate policy: an expired value is still
returned immediately while a background thread recomputes it.  Dashboards stay
responsive and never wait for a slow roll-up; callers that need a guaranteed
fresh read pass ``force=True``.  Concurrent callers of a cold key share a single
computation (single flight) so a startup warm-up and the first page request do
not duplicate the same multi-second query.
"""

from __future__ import annotations

import threading
import time
from collections import OrderedDict
from typing import Any, Callable, Hashable


class TTLCache:
    """Thread-safe LRU cache with TTL, background revalidation and single flight."""

    def __init__(self, ttl_seconds: float, max_entries: int = 32) -> None:
        self.ttl_seconds = float(ttl_seconds)
        self.max_entries = max(1, int(max_entries))
        self._entries: OrderedDict[Hashable, tuple[float, Any]] = OrderedDict()
        self._refreshing: set[Hashable] = set()
        self._inflight: dict[Hashable, threading.Event] = {}
        self._lock = threading.Lock()

    # -- primitives ---------------------------------------------------------
    def _peek(self, key: Hashable) -> tuple[bool, Any]:
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                return False, None
            expires_at, value = entry
            self._entries.move_to_end(key)
            return expires_at > time.monotonic(), value

    def get(self, key: Hashable) -> Any | None:
        _, value = self._peek(key)
        return value

    def set(self, key: Hashable, value: Any) -> None:
        expires_at = time.monotonic() + self.ttl_seconds
        with self._lock:
            self._entries[key] = (expires_at, value)
            self._entries.move_to_end(key)
            while len(self._entries) > self.max_entries:
                self._entries.popitem(last=False)

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()
            self._refreshing.clear()

    def _claim(self, key: Hashable) -> tuple[threading.Event, bool]:
        with self._lock:
            pending = self._inflight.get(key)
            if pending is not None:
                return pending, False
            pending = threading.Event()
            self._inflight[key] = pending
            return pending, True

    def _release(self, key: Hashable, pending: threading.Event) -> None:
        with self._lock:
            self._inflight.pop(key, None)
        pending.set()

    # -- public API ---------------------------------------------------------
    def get_or_compute(
        self,
        key: Hashable,
        factory: Callable[[], Any],
        *,
        force: bool = False,
    ) -> Any:
        fresh, value = self._peek(key) if not force else (False, None)
        if value is not None:
            if not fresh:
                self._revalidate_in_background(key, factory)
            return value

        pending, owner = self._claim(key)
        if not owner:
            pending.wait(timeout=60)
            cached = self.get(key)
            if cached is not None:
                return cached
            pending, owner = self._claim(key)
            if not owner:
                # Coordination keeps failing (owner crashed twice); compute
                # directly rather than blocking a request forever.
                return factory()
        try:
            computed = factory()
            self.set(key, computed)
            return computed
        finally:
            self._release(key, pending)

    def _revalidate_in_background(self, key: Hashable, factory: Callable[[], Any]) -> None:
        with self._lock:
            if key in self._refreshing:
                return
            self._refreshing.add(key)

        def worker() -> None:
            try:
                self.set(key, factory())
            except Exception:  # keep serving the stale value on failure
                pass
            finally:
                with self._lock:
                    self._refreshing.discard(key)

        threading.Thread(target=worker, name=f"ttl-refresh-{key}", daemon=True).start()
