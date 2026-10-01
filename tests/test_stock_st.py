import pandas as pd

from collectors.stock.basic.stock_st import StockSTCollector


def test_historical_stock_st_does_not_repeat_current_details_per_security():
    collector = object.__new__(StockSTCollector)
    collector.logger = type("Logger", (), {"info": lambda *_args: None})()
    collector.fetch_stock_st = lambda _trade_date: pd.DataFrame([
        {
            "ts_code": "000001.SZ",
            "name": "示例",
            "trade_date": "20260922",
            "type": "ST",
            "type_name": "风险警示板",
        }
    ])
    collector.fetch_st_detail = lambda _ts_code: (_ for _ in ()).throw(
        AssertionError("historical list collection must not fetch current details")
    )

    frame = collector.fetch(trade_date="20260922")

    assert len(frame) == 1
    assert frame.iloc[0]["ts_code"] == "000001.SZ"
    assert frame.iloc[0]["st_reason"] is None


def test_daily_stock_st_uses_incremental_events_and_previous_snapshot():
    collector = object.__new__(StockSTCollector)
    collector.logger = type("Logger", (), {"info": lambda *_args: None})()
    collector.fetch_stock_st = lambda _trade_date: pd.DataFrame([
        {
            "ts_code": "000001.SZ", "name": "旧标的", "trade_date": "20260924",
            "type": "ST", "type_name": "风险警示板",
        },
        {
            "ts_code": "000002.SZ", "name": "新标的", "trade_date": "20260924",
            "type": "ST", "type_name": "风险警示板",
        },
    ])
    collector._load_previous_details = lambda _codes, _date: {
        "000001.SZ": {
            "ts_code": "000001.SZ", "pub_date": "20260901",
            "imp_date": "20260902", "st_type": "ST",
            "st_reason": "旧原因", "st_explain": "旧说明",
        }
    }
    collector.fetch_st_updates = lambda _date: [{
        "ts_code": "000001.SZ", "pub_date": "20260924",
        "imp_date": "20260925", "st_tpye": "*ST",
        "st_reason": "新原因", "st_explain": "新说明",
    }]
    detail_calls = []

    def fetch_detail(code):
        detail_calls.append(code)
        return [{
            "ts_code": code, "pub_date": "20260924", "imp_date": "20260924",
            "st_type": "ST", "st_reason": "首次原因", "st_explain": "首次说明",
        }]

    collector.fetch_st_detail = fetch_detail

    frame = collector.fetch(trade_date="20260924", include_details=True)

    assert detail_calls == ["000002.SZ"]
    rows = frame.set_index("ts_code")
    assert rows.loc["000001.SZ", "st_reason"] == "新原因"
    assert rows.loc["000001.SZ", "st_type"] == "*ST"
    assert rows.loc["000002.SZ", "st_reason"] == "首次原因"


def test_latest_details_prefers_effective_date_then_publication_date():
    selected = StockSTCollector._latest_details([
        {"ts_code": "000001.SZ", "pub_date": "20260924", "imp_date": "20260925"},
        {"ts_code": "000001.SZ", "pub_date": "20260923", "imp_date": "20260926"},
    ])

    assert selected["000001.SZ"]["imp_date"] == "20260926"
