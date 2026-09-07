"""Dataset partition-coverage auditing."""

from service.data_coverage.registry import COVERAGE_RULES
from service.data_coverage.service import CoverageService

__all__ = ["COVERAGE_RULES", "CoverageService"]
