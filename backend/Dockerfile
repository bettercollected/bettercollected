FROM python:3.10 as builder

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
    PYSETUP_PATH="/api/backend" \
    VENV_PATH="/api/backend/.venv"

ENV PATH="${POETRY_HOME}/bin:${VENV_PATH}/bin:${PATH}"

# Install project without root package, then build and install from wheel.
# This is needed because Poetry doesn't support installing root package without
# editable mode: https://github.com/python-poetry/poetry/issues/1382
# Otherwise venv with source code would need to be copied to final image.
RUN  curl -sSL https://raw.githubusercontent.com/python-poetry/poetry/${POETRY_VERSION}/install-poetry.py | POETRY_HOME=$POETRY_HOME POETRY_VERSION=$POETRY_VERSION python3 -

WORKDIR /api
COPY ./backend ./backend
COPY ./common ./common

WORKDIR $PYSETUP_PATH
RUN poetry install --only main --no-interaction
EXPOSE 8000/tcp

CMD ["uvicorn", "backend.app:get_application", "--host", "0.0.0.0", "--port", "8000"]
