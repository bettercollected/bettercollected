FROM python:3.11-slim

# Install UV from the official image
COPY --from=ghcr.io/astral-sh/uv:0.12.23 /uv /uvx /bin/

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

# Run as an unprivileged user. The custom-code sandbox then cuts its child off from
# the filesystem with Landlock (kernel 5.13 or later); a root container with the
# default capabilities adds chroot and a user drop, but root with `cap_drop: ALL`
# cannot chroot, and the sandbox then refuses custom code (docs/executor-isolation.md).
RUN useradd --system --uid 10001 --no-create-home --shell /usr/sbin/nologin executor
USER 10001

# Run the application
CMD ["python", "main.py"]
