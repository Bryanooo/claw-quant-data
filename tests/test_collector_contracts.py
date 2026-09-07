from collections import Counter

from collectors.contracts import EmptyPolicy, PaginationMode, ResourceClass, WriteMode
from service.collector_catalog import discover_collectors


def test_every_concrete_collector_is_discoverable_and_targets_a_table():
    contracts = discover_collectors()

    # This is intentionally an exact invariant: adding/removing a collector
    # must be reviewed instead of silently weakening the catalog.
    assert len(contracts) == 98
    assert all(contract.table_name for contract in contracts)
    assert len({contract.qualified_name for contract in contracts}) == len(contracts)


def test_generic_collectors_declare_api_and_primary_key_contracts():
    generic = [contract for contract in discover_collectors() if contract.uses_generic_store]

    missing_api = [item.qualified_name for item in generic if not item.api_name]
    missing_keys = [item.qualified_name for item in generic if not item.primary_keys]
    assert missing_api == []
    assert missing_keys == []


def test_collector_targets_have_one_canonical_implementation():
    contracts = discover_collectors()
    duplicates = {
        table: count
        for table, count in Counter(item.table_name for item in contracts).items()
        if count > 1
    }
    assert duplicates == {}


def test_every_collector_declares_runtime_metadata():
    contracts = discover_collectors()

    assert all(isinstance(item.write_mode, WriteMode) for item in contracts)
    assert all(isinstance(item.pagination_mode, PaginationMode) for item in contracts)
    assert all(isinstance(item.empty_policy, EmptyPolicy) for item in contracts)
    assert all(isinstance(item.resource_class, ResourceClass) for item in contracts)
    assert all(item.version for item in contracts)


def test_finance_collectors_use_the_standard_runtime_contract():
    finance = [
        item for item in discover_collectors()
        if item.resource_class is ResourceClass.FINANCE
    ]

    assert len(finance) == 8
    assert all(item.pagination_mode is PaginationMode.OFFSET for item in finance)
    assert all(item.required_parameters == ("period",) for item in finance)


def test_share_float_identity_preserves_distinct_announcements():
    contract = next(
        item for item in discover_collectors() if item.api_name == "share_float"
    )

    assert contract.primary_keys == (
        "ts_code",
        "ann_date",
        "float_date",
        "holder_name",
        "share_type",
    )
