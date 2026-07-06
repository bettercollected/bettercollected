#!/bin/bash

# Ensure uv is installed (the Python services use uv, not Poetry)
if ! uv --version &>/dev/null; then
    echo "uv is required but not found. Install it: https://docs.astral.sh/uv/getting-started/installation/"
    exit 1
fi

# Ensure yarn is installed for the webapp
if ! yarn --version &>/dev/null; then
    echo "yarn is required but not found. Please install it."
    exit 1
fi

# Store the root directory path
root_dir=$(pwd)

# List of service directories and subservice directories in "service" and "service/subservice" format
services=("auth" "integrations/google" "integrations/typeform" "backend" "temporal/worker")

# Initialize an array to hold the background process IDs
pids=()

# Function to set up a service
setup_service() {
    service="$1"

    echo "Setting up $service..."

    # Split the service directory into service and subservice parts
    IFS="/" read -r main_service sub_service <<< "$service"

    # Change to the service directory
    if [ -z "$sub_service" ]; then
        cd "$root_dir/$main_service" || exit
    else
        cd "$root_dir/$main_service/$sub_service" || exit
    fi

    # Check if pyproject.toml exists
    if [ -f "pyproject.toml" ]; then
        # uv creates its own .venv and picks a compatible Python version per
        # requires-python (>=3.10) — no separate interpreter/venv step needed.
        uv sync
    else
        echo "No pyproject.toml found for $service, skipping"
    fi
}

# Iterate through services and run setup_service function in background
for service in "${services[@]}"; do
    setup_service "$service" &
    pids+=($!)
done

setup_webapp() {
  cd webapp || exit
  yarn
}

# Wait for all background processes to finish
for pid in "${pids[@]}"; do
    wait "$pid"
done

setup_webapp

echo "Initialization complete!"
