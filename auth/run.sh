#!/bin/bash
unset DEBUG
uv run python3 -m uvicorn auth.app:get_application --host 0.0.0.0 --port 8001
