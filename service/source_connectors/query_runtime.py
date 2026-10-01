"""Process-wide query-through broker shared by REST and canonical adapters."""

from service.source_connectors import SOURCE_CONNECTORS
from service.source_connectors.query_broker import QueryBroker
from service.source_connectors.registry import SOURCE_REGISTRY


QUERY_BROKER = QueryBroker(
    registry=SOURCE_REGISTRY,
    connector_resolver=SOURCE_CONNECTORS.get,
)
