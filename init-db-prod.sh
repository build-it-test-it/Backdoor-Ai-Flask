#!/bin/bash

# Production-grade database initialization script for Backdoor AI
# This script performs robust initialization of the PostgreSQL database for production use

set -e

# Set up error handling
handle_error() {
    echo "Error: An error occurred during database initialization at line $1"
    exit 1
}

trap 'handle_error $LINENO' ERR

# Check for PostgreSQL client
if ! command -v psql &> /dev/null; then
    echo "PostgreSQL client not found. Installing..."
    apt-get update && apt-get install -y postgresql-client
fi

# Check if DATABASE_URL is set
if [ -z "$DATABASE_URL" ]; then
    echo "Error: DATABASE_URL environment variable is not set."
    echo "Please set DATABASE_URL to your PostgreSQL database URL."
    echo "Example: export DATABASE_URL=postgresql://postgres:password@localhost:5432/backdoor"
    exit 1
fi

echo "Initializing Backdoor AI PostgreSQL database..."

# Handle Render's postgres:// to postgresql:// conversion for SQLAlchemy
if [[ "$DATABASE_URL" == postgres://* ]]; then
    export FIXED_DATABASE_URL=$(echo $DATABASE_URL | sed 's/postgres:\/\//postgresql:\/\//')
    echo "Converted DATABASE_URL format from postgres:// to postgresql://"
else
    export FIXED_DATABASE_URL=$DATABASE_URL
fi

# Extract database info for psql commands
DB_URL_REGEX="^(postgresql|postgres):\/\/([^:]+):([^@]+)@([^:]+):([0-9]+)\/(.+)$"
if [[ $FIXED_DATABASE_URL =~ $DB_URL_REGEX ]]; then
    DB_USER="${BASH_REMATCH[2]}"
    DB_PASS="${BASH_REMATCH[3]}"
    DB_HOST="${BASH_REMATCH[4]}"
    DB_PORT="${BASH_REMATCH[5]}"
    DB_NAME="${BASH_REMATCH[6]}"
    
    # Set up PGPASSWORD for psql
    export PGPASSWORD="$DB_PASS"
    
    # Test connection with retry
    echo "Testing database connection..."
    MAX_RETRIES=5
    RETRY_COUNT=0
    RETRY_DELAY=2
    
    while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
        if psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c "SELECT 1" >/dev/null 2>&1; then
            echo "✅ Successfully connected to PostgreSQL database!"
            break
        else
            RETRY_COUNT=$((RETRY_COUNT + 1))
            if [ $RETRY_COUNT -lt $MAX_RETRIES ]; then
                echo "⚠️ Connection attempt $RETRY_COUNT failed, retrying in $RETRY_DELAY seconds..."
                sleep $RETRY_DELAY
                RETRY_DELAY=$((RETRY_DELAY * 2))
            else
                echo "❌ Failed to connect to database after $MAX_RETRIES attempts."
                exit 1
            fi
        fi
    done
else
    echo "❌ Could not parse DATABASE_URL. Make sure it's in the format: postgresql://user:pass@host:port/dbname"
    exit 1
fi

echo "🔧 Setting up Flask-Migrate..."

# Initialize Flask-Migrate if not already initialized
if [ ! -d "migrations" ]; then
    echo "Creating migrations directory..."
    flask db init
    echo "✅ Flask-Migrate initialized"
else
    echo "✅ Migrations directory already exists"
fi

# Check if we have existing migrations
if [ ! -f "migrations/versions/initial_schema.py" ] && [ ! -f "migrations/versions/e17b51a9e4d2_initial_database_schema.py" ]; then
    echo "Creating initial migration..."
    flask db migrate -m "Initial database schema"
    echo "✅ Initial migration created"
else
    echo "✅ Initial migration already exists"
fi

# Create database backup before upgrading (if in production)
if [ "$BACKDOOR_ENV" == "production" ]; then
    BACKUP_DIR="/tmp/backdoor/db_backups"
    mkdir -p "$BACKUP_DIR"
    BACKUP_FILE="$BACKUP_DIR/backdoor_db_backup_$(date +%Y%m%d_%H%M%S).sql"
    
    echo "📦 Creating database backup before migration..."
    pg_dump -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" > "$BACKUP_FILE"
    
    if [ $? -eq 0 ]; then
        echo "✅ Database backup created: $BACKUP_FILE"
    else
        echo "⚠️ Warning: Database backup failed. Continuing with upgrade..."
    fi
fi

# Apply migrations
echo "🚀 Applying database migrations..."
flask db upgrade

# Verify schema
echo "🔍 Verifying database schema..."
python -c "
import sys
from app import create_app
from app.database import db_check_connection

app = create_app()
with app.app_context():
    if db_check_connection(max_retries=3):
        print('✅ Database schema verification successful!')
        sys.exit(0)
    else:
        print('❌ Database schema verification failed')
        sys.exit(1)
"

if [ $? -eq 0 ]; then
    echo "✅ Database initialization complete!"
    echo "You can now run the application with: gunicorn wsgi:app"
else
    echo "❌ Database initialization failed during verification."
    exit 1
fi
