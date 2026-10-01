"""Dataset partition-coverage auditing.

Keep the package initializer dependency-light.  The repair service imports the
V2 gap planner, while the planner imports the coverage registry; eagerly
importing :mod:`service.data_coverage.service` here would therefore make the
standalone V2 repair CLI depend on import order.
"""

from service.data_coverage.registry import COVERAGE_RULES

__all__ = ["COVERAGE_RULES", "CoverageService"]


def __getattr__(name: str):
    if name == "CoverageService":
        from service.data_coverage.service import CoverageService

        return CoverageService
    raise AttributeError(name)
