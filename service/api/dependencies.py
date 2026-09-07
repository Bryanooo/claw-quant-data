"""FastAPI dependencies shared across routers."""

from typing import Annotated

from fastapi import Depends, Request

from service.collection_jobs.registry import TASKS
from service.collection_jobs.repository import JobRepository
from service.collection_jobs.service import CollectionJobService
from service.collection_jobs.fanout_campaigns import FanoutCampaignService
from service.collection_monitor import CollectionMonitorService
from service.data_coverage.service import CoverageService
from service.data_health import DataHealthService
from service.data_service.registry import DATASETS
from service.data_service.repository import DatasetRepository
from service.data_service.service import DataService
from service.data_service.interfaces import InterfaceDataService
from service.initialization.service import InitializationService
from service.normalization_monitor import NormalizationMonitorService

def get_data_service(request: Request) -> DataService:
    repository = DatasetRepository(request.app.state.database)
    return DataService(repository, DATASETS)


DataServiceDependency = Annotated[DataService, Depends(get_data_service)]


def get_interface_data_service(request: Request) -> InterfaceDataService:
    repository = DatasetRepository(request.app.state.database)
    return InterfaceDataService(repository, DATASETS)


InterfaceDataServiceDependency = Annotated[
    InterfaceDataService,
    Depends(get_interface_data_service),
]


def get_normalization_monitor(request: Request) -> NormalizationMonitorService:
    return NormalizationMonitorService(request.app.state.database)


NormalizationMonitorDependency = Annotated[
    NormalizationMonitorService,
    Depends(get_normalization_monitor),
]


def get_collection_job_service() -> CollectionJobService:
    return CollectionJobService(JobRepository(), TASKS)


CollectionJobServiceDependency = Annotated[
    CollectionJobService,
    Depends(get_collection_job_service),
]


def get_fanout_campaign_service() -> FanoutCampaignService:
    return FanoutCampaignService()


FanoutCampaignServiceDependency = Annotated[
    FanoutCampaignService,
    Depends(get_fanout_campaign_service),
]


def get_coverage_service() -> CoverageService:
    return CoverageService()


CoverageServiceDependency = Annotated[
    CoverageService,
    Depends(get_coverage_service),
]


def get_collection_monitor_service() -> CollectionMonitorService:
    return CollectionMonitorService()


def get_initialization_service() -> InitializationService:
    return InitializationService()


InitializationServiceDependency = Annotated[
    InitializationService,
    Depends(get_initialization_service),
]


def get_data_health_service(request: Request) -> DataHealthService:
    return DataHealthService(
        collection_service=get_collection_monitor_service(),
        coverage_service=get_coverage_service(),
        data_service=get_data_service(request),
        initialization_service=get_initialization_service(),
    )
