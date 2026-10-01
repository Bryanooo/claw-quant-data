"""HTTP route modules."""

from service.api.routers import (
    coverage,
    datasets,
    health,
    interfaces,
    normalization,
    orchestration_v2,
    sources,
    stocks,
)

__all__ = [
    "coverage",
    "datasets",
    "health",
    "interfaces",
    "normalization",
    "orchestration_v2",
    "sources",
    "stocks",
]
