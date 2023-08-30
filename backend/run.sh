#!/bin/bash

source "$(poetry env info --path)/bin/activate"
python3.10 -m uvicorn backend.app:get_application --host 0.0.0.0 --port 8000 --reload
deactivate
