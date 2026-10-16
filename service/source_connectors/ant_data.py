"""Preferred name for the Ant provider; durable source_id remains financial_data."""
from service.source_connectors.financial_data import FinancialDataConnector, validate_common_query

AntDataConnector = FinancialDataConnector

__all__ = ["AntDataConnector", "validate_common_query"]
