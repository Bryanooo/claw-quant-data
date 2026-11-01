from datetime import date
from unittest.mock import MagicMock, patch
import pytest
from scripts.cleanup_factor_reference import clean


def test_october_cannot_be_deleted():
    with pytest.raises(ValueError,match='protected'):
        clean(date(2026,10,8),apply=True)


def test_unbounded_cleanup_rejected():
    with pytest.raises(ValueError,match='limits'):
        clean(date(2026,9,1),apply=True,max_rows=100001)


def test_no_deletion_before_verified_cutover():
    connection=MagicMock()
    cursor=connection.cursor.return_value.__enter__.return_value
    cursor.fetchone.side_effect=[(True,),(True,False)]
    with patch('scripts.cleanup_factor_reference.get_conn',return_value=connection):
        with pytest.raises(RuntimeError,match='cutover'):
            clean(date(2026,9,1),apply=True)
    assert not any('DELETE' in str(call) for call in cursor.execute.call_args_list)
    connection.close.assert_called_once()


def test_locally_used_dates_are_never_pruned():
    connection=MagicMock()
    cursor=connection.cursor.return_value.__enter__.return_value
    cursor.fetchone.side_effect=[(True,),(True,True),(True,)]
    with patch('scripts.cleanup_factor_reference.get_conn',return_value=connection):
        assert clean(date(2026,9,1),apply=True)['protected']
    assert not any('DELETE' in str(call) for call in cursor.execute.call_args_list)
