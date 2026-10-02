FROM python:3.14-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    POETRY_HOME="/opt/poetry" \
    POETRY_VIRTUALENVS_IN_PROJECT=true \
    POETRY_NO_INTERACTION=1 \
    PYSETUP_PATH="/opt/pysetup" \
    VENV_PATH="/opt/pysetup/.venv" \
    PATH="/opt/poetry/bin:/opt/pysetup/.venv/bin:$PATH"

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    curl \
    build-essential && \
    rm -rf /var/lib/apt/lists/*

RUN curl -sSL https://install.python-poetry.org | python3

WORKDIR $PYSETUP_PATH

FROM base AS builder

COPY pyproject.toml poetry.lock ./

RUN poetry install --only main --no-root

FROM python:3.14-slim AS production

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app/src \
    VENV_PATH="/opt/pysetup/.venv" \
    PATH="/opt/pysetup/.venv/bin:$PATH"

COPY --from=builder /opt/pysetup /opt/pysetup

WORKDIR /app

COPY src ./src
COPY migrations ./migrations
COPY alembic.ini .
COPY entrypoint.sh .

RUN sed -i 's/\r$//' entrypoint.sh && \
    chmod +x entrypoint.sh && \
    useradd --create-home appuser && \
    mkdir -p storage/xml/zip storage/xml/current storage/openalex/researcher storage/openalex/article logs && \
    chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

CMD uvicorn --host 0.0.0.0 --port 8000 src.simcc_admin.app:app
