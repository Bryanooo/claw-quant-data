"""Execution context shared by the V2 worker and collectors."""

from contextlib import contextmanager
from contextvars import ContextVar


_DURABLE_JOB_ACTIVE: ContextVar[bool] = ContextVar(
    "durable_v2_execution_active", default=False
)


def is_durable_job_active() -> bool:
    return _DURABLE_JOB_ACTIVE.get()


@contextmanager
def durable_job_execution():
    """Mark collector calls whose whole unit of work is retried by the queue."""
    token = _DURABLE_JOB_ACTIVE.set(True)
    try:
        yield
    finally:
        _DURABLE_JOB_ACTIVE.reset(token)
