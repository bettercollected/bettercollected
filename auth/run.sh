#!/bin/bash

poetry shell

python3.10 -m uvicorn auth.app:get_application --host 0.0.0.0 --port 8001 --reload
