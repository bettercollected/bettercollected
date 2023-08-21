#!/bin/bash

# Ensure the required Python version is installed
if ! python3.10 --version &>/dev/null; then
    echo "Python 3.10 is required but not found. Please install it."
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
        # Create a virtual environment using Poetry
        poetry env use 3.10

        # Use makefile to install dependencies
        make install
    elif [ -f "requirements.txt" ]; then
        # Create a virtual environment using venv
        python3.10 -m venv venv

        # Activate the virtual environment
        source venv/bin/activate

        # Use pip to install dependencies from requirements.txt
        pip install -r requirements.txt

        # Deactivate the virtual environment
        deactivate
    else
        echo "No dependency file found for $service"
    fi
}

# Iterate through services and run setup_service function in background
for service in "${services[@]}"; do
    setup_service "$service" &
    pids+=($!)
done

setup_webapp() {
  cd webapp
  yarn
}

# Wait for all background processes to finish
for pid in "${pids[@]}"; do
    wait "$pid"
done

setup_webapp

echo "Initialization complete!"

