#!/bin/bash
# replace-runtime-variables.sh

set -x


if [ -z "$ROOT_DIR" ]; then
    export ROOT_DIR="/app"
fi

if [ -f .env ]; then
    set -a
    . ./.env
    set +a
else
    echo "No .env file found. Please make sure to create one."
fi

# Define a list of environment variables to check and replace
VARIABLES=("NEXT_PUBLIC_API_ENDPOINT_HOST" "NEXT_PUBLIC_DASHBOARD_DOMAIN")

# Check if each variable is set
for VAR in "${VARIABLES[@]}"; do
    if [ -z "${!VAR}" ]; then
        echo "$VAR is not set. Please set it and rerun the script."
        exit 1
    fi
done

# Find and replace BAKED values with real values
find "$ROOT_DIR/public" "$ROOT_DIR/.next" -type f -name "*.js" |
while read file; do
    for VAR in "${VARIABLES[@]}"; do
        sed -i "s|BAKED_$VAR|${!VAR}|g" "$file"
    done
done

set +x