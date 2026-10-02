# syntax=docker/dockerfile:1

# Build stage: resolve and install dependencies with uv into /app/.venv.
FROM ghcr.io/astral-sh/uv:python3.14-trixie-slim AS build

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


FROM python:3.14-slim-trixie AS runtime

RUN groupadd --system --gid 10001 browser \
    && useradd --system --uid 10001 --gid browser --home-dir /opt/home --create-home browser

COPY --from=build --chown=browser:browser /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HOME=/opt/home

# The libraries Firefox needs, as Playwright lists them for this system.
RUN python -m playwright install-deps firefox \
    && rm -rf /var/lib/apt/lists/*

# The Russian national CA, for its hosts only (render.py, _NationalCa).
COPY --from=certs russian_trusted_ca.pem /app/certs/russian_trusted_ca.pem

USER browser
WORKDIR /app

# Bake the browser into the image: no download when the container starts.
# The first start writes the font configuration the read-only container
# could not write later (warmup.py).
RUN python -m camoufox fetch \
    && python -m radar_browser.warmup

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4)"]
CMD ["radar-browser"]
