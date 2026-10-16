"""Provider-neutral data-source connectors and acquisition contracts."""

from service.source_connectors.contracts import (
    AcquisitionMode,
    ConnectorRequest,
    ConnectorResult,
    EndpointSpec,
    SourceKind,
    SourceSpec,
)
from service.source_connectors.registry import SOURCE_CONNECTORS, SOURCE_REGISTRY
from service.source_connectors.chinamoney import ChinaMoneyConnector
from service.source_connectors.ant_data import AntDataConnector
from service.source_connectors.raw_archive import SourceRawArchive
from service.source_connectors.tushare import TushareConnector


if "tushare" not in SOURCE_CONNECTORS:
    SOURCE_CONNECTORS.register(TushareConnector())
if "chinamoney" not in SOURCE_CONNECTORS:
    SOURCE_CONNECTORS.register(ChinaMoneyConnector())
if "financial_data" not in SOURCE_CONNECTORS:
    SOURCE_CONNECTORS.register(AntDataConnector(
        archive=SourceRawArchive(
            source_id="financial_data",
            acquisition_mode=AcquisitionMode.QUERY_THROUGH,
        )
    ))

__all__ = [
    "AcquisitionMode",
    "ConnectorRequest",
    "ConnectorResult",
    "EndpointSpec",
    "SOURCE_CONNECTORS",
    "SOURCE_REGISTRY",
    "SourceKind",
    "SourceSpec",
]

from service.source_connectors.public_catalog import PUBLIC_SOURCES
from service.source_connectors.public_web import PublicWebConnector

for _source in PUBLIC_SOURCES:
    if _source.source_id not in SOURCE_CONNECTORS:
        SOURCE_CONNECTORS.register(PublicWebConnector(
            _source, archive=SourceRawArchive(
                source_id=_source.source_id, acquisition_mode=AcquisitionMode.QUERY_THROUGH,
            ),
        ))
