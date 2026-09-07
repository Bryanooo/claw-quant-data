"""Machine-readable Tushare interface contracts used by collectors and jobs."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import json
from pathlib import Path
from typing import Any

from service.config import PROJECT_ROOT


CONTRACTS_PATH = PROJECT_ROOT / "docs" / "tushare" / "contracts.json"


class InterfaceCatalogError(ValueError):
    """Base error for a rejected catalog operation."""


class InterfaceNotFoundError(InterfaceCatalogError):
    pass


class InterfaceNotCollectableError(InterfaceCatalogError):
    pass


@dataclass(frozen=True, slots=True)
class TushareInterfaceContract:
    api_name: str
    title: str
    category: str
    category_path: str
    description: str
    read_only: bool
    collectable: bool
    input_parameters: tuple[dict[str, str], ...]
    output_parameters: tuple[dict[str, str], ...]
    permission: dict[str, Any]
    implementation: dict[str, Any]
    document_ids: tuple[int, ...]

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "TushareInterfaceContract":
        return cls(
            api_name=value["api_name"],
            title=value["title"],
            category=value["category"],
            category_path=value["category_path"],
            description=value["description"],
            read_only=bool(value["read_only"]),
            collectable=bool(value["collectable"]),
            input_parameters=tuple(value["input_parameters"]),
            output_parameters=tuple(value["output_parameters"]),
            permission=dict(value["permission"]),
            implementation=dict(value["implementation"]),
            document_ids=tuple(value["doc_ids"]),
        )

    @property
    def source_doc_id(self) -> int | None:
        return self.document_ids[0] if self.document_ids else None


class TushareInterfaceCatalog:
    def __init__(self, contracts: tuple[TushareInterfaceContract, ...] | None = None):
        values = contracts if contracts is not None else load_contracts()
        self._contracts = {item.api_name: item for item in values}

    def list(self) -> tuple[TushareInterfaceContract, ...]:
        return tuple(sorted(self._contracts.values(), key=lambda item: item.api_name))

    def get(self, api_name: str) -> TushareInterfaceContract:
        try:
            return self._contracts[api_name]
        except KeyError as exc:
            raise InterfaceNotFoundError(
                f"Tushare interface is not registered: {api_name}"
            ) from exc

    def require_collectable(self, api_name: str) -> TushareInterfaceContract:
        contract = self.get(api_name)
        if not contract.collectable:
            reason = contract.permission.get("status", "unknown")
            if not contract.read_only:
                reason = "write interface; collection is intentionally disabled"
            raise InterfaceNotCollectableError(
                f"Tushare interface {api_name} is not collectable: {reason}"
            )
        return contract


@lru_cache(maxsize=1)
def load_contracts() -> tuple[TushareInterfaceContract, ...]:
    if not CONTRACTS_PATH.exists():
        raise RuntimeError(
            f"Tushare contract catalog is missing: {CONTRACTS_PATH}; "
            "run scripts/audit_tushare_interfaces.py"
        )
    payload = json.loads(CONTRACTS_PATH.read_text(encoding="utf-8"))
    return tuple(
        TushareInterfaceContract.from_dict(item) for item in payload["interfaces"]
    )


@lru_cache(maxsize=1)
def get_catalog() -> TushareInterfaceCatalog:
    return TushareInterfaceCatalog()
