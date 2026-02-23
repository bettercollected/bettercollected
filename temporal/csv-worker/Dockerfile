FROM joyzoursky/python-chromedriver

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

ENV VIRTUAL_ENV=/venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"
ENV UV_PROJECT_ENVIRONMENT=$VIRTUAL_ENV
# Copy dependency files
COPY ./temporal/csv-worker/pyproject.toml ./pyproject.toml
COPY ./temporal/csv-worker/uv.lock ./uv.lock


# Install dependencies
RUN uv sync --frozen --no-install-project

# Copy application code
COPY ./temporal/csv-worker/ .

# Run the application
CMD ["python3","main.py"]
