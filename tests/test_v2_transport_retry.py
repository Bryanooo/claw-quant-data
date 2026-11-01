from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import requests

from service.orchestration_v2 import runtime


def test_transient_request_retries_without_creating_new_task(monkeypatch):
    run = Mock(side_effect=[ConnectionError('network unreachable'), TimeoutError(), 7])
    monkeypatch.setattr(runtime.TASKS, 'run', run)
    on_retry, wait = Mock(), Mock()
    spec = SimpleNamespace(task_name='test', parameters={'resume': True})
    assert runtime.run_acquisition_request(spec, on_retry=on_retry, wait=wait) == 7
    assert run.call_count == 3
    assert [call.args[0] for call in wait.call_args_list] == [1, 2]
    assert on_retry.call_count == 2


@pytest.mark.parametrize('error', [ValueError('invalid parameter'), RuntimeError('429 Client Error'), RuntimeError('permission denied')])
def test_non_transport_error_is_not_locally_retried(monkeypatch, error):
    run = Mock(side_effect=error)
    monkeypatch.setattr(runtime.TASKS, 'run', run)
    with pytest.raises(type(error)):
        runtime.run_acquisition_request(SimpleNamespace(task_name='test', parameters={}), on_retry=Mock(), wait=Mock())
    assert run.call_count == 1


def test_network_retry_is_bounded(monkeypatch):
    run = Mock(side_effect=ConnectionError('network unreachable'))
    monkeypatch.setattr(runtime.TASKS, 'run', run)
    with pytest.raises(ConnectionError):
        runtime.run_acquisition_request(SimpleNamespace(task_name='test', parameters={}), on_retry=Mock(), wait=Mock())
    assert run.call_count == 3


def test_http_unauthorized_is_not_retried_as_network(monkeypatch):
    response = requests.Response(); response.status_code = 401
    run = Mock(side_effect=requests.HTTPError(response=response))
    monkeypatch.setattr(runtime.TASKS, 'run', run)
    with pytest.raises(requests.HTTPError):
        runtime.run_acquisition_request(SimpleNamespace(task_name='test', parameters={}), on_retry=Mock(), wait=Mock())
    assert run.call_count == 1


def test_daily_chip_quota_releases_lease_without_transport_retries(monkeypatch):
    from service import tushare_rate_limit as limits
    run = Mock(side_effect=Exception('频率超限(100000次/天)'))
    monkeypatch.setattr(runtime.TASKS, 'run', run)
    mark = Mock()
    monkeypatch.setattr(limits, 'mark_daily_quota_exhausted', mark)
    wait = Mock()
    with pytest.raises(limits.TushareRateSlotDeferredError) as raised:
        runtime.run_acquisition_request(SimpleNamespace(task_name='test', api_name='cyq_chips', parameters={}), on_retry=Mock(), wait=wait)
    assert raised.value.defer_without_failure
    assert run.call_count == 1
    wait.assert_not_called()
    mark.assert_called_once_with('cyq_chips')
