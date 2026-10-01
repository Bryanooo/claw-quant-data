"""Backward-compatible Tushare facade over provider-neutral raw evidence."""

from __future__ import annotations

from functools import lru_cache
from typing import Any, Callable

# Keep these imports public: existing tests and extensions patch the SDK
# module at this compatibility boundary.
import psycopg2
import psycopg2.extras

from service.source_connectors.contracts import AcquisitionMode
from service.source_connectors.raw_archive import (
    SourceRawArchive,
    canonical_json as _canonical_json,
    json_value as _json_value,
    safe_parameters as _safe_parameters,
    sha256_json as _sha256,
)
from service.tushare_catalog import InterfaceNotFoundError, TushareInterfaceCatalog


@lru_cache(maxsize=256)
def _source_doc_id(api_name: str) -> int | None:
    try:
        return TushareInterfaceCatalog().get(api_name).source_doc_id
    except InterfaceNotFoundError:
        return None


class TushareRawArchive(SourceRawArchive):
    """Keep the established API while recording explicit source lineage."""

    def __init__(self, connection_factory: Callable[[], Any] | None = None):
        super().__init__(
            source_id="tushare",
            acquisition_mode=AcquisitionMode.SCHEDULED_PULL,
            source_doc_resolver=_source_doc_id,
            connection_factory=connection_factory,
            legacy_tushare=True,
        )

    def archive_response(self, *, api_name: str, **kwargs):
        return super().archive_response(endpoint_key=api_name, **kwargs)

    def archive_failure(self, *, api_name: str, **kwargs) -> None:
        super().archive_failure(endpoint_key=api_name, **kwargs)

    def resolve_records(self, *, api_name: str, **kwargs) -> int:
        return super().resolve_records(endpoint_key=api_name, **kwargs)
