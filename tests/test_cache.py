"""TTL cache keeps read-heavy endpoints fast without hiding data changes."""

from __future__ import annotations

import time

from service.cache import TTLCache


def test_cache_reuses_value_until_ttl_expires():
    cache = TTLCache(ttl_seconds=5, max_entries=2)
    calls = []

    def factory():
        calls.append(1)
        return {"value": len(calls)}

    first = cache.get_or_compute("k", factory)
    second = cache.get_or_compute("k", factory)
    assert first == second == {"value": 1}
    assert len(calls) == 1


def test_force_bypasses_cached_value():
    cache = TTLCache(ttl_seconds=60, max_entries=2)
    cache.get_or_compute("k", lambda: {"value": "cached"})
    refreshed = cache.get_or_compute("k", lambda: {"value": "fresh"}, force=True)
    assert refreshed == {"value": "fresh"}


def test_expired_entry_is_served_stale_then_revalidated():
    cache = TTLCache(ttl_seconds=0.01, max_entries=2)
    cache.get_or_compute("k", lambda: {"value": "old"})
    time.sleep(0.02)
    # The expired value is returned immediately ...
    assert cache.get_or_compute("k", lambda: {"value": "new"}) == {"value": "old"}
    # ... and the background refresh replaces it shortly after.
    for _ in range(50):
        if cache.get("k") == {"value": "new"}:
            break
        time.sleep(0.01)
    assert cache.get("k") == {"value": "new"}


def test_cache_evicts_least_recently_used_entry():
    cache = TTLCache(ttl_seconds=60, max_entries=2)
    cache.set("a", 1)
    cache.set("b", 2)
    cache.set("c", 3)
    assert cache.get("a") is None
    assert cache.get("b") == 2
