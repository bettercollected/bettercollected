# This digest SHA points to python:3.9-slim-bullseye tag
FROM python:3.10 as builder
LABEL maintainer="Bibishan Pandey, bibishan.b.pandey@gmail.com"

# Configure environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONHASHSEED=0 \
    SOURCE_DATE_EPOCH=315532800 \
    CFLAGS=-g0 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=off \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PIP_DEFAULT_TIMEOUT=100 \
    POETRY_HOME="/opt/poetry" \
    POETRY_VIRTUALENVS_IN_PROJECT=true \
    POETRY_NO_INTERACTION=1 \
    POETRY_VERSION=1.3.2 \
    POETRY_INSTALL_OPTS="--no-interaction --without dev --no-root" \
    PYSETUP_PATH="/api/auth" \
    VENV_PATH="/api/auth/.venv"

ENV PATH="${POETRY_HOME}/bin:${VENV_PATH}/bin:${PATH}"

WORKDIR /api
COPY ./auth ./auth
COPY ./common ./common

WORKDIR $PYSETUP_PATH
RUN make install

EXPOSE 8000/tcp

HEALTHCHECK CMD curl http://localhost:8000

CMD ["uvicorn", "auth.app:get_application", "--host", "0.0.0.0", "--port", "8000"]
