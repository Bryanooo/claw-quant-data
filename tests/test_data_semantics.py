from datetime import date

from service.data_service.models import DatasetQuery
from service.data_service.registry import DATASETS
from service.data_service.repository import DatasetRepository
from service.investment_calendar import InvestmentCalendarRepository
from service.research.repository import ResearchRepository
from service.tushare_normalization import NORMALIZATION_CONTRACTS


def test_high_risk_normalized_identities_are_contract_reviewed():
    expected = {
        "factor_value": ("trade_date", "ts_code", "factor_name"),
        "fund_portfolio": ("ts_code", "end_date", "symbol"),
        "index_weight": ("trade_date", "index_code", "con_code"),
        "slb_sec_detail": ("trade_date", "ts_code", "tenor"),
        "eco_cal": ("date", "time", "currency", "country", "event"),
        "major_news": ("src", "pub_time", "title"),
        "fund_nav": ("nav_date", "ts_code"),
    }

    for api_name, identity in expected.items():
        contract = NORMALIZATION_CONTRACTS.get(api_name)
        dataset = DATASETS.get(api_name)
        assert contract.business_identity_fields == identity
        assert contract.identity_confidence == "contract_reviewed"
        assert dataset.business_identity_fields == identity
        assert dataset.read_table == f"tushare_current_{api_name}"


def test_observation_and_availability_dates_are_distinct():
    expected = {
        "fund_portfolio": ("end_date", "ann_date"),
        "fina_audit": ("end_date", "ann_date"),
        "fund_manager": ("begin_date", "ann_date"),
        "fund_nav": ("nav_date", "ann_date"),
    }

    for api_name, (observation, availability) in expected.items():
        contract = NORMALIZATION_CONTRACTS.get(api_name)
        dataset = DATASETS.get(api_name)
        assert contract.date_column == observation
        assert contract.availability_column == availability
        assert dataset.date_column == observation
        assert dataset.availability_column == availability


class CapturingDatabase:
    def __init__(self):
        self.statement = None
        self.params = None

    def fetch_all(self, statement, params=()):
        self.statement = statement
        self.params = params
        return []

    def fetch_one(self, statement, params=()):
        self.statement = statement
        self.params = params
        return {"total": 0}


def test_as_of_query_reduces_versions_after_availability_cutoff():
    database = CapturingDatabase()
    dataset = DATASETS.get("fund_portfolio")
    query = DatasetQuery(
        exact_filters={"ts_code": "000001.OF"},
        end_date=date(2024, 3, 31),
        as_of=date(2024, 4, 30),
        limit=20,
    )

    DatasetRepository(database).records(dataset, query)

    rendered = repr(database.statement)
    assert "DISTINCT ON" in rendered
    assert "tushare_norm_fund_portfolio" in rendered
    assert "tushare_current_fund_portfolio" not in rendered
    assert "ann_date" in rendered
    assert database.params == (
        "000001.OF",
        date(2024, 3, 31),
        date(2024, 4, 30),
        20,
        0,
    )


def test_present_day_query_uses_governed_current_view():
    database = CapturingDatabase()
    dataset = DATASETS.get("fund_portfolio")
    query = DatasetQuery(
        exact_filters={"ts_code": "000001.OF"},
        limit=20,
    )

    DatasetRepository(database).records(dataset, query)

    rendered = repr(database.statement)
    assert "tushare_current_fund_portfolio" in rendered
    assert "DISTINCT ON" not in rendered


def test_research_valuation_queries_use_current_contract():
    database = CapturingDatabase()

    ResearchRepository(database).latest_stock_valuations(
        ["300750.SZ"], as_of=date(2026, 9, 24)
    )

    assert "tushare_current_daily_basic" in database.statement
    assert "tushare_norm_daily_basic" not in database.statement


def test_investment_calendar_uses_reviewed_current_contract():
    database = CapturingDatabase()

    InvestmentCalendarRepository(database).economic_events(
        date(2026, 9, 1), date(2026, 9, 30)
    )

    assert "tushare_current_eco_cal" in database.statement
    assert "tushare_norm_eco_cal" not in database.statement
