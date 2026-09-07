"""Static discovery and metadata for concrete collector classes."""

from __future__ import annotations

from dataclasses import dataclass
import importlib
import inspect
from pathlib import Path
from functools import lru_cache

import collectors
from collectors.base import BaseCollector
from collectors.contracts import EmptyPolicy, PaginationMode, ResourceClass, WriteMode


@dataclass(frozen=True)
class CollectorContract:
    qualified_name: str
    api_name: str
    table_name: str
    primary_keys: tuple[str, ...]
    uses_generic_store: bool
    write_mode: WriteMode
    pagination_mode: PaginationMode
    empty_policy: EmptyPolicy
    resource_class: ResourceClass
    version: str
    required_parameters: tuple[str, ...]


def _first_value(cls: type, modern: str, legacy: str, default):
    value = getattr(cls, modern, default)
    return value if value else getattr(cls, legacy, default)


@lru_cache(maxsize=1)
def discover_collector_classes() -> tuple[type[BaseCollector], ...]:
    """Return concrete collector classes without constructing clients."""
    classes: list[type[BaseCollector]] = []
    package_root = Path(next(iter(collectors.__path__)))
    module_names = sorted(
        ".".join((collectors.__name__, *path.relative_to(package_root).with_suffix("").parts))
        for path in package_root.rglob("*.py")
        if path.name != "__init__.py"
    )
    for module_name in module_names:
        module = importlib.import_module(module_name)
        for _, cls in inspect.getmembers(module, inspect.isclass):
            if (
                cls.__module__ == module.__name__
                and cls is not BaseCollector
                and issubclass(cls, BaseCollector)
                and cls.__name__.endswith("Collector")
                and cls.spec().table_name
            ):
                classes.append(cls)
    return tuple(sorted(classes, key=lambda cls: cls.spec().qualified_name))


def discover_collectors() -> tuple[CollectorContract, ...]:
    """Import collector modules and return contracts without constructing clients."""
    contracts: list[CollectorContract] = []
    for cls in discover_collector_classes():
        spec = cls.spec()
        table_name = spec.table_name
        api_name = spec.api_name
        if not table_name:
            continue
        keys = _first_value(cls, "pk_columns", "PK_COLUMNS", ())
        contracts.append(
            CollectorContract(
                qualified_name=spec.qualified_name,
                api_name=api_name,
                table_name=table_name,
                primary_keys=tuple(keys),
                uses_generic_store=cls.store is BaseCollector.store,
                write_mode=spec.write_mode,
                pagination_mode=spec.pagination_mode,
                empty_policy=spec.empty_policy,
                resource_class=spec.resource_class,
                version=spec.version,
                required_parameters=spec.required_parameters,
            )
        )
    return tuple(sorted(contracts, key=lambda item: item.qualified_name))


def resolve_collector_classes(api_name: str) -> tuple[type[BaseCollector], ...]:
    """Resolve direct and documented equivalent specialized implementations."""
    classes = discover_collector_classes()
    direct = tuple(cls for cls in classes if cls.spec().api_name == api_name)
    if direct:
        return direct

    from service.tushare_catalog import TushareInterfaceCatalog

    references = TushareInterfaceCatalog().get(api_name).implementation.get(
        "references", ()
    )
    modules = {
        reference.split(":", 1)[0][:-3].replace("/", ".")
        for reference in references
        if reference.split(":", 1)[0].endswith(".py")
    }
    qualified = {
        reference.replace("/", ".").replace(".py:", ".")
        for reference in references
        if ":" in reference
    }
    return tuple(
        cls
        for cls in classes
        if cls.spec().qualified_name in qualified or cls.__module__ in modules
    )
