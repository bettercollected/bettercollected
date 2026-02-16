FROM python:3.12 AS builder
LABEL maintainer="Bibishan Pandey, bibishan.b.pandey@gmail.com"

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV PYTHONUNBUFFERED=1 \
    PYTHONHASHSEED=0 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_PROJECT_ENVIRONMENT="/api/integrations/google/.venv" \
    PYSETUP_PATH="/api/integrations/google" \
    VENV_PATH="/api/integrations/google/.venv"

ENV PATH="${VENV_PATH}/bin:${PATH}"

WORKDIR /api

COPY ./common ./common
COPY ./integrations/google ./integrations/google
WORKDIR $PYSETUP_PATH

RUN uv sync --no-dev --no-editable

EXPOSE 8000/tcp

HEALTHCHECK CMD curl http://localhost:8000/ready

CMD ["python3", "-m", "googleform"]
