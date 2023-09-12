#!/bin/bash

user_preference="$1"

# Array to hold selected services
services_to_start=("mongodb" "mongo-seed" "webapp" "nginx" "backend" "auth" "postgresql" "temporal" "worker")

# Determine the appropriate Docker Compose command
if command -v docker-compose &> /dev/null; then
    docker_compose_cmd="docker-compose"
elif command -v docker &> /dev/null; then
    # Check if 'docker compose' is available
    if docker compose --help &> /dev/null; then
        docker_compose_cmd="docker compose"
    else
        echo "Neither 'docker-compose' nor 'docker compose' is available. Please install Docker Compose."
        exit 1
    fi
else
    echo "Docker is not installed. Please install Docker and Docker Compose."
    exit 1
fi

# Common docker function
function dockerup() {
    "$docker_compose_cmd" -f "docker-compose.deployment.yml" up --build -d "$@"
}

function dockerdown() {
    "$docker_compose_cmd" -f "docker-compose.deployment.yml" down
}

if [ "$user_preference" == both ]; then
    services=("integrations-typeform" "integrations-googleform")
    for service in "${services[@]}"; do
        services_to_start+=("$service")
    done
    dockerup "${services_to_start[@]}"
elif [ "$user_preference" == googleform ]; then
    services_to_start+=("integrations-googleform")
    dockerup "${services_to_start[@]}"
elif [ "$user_preference" == typeform ]; then
    services_to_start+=("integrations-typeform")
    dockerup "${services_to_start[@]}"
elif [ "$user_preference" == down ]; then
    dockerdown
else
    dockerup "${services_to_start[@]}"
fi
