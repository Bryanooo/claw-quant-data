"""Stable contracts shared by APIs, websites, query-through and stream sources."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
import re
from types import MappingProxyType
from typing import Any, Mapping, Protocol


class AcquisitionMode(StrEnum):
    SCHEDULED_PULL = "scheduled_pull"
    WEB_SNAPSHOT = "web_snapshot"
    QUERY_THROUGH = "query_through"
    STREAM = "stream"


class SourceKind(StrEnum):
    API = "api"
    WEBSITE = "website"
    FILE = "file"
    STREAM = "stream"
    HYBRID = "hybrid"


@dataclass(frozen=True, slots=True)
class SourceSpec:
    source_id: str
    display_name: str
    kind: SourceKind
    acquisition_modes: tuple[AcquisitionMode, ...]
    credential_ref: str | None = None
    base_url: str | None = None
    timezone: str = "UTC"
    license_policy: Mapping[str, Any] = field(default_factory=dict)
    configuration: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not re.fullmatch(r"[a-z][a-z0-9_-]{1,63}", self.source_id):
            raise ValueError(f"invalid source_id: {self.source_id}")
        if not self.display_name.strip():
            raise ValueError("source display_name is required")
        if not self.acquisition_modes:
            raise ValueError("source must declare at least one acquisition mode")
        if len(set(self.acquisition_modes)) != len(self.acquisition_modes):
            raise ValueError("source acquisition modes must be unique")
        object.__setattr__(self, "license_policy", MappingProxyType(dict(
            self.license_policy
        )))
        object.__setattr__(self, "configuration", MappingProxyType(dict(
            self.configuration
        )))


@dataclass(frozen=True, slots=True)
class EndpointSpec:
    source_id: str
    endpoint_key: str
    title: str
    acquisition_mode: AcquisitionMode
    resource_class: str = "default"
    cadence: str | None = None
    parser_name: str | None = None
    parser_version: str | None = None
    cache_ttl_seconds: int | None = None
    request_contract: Mapping[str, Any] = field(default_factory=dict)
    completeness_policy: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_.:-]*", self.endpoint_key):
            raise ValueError(f"invalid endpoint_key: {self.endpoint_key}")
        if self.cache_ttl_seconds is not None and self.cache_ttl_seconds < 0:
            raise ValueError("cache_ttl_seconds must not be negative")
        object.__setattr__(self, "request_contract", MappingProxyType(dict(
            self.request_contract
        )))
        object.__setattr__(self, "completeness_policy", MappingProxyType(dict(
            self.completeness_policy
        )))


@dataclass(frozen=True, slots=True)
class ConnectorRequest:
    source_id: str
    endpoint_key: str
    acquisition_mode: AcquisitionMode
    parameters: Mapping[str, Any] = field(default_factory=dict)
    requested_at: datetime | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "parameters", MappingProxyType(dict(
            self.parameters
        )))


@dataclass(frozen=True, slots=True)
class ConnectorResult:
    source_id: str
    endpoint_key: str
    acquisition_mode: AcquisitionMode
    records: tuple[Mapping[str, Any], ...] = ()
    fetched_rows: int = 0
    stored_rows: int = 0
    status: str = "unverified"
    evidence: Mapping[str, Any] = field(default_factory=dict)
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "records", tuple(
            MappingProxyType(dict(record)) for record in self.records
        ))
        object.__setattr__(self, "evidence", MappingProxyType(dict(
            self.evidence
        )))


class SourceConnector(Protocol):
    source: SourceSpec

    def execute(self, request: ConnectorRequest) -> ConnectorResult:
        """Execute one bounded acquisition request."""


class QueryThroughConnector(Protocol):
    source: SourceSpec

    def query(self, request: ConnectorRequest) -> ConnectorResult:
        """Execute one latency-bounded read-through request."""
