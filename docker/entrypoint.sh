#!/bin/bash
set -e

# Create necessary directories
mkdir -p /tmp/backdoor/logs
mkdir -p /tmp/backdoor/data
mkdir -p /tmp/backdoor/cache
mkdir -p /tmp/backdoor/tools
mkdir -p /tmp/backdoor/config
mkdir -p /tmp/backdoor/microagents

# Start code-server in the background
echo "Starting code-server..."
code-server --bind-addr 0.0.0.0:8080 --auth none --cert false &

# Start execution server
echo "Starting execution server..."
cd ${WORKSPACE_DIR}

# Create a simple health check endpoint
cat > /tmp/server.py << 'EOT'
import os
import sys
import json
import subprocess
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

app = FastAPI(title="Backdoor Execution Server")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok"}

@app.post("/execute")
async def execute(request: Request):
    """Execute a command."""
    try:
        data = await request.json()
        command = data.get("command")
        
        if not command:
            raise HTTPException(status_code=400, detail="Command is required")
        
        # Execute command
        process = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True
        )
        
        return {
            "stdout": process.stdout,
            "stderr": process.stderr,
            "exit_code": process.returncode
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/workspace")
async def workspace():
    """Get workspace information."""
    try:
        # Get list of files in workspace
        files = []
        for root, dirs, filenames in os.walk(os.environ.get("WORKSPACE_DIR", "/workspace")):
            for filename in filenames:
                files.append(os.path.join(root, filename))
        
        return {
            "workspace_dir": os.environ.get("WORKSPACE_DIR", "/workspace"),
            "files": files[:100]  # Limit to 100 files
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    port = int(os.environ.get("BACKDOOR_CONTAINER_PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
EOT

# Start the server
python3 /tmp/server.py &

# Create a file to indicate initialization is complete
touch /tmp/backdoor/initialized

# Keep the container running
echo "Backdoor runtime is ready!"
tail -f /dev/null