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
from service.source_connectors.financial_data import FinancialDataConnector
from service.source_connectors.tushare import TushareConnector


if "tushare" not in SOURCE_CONNECTORS:
    SOURCE_CONNECTORS.register(TushareConnector())
if "chinamoney" not in SOURCE_CONNECTORS:
    SOURCE_CONNECTORS.register(ChinaMoneyConnector())
if "financial_data" not in SOURCE_CONNECTORS:
    SOURCE_CONNECTORS.register(FinancialDataConnector())

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
