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

# libsndfile for soundfile, sox for an import inside qwen-tts.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libsndfile1 sox \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system --gid 10001 tts \
    && useradd --system --uid 10001 --gid tts --home-dir /opt/home --create-home tts \
    && mkdir -p /opt/models && chown tts:tts /opt/models

COPY --from=build --chown=tts:tts /app/.venv /app/.venv

ARG TTS_MODEL=Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HOME=/opt/home \
    HF_HOME=/opt/models/hf \
    TTS_MODEL=${TTS_MODEL}

USER tts
WORKDIR /app

# Bake the model into the image: the container runs without internet access.
RUN python -m radar_tts.warmup

ENV HF_HUB_OFFLINE=1 \
    TTS_HOST=0.0.0.0 \
    TTS_PORT=8000

EXPOSE 8000
CMD ["radar-tts"]
