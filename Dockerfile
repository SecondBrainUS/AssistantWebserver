# Stage 1: Build
FROM python:3.11-buster AS builder

RUN pip install poetry==1.8.3

ARG GITHUB_TOKEN
RUN git config --global url."https://oauth2:${GITHUB_TOKEN}@github.com".insteadOf "https://github.com"

ENV POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_IN_PROJECT=1 \
    POETRY_VIRTUALENVS_CREATE=1 \
    POETRY_CACHE_DIR=/tmp/poetry_cache

WORKDIR /app

COPY poetry.lock pyproject.toml ./
RUN touch README.md
RUN poetry install && rm -rf $POETRY_CACHE_DIR

# Stage 2: Runtime
FROM python:3.11-slim-buster AS runtime

EXPOSE 8000
ENV ENVPATH=env/.env.docker

RUN apt-get update && \
    apt-get install -y libpq-dev && \
    rm -rf /var/lib/apt/lists/*

ENV VIRTUAL_ENV=/app/.venv \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

COPY --from=builder ${VIRTUAL_ENV} ${VIRTUAL_ENV}
COPY . .

ENTRYPOINT ["python", "-m", "uvicorn", "webserver.main:app", "--host", "0.0.0.0", "--reload"]
