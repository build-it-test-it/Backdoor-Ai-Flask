#!/bin/bash

# This script initializes the PostgreSQL database for Backdoor AI
# It should be run once after setting up the environment

set -e

# Check if DATABASE_URL is set
if [ -z "$DATABASE_URL" ]; then
    echo "Error: DATABASE_URL environment variable is not set."
    echo "Please set DATABASE_URL to your PostgreSQL database URL."
    echo "Example: export DATABASE_URL=postgresql://postgres:password@localhost:5432/backdoor"
    exit 1
fi

echo "Initializing Backdoor AI database..."

# Initialize the database
flask db init

# Create the initial migration
flask db migrate -m "Initial database schema"

# Apply the migration
flask db upgrade

echo "Database initialization complete!"
echo "You can now run the application with: python run.py"
