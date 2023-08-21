#!/bin/bash

source "$(poetry env info --path)/bin/activate"
python3.10 -m uvicorn typeform.app:get_application --host 0.0.0.0 --port 8002 --reload
deactivate
