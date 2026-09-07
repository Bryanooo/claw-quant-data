"""Discovery and typed querying for catalog-backed Tushare interfaces."""

from __future__ import annotations

from service.collector_catalog import discover_collectors
from service.data_service.models import InterfaceDataNotFoundError, InvalidQueryError
from service.data_service.registry import DatasetRegistry
from service.data_service.service import DataService
from service.tushare_catalog import (
    InterfaceNotFoundError,
    TushareInterfaceCatalog,
    TushareInterfaceContract,
)
from service.tushare_normalization import NORMALIZATION_CONTRACTS


def _collector_reference(qualified_name: str) -> tuple[str, str]:
    module, class_name = qualified_name.rsplit(".", 1)
    return module, f"{module.replace('.', '/')}.py:{class_name}"


def _contract_tables() -> dict[str, tuple[str, ...]]:
    """Resolve normal and equivalent APIs to their normalized collector tables."""
    collectors = discover_collectors()
    by_api: dict[str, set[str]] = {}
    by_module: dict[str, set[str]] = {}
    by_reference: dict[str, set[str]] = {}
    for collector in collectors:
        if collector.api_name:
            by_api.setdefault(collector.api_name, set()).add(collector.table_name)
        module, reference = _collector_reference(collector.qualified_name)
        by_module.setdefault(module, set()).add(collector.table_name)
        by_reference.setdefault(reference, set()).add(collector.table_name)

    resolved: dict[str, tuple[str, ...]] = {}
    for contract in TushareInterfaceCatalog().list():
        tables = set(by_api.get(contract.api_name, ()))
        for reference in contract.implementation.get("references", ()):
            tables.update(by_reference.get(reference, ()))
            module_reference = reference.split(":", 1)[0]
            if module_reference.endswith(".py"):
                module = module_reference[:-3].replace("/", ".")
                tables.update(by_module.get(module, ()))
        resolved[contract.api_name] = tuple(sorted(tables))
    return resolved


class InterfaceDataService:
    def __init__(
        self,
        repository,
        registry: DatasetRegistry,
        catalog: TushareInterfaceCatalog | None = None,
    ):
        self._registry = registry
        self._catalog = catalog or TushareInterfaceCatalog()
        self._data_service = DataService(repository, registry)
        self._tables = _contract_tables()
        self._dataset_names_by_table = {
            item.table: item.name for item in registry.list()
        }
        self._normalization = {
            item.api_name: item for item in NORMALIZATION_CONTRACTS.list()
        }

    def list_interfaces(self) -> list[dict]:
        return [
            self._summary(contract)
            for contract in self._catalog.list()
            if contract.collectable
        ]

    def describe_interface(self, api_name: str) -> dict:
        contract = self._require_collectable(api_name)
        output_fields = self._output_fields(contract)
        normalization = self._normalization.get(api_name)
        date_fields = (
            [field.name for field in normalization.fields if field.sql_type == "DATE"]
            if normalization
            else [
                name
                for name in (
                    "trade_date",
                    "cal_date",
                    "ann_date",
                    "end_date",
                    "report_date",
                    "nav_date",
                    "date",
                )
                if name in output_fields
            ]
        )
        return {
            **self._summary(contract),
            "description": contract.description,
            "document_urls": [
                f"https://tushare.pro/document/2?doc_id={doc_id}"
                for doc_id in contract.document_ids
            ],
            "input_parameters": list(contract.input_parameters),
            "output_parameters": list(contract.output_parameters),
            "allowed_filters": sorted(output_fields | {"_record_hash"}),
            "date_fields": date_fields,
        }

    def query_records(
        self,
        api_name: str,
        *,
        filters: dict[str, str],
        date_field: str | None,
        date_value: str | None,
        start_date: str | None,
        end_date: str | None,
        limit: int,
        offset: int,
        include_total: bool,
    ) -> dict:
        contract = self._require_collectable(api_name)
        if contract.implementation.get("mode") != "generic_raw":
            datasets = self._dataset_names(contract)
            raise InvalidQueryError(
                f"interface {api_name} uses normalized datasets: "
                f"{', '.join(datasets) or 'none'}"
            )
        dataset = self._registry.get(api_name)
        if date_field and date_field != dataset.date_column:
            raise InvalidQueryError(
                f"date ranges for {api_name} use {dataset.date_column or 'no date field'}; "
                "use exact filters for other date columns"
            )
        result = self._data_service.query_dataset(
            api_name,
            exact_filters=filters,
            date_value=date_value,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
            offset=offset,
            include_total=include_total,
        )
        return {
            "data": result["data"],
            "meta": {
                "interface": api_name,
                "storage": dataset.table,
                "read_view": dataset.current_view,
                "returned": result["meta"]["returned"],
                "date_field": dataset.date_column,
            },
            "page": result["page"],
        }

    def _summary(self, contract: TushareInterfaceContract) -> dict:
        mode = contract.implementation.get("mode", "unknown")
        return {
            "api_name": contract.api_name,
            "title": contract.title,
            "category": contract.category,
            "permission_status": contract.permission.get("status", "unknown"),
            "implementation_mode": mode,
            "storage_mode": (
                "typed_standard_and_raw"
                if mode == "generic_raw"
                else "specialized_normalized"
            ),
            "datasets": self._dataset_names(contract),
            "records_url": (
                f"/api/v1/interfaces/{contract.api_name}/records"
                if mode == "generic_raw"
                else None
            ),
        }

    def _dataset_names(self, contract: TushareInterfaceContract) -> list[str]:
        if contract.implementation.get("mode") == "generic_raw":
            return [contract.api_name, "tushare_raw"]
        return [
            self._dataset_names_by_table[table]
            for table in self._tables.get(contract.api_name, ())
            if table in self._dataset_names_by_table
        ]

    def _require_collectable(self, api_name: str) -> TushareInterfaceContract:
        try:
            contract = self._catalog.get(api_name)
        except InterfaceNotFoundError as exc:
            raise InterfaceDataNotFoundError(str(exc)) from exc
        if not contract.collectable:
            raise InvalidQueryError(f"interface {api_name} is not collectable")
        return contract

    @staticmethod
    def _output_fields(contract: TushareInterfaceContract) -> set[str]:
        return {
            str(parameter["name"])
            for parameter in contract.output_parameters
            if parameter.get("name")
        }
