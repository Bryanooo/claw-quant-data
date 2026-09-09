from service.data_service.registry import DATASETS
from service.tushare_normalization import (
    NORMALIZATION_CONTRACTS,
    normalized_table_name,
)


def test_all_generic_interfaces_have_typed_normalization_contracts():
    contracts = NORMALIZATION_CONTRACTS.list()

    assert len(contracts) == 95
    assert len({contract.api_name for contract in contracts}) == 95
    assert len({contract.table_name for contract in contracts}) == 95
    assert all(contract.fields for contract in contracts)
    assert all(
        contract.table_name == normalized_table_name(contract.api_name)
        for contract in contracts
    )


def test_normalization_contract_uses_semantic_postgres_types():
    contract = NORMALIZATION_CONTRACTS.get("adj_factor")
    fields = {field.name: field.sql_type for field in contract.fields}

    assert fields == {
        "ts_code": "TEXT",
        "trade_date": "DATE",
        "adj_factor": "NUMERIC",
    }
    assert contract.date_column == "trade_date"
    assert contract.identity_fields == ("trade_date", "ts_code")
    assert contract.business_identity_fields == ("trade_date", "ts_code")
    assert contract.identity_confidence == "heuristic"


def test_multidimensional_business_identity_is_contract_reviewed():
    contract = NORMALIZATION_CONTRACTS.get("fut_holding")

    assert contract.identity_fields == ("trade_date", "symbol")
    assert contract.business_identity_fields == (
        "trade_date",
        "symbol",
        "broker",
    )
    assert contract.identity_confidence == "contract_reviewed"


def test_every_typed_contract_is_exposed_as_a_dataset():
    registered = {dataset.table: dataset for dataset in DATASETS.list()}

    for contract in NORMALIZATION_CONTRACTS.list():
        dataset = registered[contract.table_name]
        assert dataset.name == contract.api_name
        assert dataset.primary_keys == ("_record_hash",)
        assert set(contract.field_names) <= set(dataset.exact_filters)
