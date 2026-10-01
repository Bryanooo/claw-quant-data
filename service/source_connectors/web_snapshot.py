"""Website snapshot connector with immutable evidence and parser lineage."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Mapping

from service.source_connectors.contracts import (
    AcquisitionMode,
    ConnectorRequest,
    ConnectorResult,
    SourceSpec,
)
from service.source_connectors.raw_archive import SourceRawArchive
from service.source_connectors.registry import SourceRegistry


class WebFetchError(RuntimeError):
    pass


class ParserDriftError(RuntimeError):
    """The raw snapshot exists, but no longer satisfies the parser contract."""


@dataclass(frozen=True, slots=True)
class FetchedArtifact:
    url: str
    status_code: int
    content_type: str
    content: bytes
    headers: Mapping[str, str]
    fetched_at: datetime


class WebSnapshotConnector:
    def __init__(
        self,
        *,
        source: SourceSpec,
        registry: SourceRegistry,
        fetcher: Callable[[ConnectorRequest], FetchedArtifact],
        parser: Callable[[bytes, ConnectorRequest], tuple[Mapping, ...]],
        archive: SourceRawArchive,
    ):
        self.source = source
        self._registry = registry
        self._fetcher = fetcher
        self._parser = parser
        self._archive = archive

    def execute(self, request: ConnectorRequest) -> ConnectorResult:
        endpoint = self._registry.get_endpoint(request.source_id, request.endpoint_key)
        if request.source_id != self.source.source_id:
            raise ValueError("request source does not match connector")
        if request.acquisition_mode != AcquisitionMode.WEB_SNAPSHOT:
            raise ValueError("web snapshot connector requires web_snapshot mode")
        if endpoint.acquisition_mode != request.acquisition_mode:
            raise ValueError("request mode does not match endpoint contract")

        artifact = self._fetcher(request)
        if artifact.status_code < 200 or artifact.status_code >= 300:
            raise WebFetchError(
                f"{request.endpoint_key} returned HTTP {artifact.status_code}"
            )
        if not artifact.content:
            raise WebFetchError(f"{request.endpoint_key} returned an empty artifact")
        archived = self._archive.archive_artifact(
            endpoint_key=request.endpoint_key,
            source_url=artifact.url,
            content_type=artifact.content_type,
            content=artifact.content,
            http_status=artifact.status_code,
            response_headers=artifact.headers,
            parser_name=endpoint.parser_name,
            parser_version=endpoint.parser_version,
            fetched_at=artifact.fetched_at,
        )
        try:
            records = tuple(self._parser(artifact.content, request))
        except Exception as exc:
            raise ParserDriftError(
                f"parser {endpoint.parser_name or 'unknown'}@"
                f"{endpoint.parser_version or 'unknown'} failed for "
                f"{request.source_id}/{request.endpoint_key}; "
                f"artifact_id={archived['artifact_id']}: {exc}"
            ) from exc
        return ConnectorResult(
            source_id=request.source_id,
            endpoint_key=request.endpoint_key,
            acquisition_mode=request.acquisition_mode,
            records=records,
            fetched_rows=len(records),
            status="complete" if records else "empty",
            evidence={
                **archived,
                "source_url": artifact.url,
                "http_status": artifact.status_code,
                "parser_name": endpoint.parser_name,
                "parser_version": endpoint.parser_version,
            },
        )
