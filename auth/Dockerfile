FROM python:3.11-slim

# Install uv
COPY --from=ghcr.io/astral-sh/uv:0.12.23 /uv /uv/bin/uv

# Configure environment variables
ENV PYTHONUNBUFFERED=1 \
    LOGURU_DIAGNOSE=NO \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /api
COPY ./auth ./auth
COPY ./common ./common

WORKDIR /api/auth
# Install dependencies using uv
RUN /uv/bin/uv sync --locked --no-dev

EXPOSE 8000/tcp

# Use python -m auth as requested
CMD ["/api/auth/.venv/bin/python", "-m", "auth"]
