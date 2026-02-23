FROM python:3.11-slim

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uv/bin/uv

# Configure environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /api
COPY ./auth ./auth
COPY ./common ./common

WORKDIR /api/auth
# Install dependencies using uv
RUN /uv/bin/uv sync --no-dev

EXPOSE 8000/tcp

HEALTHCHECK CMD curl http://localhost:8000 || exit 1

# Use python -m auth as requested
CMD ["/api/auth/.venv/bin/python", "-m", "auth"]
