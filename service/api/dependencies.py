"""FastAPI dependencies shared across routers."""

from typing import Annotated

from fastapi import Depends, Request

from service.data_coverage.service import CoverageService
from service.data_health import DataHealthService
from service.data_service.registry import DATASETS
from service.data_service.repository import DatasetRepository
from service.data_service.service import DataService
from service.data_service.canonical_market import CanonicalMarketDataService
from service.data_service.canonical_fund import CanonicalFundDataService
from service.data_service.canonical_equity import CanonicalEquityDataService
from service.data_service.canonical_equity_events import CanonicalEquityEventService
from service.data_service.canonical_equity_actions import CanonicalEquityActionService
from service.data_service.canonical_index import CanonicalIndexDataService
from service.data_service.interfaces import InterfaceDataService
from service.data_service.raw_archive import RawArchiveRepository, RawArchiveService
from service.initialization.service import InitializationService
from service.normalization_monitor import NormalizationMonitorService
from service.investment_calendar import (
    InvestmentCalendarRepository,
    InvestmentCalendarService,
)
from service.orchestration_v2.repository import OrchestrationV2Repository
from service.research.repository import ResearchRepository
from service.research.service import ResearchService
from service.source_connectors.query_runtime import QUERY_BROKER


def get_data_service(request: Request) -> DataService:
    repository = DatasetRepository(request.app.state.database)
    return DataService(repository, DATASETS)


DataServiceDependency = Annotated[DataService, Depends(get_data_service)]


def get_canonical_market_service(request: Request) -> CanonicalMarketDataService:
    return CanonicalMarketDataService(get_data_service(request), QUERY_BROKER)


CanonicalMarketDataServiceDependency = Annotated[
    CanonicalMarketDataService,
    Depends(get_canonical_market_service),
]


def get_canonical_fund_service(request: Request) -> CanonicalFundDataService:
    return CanonicalFundDataService(get_data_service(request), QUERY_BROKER)


CanonicalFundDataServiceDependency = Annotated[
    CanonicalFundDataService,
    Depends(get_canonical_fund_service),
]


def get_canonical_equity_service(request: Request) -> CanonicalEquityDataService:
    return CanonicalEquityDataService(get_data_service(request), QUERY_BROKER)


CanonicalEquityDataServiceDependency = Annotated[
    CanonicalEquityDataService,
    Depends(get_canonical_equity_service),
]


def get_canonical_equity_event_service(request: Request) -> CanonicalEquityEventService:
    return CanonicalEquityEventService(get_data_service(request), QUERY_BROKER)


CanonicalEquityEventServiceDependency = Annotated[
    CanonicalEquityEventService,
    Depends(get_canonical_equity_event_service),
]


def get_canonical_equity_action_service(request: Request) -> CanonicalEquityActionService:
    return CanonicalEquityActionService(get_data_service(request), QUERY_BROKER)


CanonicalEquityActionServiceDependency = Annotated[
    CanonicalEquityActionService,
    Depends(get_canonical_equity_action_service),
]


def get_canonical_index_service(request: Request) -> CanonicalIndexDataService:
    return CanonicalIndexDataService(get_data_service(request), QUERY_BROKER)


CanonicalIndexDataServiceDependency = Annotated[
    CanonicalIndexDataService,
    Depends(get_canonical_index_service),
]


def get_research_service(request: Request) -> ResearchService:
    return ResearchService(
        get_data_service(request),
        ResearchRepository(request.app.state.database),
    )


ResearchServiceDependency = Annotated[
    ResearchService,
    Depends(get_research_service),
]


def get_investment_calendar_service(request: Request) -> InvestmentCalendarService:
    return InvestmentCalendarService(
        InvestmentCalendarRepository(request.app.state.database)
    )


def get_interface_data_service(request: Request) -> InterfaceDataService:
    repository = DatasetRepository(request.app.state.database)
    return InterfaceDataService(repository, DATASETS)


InterfaceDataServiceDependency = Annotated[
    InterfaceDataService,
    Depends(get_interface_data_service),
]


def get_raw_archive_service(request: Request) -> RawArchiveService:
    return RawArchiveService(RawArchiveRepository(request.app.state.database))


RawArchiveServiceDependency = Annotated[
    RawArchiveService,
    Depends(get_raw_archive_service),
]


def get_normalization_monitor(request: Request) -> NormalizationMonitorService:
    return NormalizationMonitorService(request.app.state.database)


NormalizationMonitorDependency = Annotated[
    NormalizationMonitorService,
    Depends(get_normalization_monitor),
]


def get_coverage_service() -> CoverageService:
    return CoverageService()


CoverageServiceDependency = Annotated[
    CoverageService,
    Depends(get_coverage_service),
]


def get_initialization_service() -> InitializationService:
    return InitializationService()


InitializationServiceDependency = Annotated[
    InitializationService,
    Depends(get_initialization_service),
]


def get_data_health_service(request: Request) -> DataHealthService:
    return DataHealthService(
        coverage_service=get_coverage_service(),
        data_service=get_data_service(request),
        initialization_service=get_initialization_service(),
        orchestration_repository=get_orchestration_v2_repository(),
    )


def get_orchestration_v2_repository() -> OrchestrationV2Repository:
    """Return the isolated V2 control-plane repository.

    V2 deliberately uses its own short transactions and remains independent
    from the legacy application database wrapper until cutover is approved.
    """

    return OrchestrationV2Repository()


OrchestrationV2RepositoryDependency = Annotated[
    OrchestrationV2Repository,
    Depends(get_orchestration_v2_repository),
]
