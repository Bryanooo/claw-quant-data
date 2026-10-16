from datetime import date
import importlib.util
from pathlib import Path
spec=importlib.util.spec_from_file_location("calendar_gate",Path(__file__).resolve().parents[1]/"service/research/calendar.py")
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
session_from_rows=module.session_from_rows

def test_calendar_distinguishes_missing_from_closed():
    day=date(2026,10,13)
    assert session_from_rows(day,'SZSE',[])['data']['is_open'] is None
    assert session_from_rows(day,'SZSE',[{'cal_date':'20261013','is_open':0}])['data']['is_open'] is False
    value=session_from_rows(day,'SZSE',[{'cal_date':'20261013','is_open':1,'pretrade_date':'20261012'}])['data']
    assert value['is_open'] is True
    assert value['previous_trading_date']=='2026-10-12'
