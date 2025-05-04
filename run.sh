#!/bin/bash

# Run script for Backdoor AI
# This script starts the Backdoor AI application

set -e

# Load environment variables from .env file if it exists
if [ -f ".env" ]; then
    echo "Loading environment variables from .env file..."
    export $(grep -v '
^
#' .env | xargs)
fi

# Activate virtual environment if it exists
if [ -d ".venv" ]; then
    source .venv/bin/activate
fi

# Check if DATABASE_URL is set
if [ -z "$DATABASE_URL" ]; then
    echo "Warning: DATABASE_URL environment variable is not set."
    echo "Using SQLite database by default."
fi

# Check if PostgreSQL server is running if using PostgreSQL
if [[ "$DATABASE_URL" == postgresql* ]]; then
    echo "Checking PostgreSQL connection..."
    pg_isready -d "$DATABASE_URL" || {
        echo "WARNING: PostgreSQL server is not running or not accessible."
        echo "Please start PostgreSQL server before running the application."
    }
fi

# Run database migrations if needed
echo "Running database migrations..."
flask db upgrade || {
    echo "Database migrations failed. Please run ./init-db.sh first."
    exit 1
}

# Start the application
echo "Starting Backdoor AI..."
python wsgi.py
