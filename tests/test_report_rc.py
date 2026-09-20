import pandas as pd

from collectors.contracts import PaginationMode
from collectors.stock.extra.report_rc import ReportRcCollector
from service.tushare_policy import TusharePolicyRegistry


def _collector_without_init():
    return ReportRcCollector.__new__(ReportRcCollector)


def test_report_identity_distinguishes_brokers_and_forecast_quarters():
    frame = pd.DataFrame(
        [
            {
                "ts_code": "000858.SZ",
                "report_date": "20220429",
                "report_title": "年度报告点评",
                "org_name": "甲证券",
                "author_name": "分析师甲",
                "quarter": "2022Q4",
            },
            {
                "ts_code": "000858.SZ",
                "report_date": "20220429",
                "report_title": "年度报告点评",
                "org_name": "乙证券",
                "author_name": "分析师乙",
                "quarter": "2022Q4",
            },
            {
                "ts_code": "000858.SZ",
                "report_date": "20220429",
                "report_title": "年度报告点评",
                "org_name": "甲证券",
                "author_name": "分析师甲",
                "quarter": "2023Q4",
            },
        ]
    )

    transformed = _collector_without_init().transform(frame)

    assert transformed["source_key"].nunique() == 3


def test_report_identity_supports_missing_quarter_and_normalizes_date():
    collector = _collector_without_init()
    compact = pd.DataFrame(
        [{
            "ts_code": "300299.SZ",
            "report_date": "20220818",
            "report_title": "事件点评",
            "org_name": "信达证券",
            "author_name": "分析师甲",
            "quarter": None,
        }]
    )
    dashed = compact.assign(report_date="2022-08-18", quarter=float("nan"))

    compact_key = collector.transform(compact).iloc[0]["source_key"]
    dashed_key = collector.transform(dashed).iloc[0]["source_key"]

    assert compact_key == dashed_key
    assert len(compact_key) == 32


def test_report_rc_requires_offset_exhaustion():
    assert ReportRcCollector.pagination_mode is PaginationMode.OFFSET
    assert TusharePolicyRegistry().get("report_rc").pagination_mode == "offset"
