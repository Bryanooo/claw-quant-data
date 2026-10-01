"""Tushare adapter for the provider-neutral connector contract."""

from __future__ import annotations

from service.source_connectors.contracts import (
    AcquisitionMode,
    ConnectorRequest,
    ConnectorResult,
)
from service.source_connectors.registry import TUSHARE_SOURCE


class TushareConnector:
    source = TUSHARE_SOURCE

    def execute(self, request: ConnectorRequest) -> ConnectorResult:
        if request.source_id != self.source.source_id:
            raise ValueError("request source does not match Tushare connector")
        if request.acquisition_mode != AcquisitionMode.SCHEDULED_PULL:
            raise ValueError("Tushare connector requires scheduled_pull mode")
        # Lazy import keeps the connector contract independent from the job
        # runtime and avoids an import cycle during registry construction.
        from service.acquisition_runtime.registry import (
            TaskExecutionResult,
            TushareInterfaceParameters,
            _run_tushare_interface,
        )

        options = dict(request.parameters)
        raw_parameters = dict(options.pop("parameters", {}))
        result = _run_tushare_interface(TushareInterfaceParameters(
            api_name=request.endpoint_key,
            parameters=raw_parameters,
            **options,
        ))
        if not isinstance(result, TaskExecutionResult):
            return ConnectorResult(
                source_id=request.source_id,
                endpoint_key=request.endpoint_key,
                acquisition_mode=request.acquisition_mode,
                stored_rows=int(result),
                status="unverified",
            )
        return ConnectorResult(
            source_id=request.source_id,
            endpoint_key=request.endpoint_key,
            acquisition_mode=request.acquisition_mode,
            fetched_rows=result.rows_fetched or 0,
            stored_rows=result.rows_inserted,
            status=result.completion_status,
            evidence=result.completion_evidence,
        )
