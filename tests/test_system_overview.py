from service.api.app import create_app
from service.system_overview import (
    SYSTEM_OVERVIEW_SCHEMA,
    build_system_overview,
)


class FakeDatabase:
    def close(self):
        pass


def test_system_overview_is_registered_as_the_cross_layer_authority():
    paths = create_app(database_factory=FakeDatabase).openapi()["paths"]

    assert "get" in paths["/api/v1/system/overview"]


def test_system_overview_keeps_non_equivalent_counts_separate():
    result = build_system_overview(
        public_catalog={
            "summary": {
                "raw_interfaces": 201,
                "standard_datasets": 192,
                "research_endpoints": 29,
            }
        },
        data_health={
            "status": "warning",
            "summary": {
                "ready_dataset_states": 180,
                "latest_dataset_states": 192,
                "open_issues": 12,
                "operator_action_required": 2,
                "active_task_instances": 3,
            },
        },
    )

    assert result["schema_version"] == SYSTEM_OVERVIEW_SCHEMA
    assert result["authorities"]["public_service_catalog"] == "/api/v1/catalog"
    assert result["inventory"]["financial_data"]["whitelisted_routes"] == 163
    assert result["inventory"]["financial_data"]["canonical_adapters_ready"] == 29
    assert result["inventory"]["financial_data"]["research_evidence_routes"] == 7
    assert result["inventory"]["public_services"] == {
        "raw_interfaces": 201,
        "standard_datasets": 192,
        "research_endpoints": 29,
    }
    assert result["runtime"]["summary"]["open_issues"] == 12
    assert result["runtime"]["details_url"] == "/api/v1/ops/data-health"
    assert len(result["number_definitions"]) == 4
    assert "不能相互等同" in result["boundaries"][0]


def test_system_overview_declares_agent_and_product_boundaries():
    result = build_system_overview(
        public_catalog={"summary": {}},
        data_health={"status": "healthy", "summary": {}},
    )

    assert result["positioning"]["agent_entrypoint"] == "/api/v1/research"
    assert "不能覆盖本地事实" in result["positioning"]["primary_data_rule"]
    assert [item["id"] for item in result["architecture"]] == [
        "sources",
        "production",
        "canonical",
        "research",
        "agents",
    ]
    assert any("回测" in item for item in result["boundaries"])
