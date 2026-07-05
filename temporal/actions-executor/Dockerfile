FROM python:3.11-slim

# Install UV from the official image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Set working directory
WORKDIR /app

# Enable bytecode compilation
ENV UV_COMPILE_BYTECODE=1

# Copy dependency files
COPY ./temporal/actions-executor/pyproject.toml .
COPY ./temporal/actions-executor/uv.lock .

# Install dependencies
RUN uv sync --frozen --no-dev

# Copy the application code
COPY ./temporal/actions-executor/ .

# Add the virtual environment to the PATH
ENV PATH="/app/.venv/bin:$PATH"

# Run the application
CMD ["python", "main.py"]
