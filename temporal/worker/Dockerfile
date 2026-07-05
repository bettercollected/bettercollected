FROM python:3.11-slim-bookworm

# Install uv ensure the path is correct
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Set environment variables
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy
ENV PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# Install dependencies
# Using --mount=type=cache allows caching of dependency downloads
# Using --mount=type=bind reduces the image size by not copying files into the layer
COPY ./temporal/worker/pyproject.toml ./temporal/worker/uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev

# Copy the application code
COPY ./temporal/worker/ .

# Install the project itself
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev
    
# Run the application
CMD ["uv", "run", "python", "main.py"]
