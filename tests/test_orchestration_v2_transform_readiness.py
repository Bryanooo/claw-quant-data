import pytest
from types import SimpleNamespace

from service.orchestration_v2.runtime import (
    allow_transform_owned_historical_validation,
    V2TransformationNotPublishableError,
    require_publishable_transformation,
)


def test_publishable_transformation_passes():
    require_publishable_transformation(
        {"dataset": "fama_french_daily", "status": "ready", "publishable": True}
    )


def test_diagnostic_transformation_cannot_publish_dataset_ready():
    with pytest.raises(
        V2TransformationNotPublishableError,
        match="status=insufficient_universe",
    ):
        require_publishable_transformation(
            {
                "dataset": "fama_french_daily",
                "status": "insufficient_universe",
                "publishable": False,
            }
        )


def test_historical_dependency_bypass_is_narrow_and_explicit():
    document = SimpleNamespace(task_key="fama_french_daily")
    execution = {
        "purpose": "backfill",
        "frozen_scope": {"historical_source_validation": "transform_owned"},
    }
    assert allow_transform_owned_historical_validation(document, execution)
    execution["purpose"] = "daily"
    assert not allow_transform_owned_historical_validation(document, execution)
    execution["purpose"] = "backfill"
    document.task_key = "technical_factor_snapshot"
    assert allow_transform_owned_historical_validation(document, execution)
    document.task_key = "market_breadth"
    assert not allow_transform_owned_historical_validation(document, execution)
