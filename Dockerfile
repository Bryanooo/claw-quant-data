FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

ENV UV_PROJECT_ENVIRONMENT=/opt/claw-venv \
    PATH="/opt/claw-venv/bin:${PATH}"

COPY pyproject.toml uv.lock ./
RUN pip install --no-cache-dir uv==0.11.32 && \
    uv sync --locked --no-dev --no-install-project --no-cache

FROM base AS test

RUN uv sync --locked --no-install-project --no-cache

COPY . .

CMD ["python", "-m", "pytest", "-q"]

FROM base AS runtime

COPY . .

CMD ["python", "-m", "collectors.scheduler"]
