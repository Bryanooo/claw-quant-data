"""FastAPI application factory."""

import logging
from collections.abc import Callable
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from service.api.routers import (
    collection_jobs,
    collection_monitor,
    coverage,
    data_health,
    datasets,
    health,
    initialization,
    interfaces,
    normalization,
    stocks,
)
from service.api.schemas import ErrorResponse
from service.collection_jobs.models import (
    InvalidTaskParametersError,
    JobConflictError,
    JobNotFoundError,
    TaskNotFoundError,
)
from service.config import APP_VERSION, PROJECT_ROOT
from service.data_service.database import Database
from service.data_service.models import (
    DatasetNotFoundError,
    InterfaceDataNotFoundError,
    InvalidQueryError,
    RecordNotFoundError,
)
from service.data_coverage.models import (
    CoverageRuleNotFoundError,
    InvalidCoverageRequestError,
)

logger = logging.getLogger("api")


def create_app(
    database_factory: Callable[[], Database] = Database,
) -> FastAPI:
    @asynccontextmanager
    async def lifespan(application: FastAPI):
        application.state.database = database_factory()
        try:
            yield
        finally:
            application.state.database.close()

    application = FastAPI(
        title="claw-quant-data API",
        summary="Queryable market-data service for Claw Quant",
        version=APP_VERSION,
        lifespan=lifespan,
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
    )

    @application.middleware("http")
    async def request_context(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or str(uuid4())
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

    def error_response(request: Request, status_code: int, code: str, message: str):
        body = ErrorResponse(
            error={
                "code": code,
                "message": message,
                "request_id": getattr(request.state, "request_id", None),
            }
        )
        return JSONResponse(status_code=status_code, content=body.model_dump())

    @application.exception_handler(DatasetNotFoundError)
    async def dataset_not_found(request: Request, exc: DatasetNotFoundError):
        return error_response(request, 404, "dataset_not_found", str(exc))

    @application.exception_handler(RecordNotFoundError)
    async def record_not_found(request: Request, exc: RecordNotFoundError):
        return error_response(request, 404, "record_not_found", str(exc))

    @application.exception_handler(InterfaceDataNotFoundError)
    async def interface_not_found(
        request: Request,
        exc: InterfaceDataNotFoundError,
    ):
        return error_response(request, 404, "interface_not_found", str(exc))

    @application.exception_handler(InvalidQueryError)
    async def invalid_query(request: Request, exc: InvalidQueryError):
        return error_response(request, 422, "invalid_query", str(exc))

    @application.exception_handler(TaskNotFoundError)
    async def task_not_found(request: Request, exc: TaskNotFoundError):
        return error_response(request, 404, "task_not_found", str(exc))

    @application.exception_handler(JobNotFoundError)
    async def job_not_found(request: Request, exc: JobNotFoundError):
        return error_response(request, 404, "job_not_found", str(exc))

    @application.exception_handler(InvalidTaskParametersError)
    async def invalid_task_parameters(
        request: Request,
        exc: InvalidTaskParametersError,
    ):
        return error_response(request, 422, "invalid_task_parameters", str(exc))

    @application.exception_handler(JobConflictError)
    async def job_conflict(request: Request, exc: JobConflictError):
        return error_response(request, 409, "job_conflict", str(exc))

    @application.exception_handler(CoverageRuleNotFoundError)
    async def coverage_rule_not_found(
        request: Request,
        exc: CoverageRuleNotFoundError,
    ):
        return error_response(request, 404, "coverage_rule_not_found", str(exc))

    @application.exception_handler(InvalidCoverageRequestError)
    async def invalid_coverage_request(
        request: Request,
        exc: InvalidCoverageRequestError,
    ):
        return error_response(request, 422, "invalid_coverage_request", str(exc))

    @application.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        return error_response(request, 422, "validation_error", str(exc))

    @application.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, exc: StarletteHTTPException):
        message = exc.detail if isinstance(exc.detail, str) else "request failed"
        return error_response(request, exc.status_code, "http_error", message)

    @application.exception_handler(Exception)
    async def unhandled_error(request: Request, exc: Exception):
        logger.exception("unhandled API error", exc_info=exc)
        return error_response(
            request,
            500,
            "internal_error",
            "an unexpected error occurred",
        )

    application.include_router(health.router, prefix="/api")
    application.include_router(datasets.router, prefix="/api")
    application.include_router(interfaces.router, prefix="/api")
    application.include_router(normalization.router, prefix="/api")
    application.include_router(stocks.router, prefix="/api")
    application.include_router(collection_jobs.router, prefix="/api")
    application.include_router(collection_monitor.router, prefix="/api")
    application.include_router(coverage.router, prefix="/api")
    application.include_router(data_health.router, prefix="/api")
    application.include_router(initialization.router, prefix="/api")

    dashboard_directory = PROJECT_ROOT / "service" / "dashboard"
    application.mount(
        "/dashboard-assets",
        StaticFiles(directory=dashboard_directory),
        name="dashboard-assets",
    )

    @application.get("/dashboard", include_in_schema=False)
    def dashboard() -> FileResponse:
        return FileResponse(dashboard_directory / "index.html")

    @application.get("/", include_in_schema=False)
    def root() -> RedirectResponse:
        return RedirectResponse("/dashboard")

    return application


app = create_app()
