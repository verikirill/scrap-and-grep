# syntax=docker/dockerfile:1

# Build stage: resolve and install dependencies with uv into /app/.venv.
FROM ghcr.io/astral-sh/uv:python3.14-trixie-slim AS build

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0

WORKDIR /app

# Dependencies first: this layer is reused until the lock file changes.
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project --no-dev

COPY pyproject.toml uv.lock ./
COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-editable


# Runtime stage: the virtualenv and nothing else, run as an unprivileged user.
FROM python:3.14-slim-trixie AS runtime

# LightGBM, the learned feed ranker, needs the OpenMP runtime.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# /data/media is where the media worker puts videos. A named volume mounted
# there starts with this directory's owner, so the worker can write to it.
RUN groupadd --system --gid 10001 radar \
    && useradd --system --uid 10001 --gid radar --home-dir /app --no-create-home radar \
    && mkdir -p /data/media \
    && chown radar:radar /data/media

COPY --from=build --chown=radar:radar /app/.venv /app/.venv

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

USER radar
WORKDIR /app
EXPOSE 8000

CMD ["uvicorn", "radar.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
