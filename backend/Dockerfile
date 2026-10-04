FROM python:3.11.12

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uv/bin/uv

# Configure environment variables
ENV PYTHONUNBUFFERED=1 \
    LOGURU_DIAGNOSE=NO \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /api
COPY ./backend ./backend
COPY ./common ./common

WORKDIR /api/backend
# Install dependencies using uv
RUN /uv/bin/uv sync --locked --no-dev

# Socket directory for the isolated document sandbox (docker-compose.deployment.yml
# "document-sandbox"): owned by the unprivileged user it runs as, so a fresh
# named volume mounted here inherits that ownership.
RUN mkdir -p /run/doc-sandbox && chown 65534:65534 /run/doc-sandbox && chmod 0770 /run/doc-sandbox

EXPOSE 8000/tcp

HEALTHCHECK CMD curl http://localhost:8000 || exit 1

# Use python -m backend as requested
CMD ["/api/backend/.venv/bin/python", "-m", "backend"]
