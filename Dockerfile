# Chapter 10: the same package this book has run locally since chapter
# 5, built once here instead of narrated. Multi-stage so the final image
# doesn't carry uv, the git clone of reliable-agents-labs, or build tools.

FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim AS builder
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

# reorder-app depends on reliable-agents-labs as a git dependency
# (chapter 4), and this base image has no git binary at all, confirmed
# live: "Git executable not found" on the first real build, not assumed.
RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml uv.lock README.md ./
COPY backend/ backend/
RUN uv sync --frozen --no-dev

FROM python:3.13-slim-bookworm
WORKDIR /app
RUN useradd --create-home --uid 1000 appuser
COPY --from=builder --chown=appuser:appuser /app/.venv /app/.venv
COPY --chown=appuser:appuser backend/ backend/
COPY --chown=appuser:appuser config/ config/
COPY --chown=appuser:appuser scripts/ scripts/
ENV PATH="/app/.venv/bin:$PATH"
USER appuser
EXPOSE 8000
CMD ["python", "scripts/run_server.py"]
