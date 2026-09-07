"""HTTP route modules."""

from service.api.routers import (
    collection_jobs,
    coverage,
    datasets,
    health,
    interfaces,
    normalization,
    stocks,
)

__all__ = [
    "collection_jobs",
    "coverage",
    "datasets",
    "health",
    "interfaces",
    "normalization",
    "stocks",
]
