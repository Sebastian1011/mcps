# syntax=docker/dockerfile:1

# python:3.12-slim, not 3.13: akshare's Linux dependency chain (py-mini-racer,
# akracer) has the most reliably available prebuilt wheels on 3.12 at the time
# this was built; matches the project's own .venv (see README "Development").
FROM python:3.12-slim AS builder

RUN pip install --no-cache-dir uv==0.9.*

WORKDIR /app

# Dependency layer first so `docker build` cache is reused across src/ edits.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY src ./src
COPY README.md ./
RUN uv sync --frozen --no-dev

FROM python:3.12-slim AS runtime

RUN useradd --create-home --uid 1000 --shell /usr/sbin/nologin app

WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
COPY src ./src

ENV PATH="/app/.venv/bin:${PATH}" \
    PYTHONUNBUFFERED=1 \
    CACHE_DIR=/data/cache \
    MCP_TRANSPORT=streamable-http \
    MCP_HOST=0.0.0.0 \
    MCP_PORT=8000

RUN mkdir -p /data/cache && chown -R app:app /data/cache /app
VOLUME ["/data/cache"]

USER app
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=3)" || exit 1

CMD ["python", "-m", "akshare_mcp"]
