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
    PYSETUP_PATH="/api" \
    VENV_PATH="/api/.venv"

ENV PATH="${POETRY_HOME}/bin:${VENV_PATH}/bin:${PATH}"

# Configure Debian snapshot archive
RUN echo "deb [check-valid-until=no] http://snapshot.debian.org/archive/debian/20220124 bullseye main" > /etc/apt/sources.list && \
    echo "deb [check-valid-until=no] http://snapshot.debian.org/archive/debian-security/20220124 bullseye-security main" >> /etc/apt/sources.list && \
    echo "deb [check-valid-until=no] http://snapshot.debian.org/archive/debian/20220124 bullseye-updates main" >> /etc/apt/sources.list

# Install build tools and dependencies
RUN apt-get update && \
    apt-get install --no-install-recommends -y curl build-essential

# Install project without root package, then build and install from wheel.
# This is needed because Poetry doesn't support installing root package without
# editable mode: https://github.com/python-poetry/poetry/issues/1382
# Otherwise venv with source code would need to be copied to final image.
COPY . $PYSETUP_PATH
WORKDIR $PYSETUP_PATH
RUN make install && \
    poetry build && \
    $VENV_PATH/bin/pip install --no-deps dist/*.whl

EXPOSE 8000/tcp

CMD ["uvicorn", "backend.app:get_application", "--host", "0.0.0.0", "--port", "8000"]
