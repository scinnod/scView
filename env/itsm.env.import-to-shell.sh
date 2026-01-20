#!/bin/bash
# Read file into array, then process
mapfile -t lines < itsm.env

for line in "${lines[@]}"; do
    # Skip empty lines and comments
    [[ -z "$line" || "$line" =~ ^# ]] && continue
    # Extract key and value
    key="${line%%=*}"
    value="${line#*=}"
    # Remove whitespace
    key=$(echo "$key" | xargs)
    value=$(echo "$value" | xargs)
    # Export
    export "$key=$value"
done