# syntax=docker/dockerfile:1

# Build stage: resolve and install dependencies with uv into /app/.venv.
FROM ghcr.io/astral-sh/uv:python3.13-trixie-slim AS build

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0

WORKDIR /app

RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project --no-dev

COPY pyproject.toml uv.lock ./
COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-editable


FROM python:3.13-slim-trixie AS runtime

RUN groupadd --system --gid 10001 docparser \
    && useradd --system --uid 10001 --gid docparser --home-dir /opt/home --create-home docparser \
    && mkdir -p /opt/models && chown docparser:docparser /opt/models

COPY --from=build --chown=docparser:docparser /app/.venv /app/.venv

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HOME=/opt/home \
    HF_HOME=/opt/models/hf \
    EASYOCR_MODULE_PATH=/opt/models/easyocr

USER docparser
WORKDIR /app

# Bake the models into the image: the container runs without internet access.
RUN python -m docparser.warmup

ENV HF_HUB_OFFLINE=1 \
    DOCPARSER_OFFLINE=true

EXPOSE 8000
CMD ["uvicorn", "docparser.app:app", "--host", "0.0.0.0", "--port", "8000"]
