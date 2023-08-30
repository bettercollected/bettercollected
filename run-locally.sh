#!/bin/bash

# Store the root directory path
root_dir=$(pwd)

# List of service directories and subservice directories
services=("webapp" "auth" "integrations/google" "integrations/typeform" "backend" "temporal/worker" )

# Initialize an array to hold the background process IDs
pids=()

# Function to run the run.sh script in a service directory
run_service() {
    service="$1"
    echo "Running 'run.sh' in $service..."
    (cd "$root_dir/$service" && ./run.sh)
}

# Loop through services and run the run.sh script in each service in parallel
for service in "${services[@]}"; do
    run_service "$service" &
    pids+=($!)
done

# Wait for all background processes to finish
for pid in "${pids[@]}"; do
    wait "$pid"
done

echo "Services startup complete!"

