from scripts.audit_october_factor_readiness import stored_quality_ready
from datetime import date
from unittest.mock import MagicMock, patch


def test_no_calendar_or_no_daily_source_cannot_pass():
    assert not stored_quality_ready([])
    assert not stored_quality_ready([dict(expected_securities=0,
                                         present_securities=0, unready_securities=0)])


def test_complete_row_coverage_does_not_imply_ready():
    assert not stored_quality_ready([dict(expected_securities=5,
                                         present_securities=5, unready_securities=1)])


def test_missing_security_cannot_pass_even_without_problem_counter():
    assert not stored_quality_ready([dict(expected_securities=5,
                                         present_securities=4, unready_securities=0)])


def test_every_day_must_pass():
    good = dict(expected_securities=5, present_securities=5, unready_securities=0)
    assert stored_quality_ready([good, good])
    assert not stored_quality_ready([good, dict(good, unready_securities=1)])


def test_comparative_audit_does_not_invent_gaps_by_clipping_source_history():
    from scripts.audit_october_factor_readiness import comparative_statement_gaps
    connection = MagicMock()
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.fetchall.return_value = []
    with patch('scripts.audit_october_factor_readiness.get_conn', return_value=connection):
        assert comparative_statement_gaps(date(2026,10,30)) == []
    sql, parameters = cursor.execute.call_args.args
    assert 'end_date >=' not in sql
    assert 'report_exists_but_not_available_at_cutoff' in sql
    assert parameters == (date(2026,10,30),) * 3
    connection.set_session.assert_called_once_with(readonly=True)
    connection.close.assert_called_once()


def test_financial_freshness_fails_closed_without_completed_compute():
    from scripts.audit_october_factor_readiness import financial_input_freshness
    connection = MagicMock()
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.fetchone.return_value = None
    with patch('scripts.audit_october_factor_readiness.get_conn', return_value=connection):
        assert financial_input_freshness(1)['status'] == 'missing_compute_evidence'
    connection.close.assert_called_once()


def test_financial_freshness_checks_both_current_and_lagged_statements():
    from scripts.audit_october_factor_readiness import financial_input_freshness
    connection = MagicMock()
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.fetchone.side_effect = [({'snapshot_date':'2026-10-30',
        'financial_input_digests':['new']*4,
        'lag63_input':{'financial_input_digests':['old']*4}},), (date(2026,7,29),)]
    with patch('scripts.audit_october_factor_readiness.get_conn', return_value=connection), \
         patch('service.research.local_factors.materializer._statement_rows') as read, \
         patch('service.research.local_factors.materializer.frame_digest', return_value='new'):
        result = financial_input_freshness(1)
    assert result['status'] == 'not_verified'
    assert [c['status'] for c in result['checks']] == ['matching']*4 + ['stale']*4
    assert read.call_count == 8
