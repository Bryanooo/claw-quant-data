from datetime import date, timedelta

from service.data_coverage.boundary_probe import build_boundary_probe_plan


def _trade_dates(end: date, count: int = 80):
    values = []
    cursor = end
    while len(values) < count:
        if cursor.weekday() < 5:
            values.append(cursor)
        cursor -= timedelta(days=1)
    return values


def test_boundary_probe_moves_newest_first_and_requires_an_older_anchor():
    earliest = date(2026, 9, 1)
    calendar = _trade_dates(earliest - timedelta(days=1))

    first = build_boundary_probe_plan(
        dataset_name="moneyflow",
        earliest_observed=earliest,
        trade_dates=calendar,
    )
    assert first.status == "probe"
    assert len(first.candidates) == 20
    assert list(first.candidates) == sorted(
        first.candidates, key=lambda item: item.end, reverse=True
    )

    empty = {item.key: "verified_empty" for item in first.candidates}
    anchor = build_boundary_probe_plan(
        dataset_name="moneyflow",
        earliest_observed=earliest,
        trade_dates=calendar,
        evidence=empty,
    )
    assert anchor.status == "probe_anchor"
    assert len(anchor.candidates) == 1

    empty[anchor.candidates[0].key] = "verified_empty"
    complete = build_boundary_probe_plan(
        dataset_name="moneyflow",
        earliest_observed=earliest,
        trade_dates=calendar,
        evidence=empty,
    )
    assert complete.status == "provisional_boundary"
    assert complete.provisional_boundary == earliest


def test_boundary_probe_never_treats_failures_as_empty():
    earliest = date(2026, 9, 1)
    calendar = _trade_dates(earliest - timedelta(days=1))
    initial = build_boundary_probe_plan(
        dataset_name="shibor",
        earliest_observed=earliest,
        trade_dates=calendar,
    )
    evidence = {item.key: "verified_empty" for item in initial.candidates}
    evidence[initial.candidates[0].key] = "failed"

    retry = build_boundary_probe_plan(
        dataset_name="shibor",
        earliest_observed=earliest,
        trade_dates=calendar,
        evidence=evidence,
    )
    assert retry.status == "retry_required"
    assert retry.candidates == (initial.candidates[0],)


def test_sparse_datasets_are_not_probed():
    plan = build_boundary_probe_plan(
        dataset_name="cashflow",
        earliest_observed=date(1995, 6, 30),
    )
    assert plan.status == "ineligible"
    assert plan.candidates == ()
