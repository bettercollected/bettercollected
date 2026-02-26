#!/bin/bash
uv run python3 -m uvicorn googleform.app:get_application --host 0.0.0.0 --port 8003