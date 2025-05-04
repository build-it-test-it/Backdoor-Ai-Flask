FROM python:3.11-slim

WORKDIR /app

# Install code-server and required dependencies
RUN apt-get update && apt-get install -y \
    curl \
    wget \
    git \
    gnupg \
    build-essential \
    postgresql-client \
    && curl -fsSL https://code-server.dev/install.sh | sh \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application
COPY . .

# Create necessary directories
RUN mkdir -p /tmp/backdoor/tools \
    /tmp/backdoor/cache \
    /tmp/backdoor/logs \
    /tmp/backdoor/data \
    /tmp/backdoor/config \
    /tmp/backdoor/vscode/workspaces \
    /tmp/backdoor/vscode/sessions

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    VSCODE_SERVER_PATH=/usr/bin/code-server

# Expose port
EXPOSE 5000

# Initialize the database and run migrations
RUN flask db upgrade || echo "Database migrations will be run at startup"

# Run the application
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "wsgi:app"]
