#!/bin/bash

# Setup script for Backdoor AI
# This script prepares your environment for running Backdoor AI

set -e

echo "Setting up Backdoor AI environment..."

# Create virtual environment if it doesn't exist
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python -m venv .venv
    source .venv/bin/activate
    pip install --upgrade pip
else
    source .venv/bin/activate
fi

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt

# Create .env file if it doesn't exist
if [ ! -f ".env" ]; then
    echo "Creating .env file..."
    cp .env.example .env
    echo "Please edit .env file with your API keys and database configuration."
fi

# Create necessary directories
echo "Creating directories..."
mkdir -p /tmp/backdoor/tools
mkdir -p /tmp/backdoor/cache
mkdir -p /tmp/backdoor/logs
mkdir -p /tmp/backdoor/data
mkdir -p /tmp/backdoor/config
mkdir -p /tmp/backdoor/vscode/workspaces
mkdir -p /tmp/backdoor/vscode/sessions

echo "Backdoor AI environment setup complete!"
echo ""
echo "Next steps:"
echo "1. Edit .env file to add your API keys"
echo "2. Initialize the database with ./init-db.sh"
echo "3. Start the application with python run.py"
