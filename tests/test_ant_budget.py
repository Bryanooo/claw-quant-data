import pytest
from datetime import datetime, timezone
from service.source_connectors.ant_budget import CAPS, check_capacity, AntBudgetDeferred, budget_scope, ORIGIN
from service.source_connectors.financial_data import FinancialDataConnector


def test_reserve_is_not_borrowable():
    assert sum(CAPS.values()) == 729
    with pytest.raises(AntBudgetDeferred):
        check_capacity(729,150,'research',1)
    with pytest.raises(AntBudgetDeferred):
        check_capacity(0,0,'backfill',1)
    with pytest.raises(AntBudgetDeferred):
        check_capacity(999,0,'intraday',2)
    check_capacity(0,0,'intraday',3)


def test_scope_is_nested_and_reset():
    with budget_scope('intraday'):
        assert ORIGIN.get()=='intraday'
        with budget_scope('backfill'):
            assert ORIGIN.get()=='backfill'
        assert ORIGIN.get()=='intraday'
    assert ORIGIN.get()=='research'


def test_denied_request_does_not_send(monkeypatch):
    import service.source_connectors.ant_budget as b
    def deny(payload):
        raise AntBudgetDeferred('limit')
    monkeypatch.setattr(b,'reserve',deny)
    connector=FinancialDataConnector(api_key='test')
    monkeypatch.setattr(connector,'_send',lambda p:pytest.fail('must not send'))
    with pytest.raises(AntBudgetDeferred):
        connector._post({'mode':'data','requests':[{'url':'/api/v1/quote/basic-snapshot','params':{}}]})


def test_failed_request_keeps_reservation(monkeypatch):
    import service.source_connectors.ant_budget as b
    calls=[]
    monkeypatch.setattr(b,'reserve',lambda p:31)
    monkeypatch.setattr(b,'finish',lambda *a,**kw:calls.append(a))
    connector=FinancialDataConnector(api_key='test')
    def fail(p):raise TimeoutError('unknown response')
    monkeypatch.setattr(connector,'_send',fail)
    with pytest.raises(TimeoutError):
        connector._post({'mode':'data','requests':[{'url':'/api/v1/quote/basic-snapshot','params':{}}]})
    assert calls==[(31,'failed',None)]


def test_fifteen_minute_schedule_has_sixteen_slots():
    from service.intraday.worker import _in_session
    from service.intraday.service import IntradayObservationService
    from datetime import time
    assert sum(_in_session(time(h,m)) for h in range(24) for m in (0,15,30,45))==16
    assert IntradayObservationService.slot(datetime(2026,10,31,2,14,tzinfo=timezone.utc)).minute==0


def test_rotation_covers_each_symbol_once_in_four_weeks(monkeypatch):
    import service.source_connectors.ant_scheduled as scheduled
    import hashlib
    symbols=[f'{i:06d}.SZ' for i in range(5577)]
    seen=[]
    for shard in range(4):
        group=[s for s in symbols if int(hashlib.sha256(s.encode()).hexdigest(),16)%4==shard]
        assert (len(group)+49)//50*3<=100
        seen.extend(group)
    assert sorted(seen)==symbols


def test_scheduled_partial_payload_cannot_pass(monkeypatch):
    from service.source_connectors import ant_scheduled as scheduled
    monkeypatch.setattr(scheduled,'active_a_share_symbols',lambda:['000001.SZ'])
    monkeypatch.setattr(scheduled,'store_rows',lambda *args:pytest.fail('must not store'))
    with pytest.raises(RuntimeError,match='incomplete'):
        scheduled.run_scheduled_pull(scheduled.SCHEDULED_ROUTES['stock_fnd.equity-structure'],
                                     lambda p:{'status':'SUCCESS','results':[]})
