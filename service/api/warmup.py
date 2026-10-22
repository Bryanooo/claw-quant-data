"""Warm the dashboard's aggregate caches during API startup.

The overview, health roll-up, catalog and capability matrix each walk a large
part of the control plane.  Their values only change when a collection cycle
writes data, so the API caches them (see :mod:`service.cache`).  Computing them
once in the background at startup keeps the first page view fast instead of
making the first operator pay several seconds of roll-up latency.
"""

from __future__ import annotations

import logging
import threading
from types import SimpleNamespace
from typing import Any

logger = logging.getLogger("api.warmup")


class _RequestStub:
    """Minimal stand-in exposing only what the dependency helpers read."""

    def __init__(self, database: Any) -> None:
        self.app = SimpleNamespace(state=SimpleNamespace(database=database))


def warm_dashboard_caches(database: Any) -> None:
    """Populate aggregate caches once; safe to call in a background thread."""

    from service.api.dependencies import (
        get_data_health_service,
        get_data_service,
        get_interface_data_service,
        get_raw_archive_service,
        get_research_service,
    )
    from service.api.routers.catalog import _CATALOG_CACHE
    from service.api.routers.data_health import _HEALTH_CACHE
    from service.api.routers.research import _CAPABILITIES_CACHE
    from service.api.routers.system import _OVERVIEW_CACHE
    from service.data_service.catalog import build_data_service_catalog
    from service.system_overview import build_system_overview

    request = _RequestStub(database)

    def build_catalog() -> dict:
        return build_data_service_catalog(
            raw_interfaces=get_raw_archive_service(request).list_interfaces(),
            datasets=get_data_service(request).list_datasets(),
            interfaces=get_interface_data_service(request).list_interfaces(),
        )

    def build_health() -> dict:
        return get_data_health_service(request).overview()

    def build_capabilities() -> dict:
        return get_research_service(request).capabilities()

    def build_overview() -> dict:
        # Reuse the freshly warmed pieces instead of recomputing them.
        catalog = _CATALOG_CACHE.get("catalog") or build_catalog()
        health = _HEALTH_CACHE.get("overview") or build_health()
        return build_system_overview(public_catalog=catalog, data_health=health)

    steps = (
        ("catalog", _CATALOG_CACHE, "catalog", build_catalog),
        ("health", _HEALTH_CACHE, "overview", build_health),
        ("capabilities", _CAPABILITIES_CACHE, "capabilities", build_capabilities),
    )
    # The three independent roll-ups run concurrently; the overview only
    # stitches them together, so it is built once they are cached.
    threads = [
        threading.Thread(
            target=_warm_one,
            args=(label, cache, key, builder),
            name=f"warm-{label}",
            daemon=True,
        )
        for label, cache, key, builder in steps
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    _warm_one("overview", _OVERVIEW_CACHE, "overview", build_overview)


def _warm_one(label: str, cache, key, builder) -> None:
    try:
        cache.get_or_compute(key, builder, force=True)
    except Exception:  # warm-up is best effort; requests degrade gracefully
        logger.warning("cache warm-up failed for %s", label, exc_info=True)


def schedule_warmup(database: Any) -> threading.Thread:
    thread = threading.Thread(
        target=warm_dashboard_caches,
        args=(database,),
        name="dashboard-cache-warmup",
        daemon=True,
    )
    thread.start()
    return thread
