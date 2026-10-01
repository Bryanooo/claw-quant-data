from scripts.generate_dataset_audit_report import classify_repair_state


def _state(**overrides):
    values = {
        "active": 0,
        "has_problem": True,
        "dataset_name": "example",
        "boundary_unverified_count": 0,
        "current_problem_count": 0,
        "stale_problem_count": 0,
        "automatic_safe": True,
        "latest_status": "unverified",
        "current_attention": 0,
    }
    values.update(overrides)
    return classify_repair_state(**values)


def test_observed_scope_without_global_calendar_is_not_called_missing():
    assert _state() == "observed_scope_not_globally_provable"


def test_partial_data_after_a_real_retry_stays_actionable():
    assert _state(
        current_problem_count=2,
        current_attention=1,
        latest_status="gaps",
    ) == "attention_after_retry"


def test_history_boundary_and_manual_scope_have_distinct_actions():
    assert _state(boundary_unverified_count=10) == "history_boundary_review"
    assert _state(automatic_safe=False) == "manual_scope_required"
