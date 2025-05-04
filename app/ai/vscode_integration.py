"""
VS Code Integration for Backdoor AI

This module integrates VS Code server functionality with the Backdoor AI system,
allowing agents to interact with VS Code through a dedicated API.
It handles:
- Running VS Code Server instances
- Managing workspaces
- Terminal session control
- File operations

Based on the VS-Server implementation but customized for Backdoor AI.
"""

import os
import sys
import json
import time
import logging
import asyncio
import subprocess
import shutil
import uuid
import threading
from pathlib import Path
from typing import Dict, List, Any, Optional, AsyncGenerator, Union, Tuple
from datetime import datetime

from flask import current_app

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("vscode_integration")

class VSCodeManager:
    """
    VS Code Server Manager for Backdoor AI
    
    This class manages VS Code server instances, providing an API for
    creating workspaces, managing terminals, and executing commands.
    """
    
    def __init__(self):
        """Initialize the VS Code manager."""
        self.base_path = '/tmp/backdoor/vscode'
        self.workspaces_path = os.path.join(self.base_path, 'workspaces')
        self.sessions_path = os.path.join(self.base_path, 'sessions')
        self.logs_path = os.path.join(self.base_path, 'logs')
        
        # Track running VS Code instances and sessions
        self.running_instances = {}  # workspace_id -> process
        self.active_sessions = {}    # session_id -> details
        
        # Create required directories
        os.makedirs(self.base_path, exist_ok=True)
        os.makedirs(self.workspaces_path, exist_ok=True)
        os.makedirs(self.sessions_path, exist_ok=True)
        os.makedirs(self.logs_path, exist_ok=True)
        
        # Default VS Code port range (we'll use a different port for each workspace)
        self.port_range_start = 8900
        self.port_range_end = 8999
        self.used_ports = set()
        
        # Check if code-server is installed
        self.code_server_path = self._find_code_server()
        if not self.code_server_path:
            logger.warning("code-server not found. VS Code integration will be limited.")
        else:
            logger.info(f"Found code-server at: {self.code_server_path}")
            
        # Set initialized flag based on code-server availability
        self.initialized = bool(self.code_server_path)
    
    def _find_code_server(self) -> Optional[str]:
        """Find code-server executable in the system."""
        try:
            # Try the most common locations
            possible_paths = [
                "/usr/bin/code-server",
                "/usr/local/bin/code-server",
                "/home/coder/code-server/bin/code-server",
                # Add more possible paths if needed
            ]
            
            # Check if any of these exist
            for path in possible_paths:
                if os.path.exists(path) and os.access(path, os.X_OK):
                    return path
            
            # If not found in standard locations, try using 'which'
            result = subprocess.run(
                ["which", "code-server"],
                capture_output=True,
                text=True,
                check=False
            )
            
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
            
            return None
        except Exception as e:
            logger.error(f"Error finding code-server: {e}")
            return None
    
    def _get_available_port(self) -> int:
        """Find an available port for VS Code server."""
        for port in range(self.port_range_start, self.port_range_end + 1):
            if port not in self.used_ports and self._is_port_available(port):
                return port
        
        # If we get here, no ports are available
        raise RuntimeError("No available ports for VS Code server")
    
    def _is_port_available(self, port: int) -> bool:
        """Check if a port is available."""
        import socket
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            return s.connect_ex(('localhost', port)) != 0
    
    def create_workspace(self, name: str, agent_id: str, template: Optional[str] = None) -> Dict[str, Any]:
        """
        Create a new VS Code workspace.
        
        Args:
            name: Name of the workspace
            agent_id: ID of the agent creating the workspace
            template: Optional template for the workspace
            
        Returns:
            Workspace information
        """
        if not self.initialized:
            return {
                "success": False,
                "error": "VS Code integration is not initialized"
            }
        
        try:
            # Create workspace ID
            workspace_id = str(uuid.uuid4())
            
            # Create workspace directory
            workspace_path = os.path.join(self.workspaces_path, workspace_id)
            os.makedirs(workspace_path, exist_ok=True)
            
            # Create .vscode directory
            vscode_dir = os.path.join(workspace_path, '.vscode')
            os.makedirs(vscode_dir, exist_ok=True)
            
            # Create settings.json with some basic settings
            settings = {
                "terminal.integrated.shell.linux": "/bin/bash",
                "editor.formatOnSave": True,
                "workbench.colorTheme": "Default Dark+",
                "telemetry.telemetryLevel": "off",
                "security.workspace.trust.enabled": False,
                "editor.minimap.enabled": True,
                "files.autoSave": "afterDelay",
                "files.autoSaveDelay": 1000,
                "workbench.editor.enablePreview": False,
                "git.autofetch": True
            }
            
            with open(os.path.join(vscode_dir, 'settings.json'), 'w') as f:
                json.dump(settings, f, indent=2)
            
            # Apply template if provided
            if template:
                self._apply_template(workspace_path, template)
            
            # Create workspace metadata
            metadata = {
                "id": workspace_id,
                "name": name,
                "path": workspace_path,
                "agent_id": agent_id,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
                "template": template,
                "status": "ready"
            }
            
            # Save metadata
            with open(os.path.join(workspace_path, '.vscode', 'workspace-info.json'), 'w') as f:
                json.dump(metadata, f, indent=2)
            
            logger.info(f"Created workspace: {workspace_id} for agent: {agent_id}")
            
            return {
                "success": True,
                "workspace": metadata
            }
        
        except Exception as e:
            logger.error(f"Error creating workspace: {e}")
            return {
                "success": False,
                "error": f"Failed to create workspace: {str(e)}"
            }
    
    def _apply_template(self, workspace_path: str, template: str) -> None:
        """Apply a template to a workspace."""
        # Basic templates - can be expanded later
        templates = {
            "python": self._apply_python_template,
            "node": self._apply_node_template,
            "web": self._apply_web_template,
            "empty": lambda _: None  # No-op for empty template
        }
        
        if template in templates:
            templates[template](workspace_path)
        else:
            logger.warning(f"Unknown template: {template}, defaulting to empty")
    
    def _apply_python_template(self, workspace_path: str) -> None:
        """Apply Python template to a workspace."""
        # Create basic Python project structure
        os.makedirs(os.path.join(workspace_path, 'src'), exist_ok=True)
        os.makedirs(os.path.join(workspace_path, 'tests'), exist_ok=True)
        
        # Create main.py
        with open(os.path.join(workspace_path, 'src', 'main.py'), 'w') as f:
            f.write("""def main():
    print("Hello, Backdoor AI!")

if __name__ == "__main__":
    main()
""")
        
        # Create requirements.txt
        with open(os.path.join(workspace_path, 'requirements.txt'), 'w') as f:
            f.write("""# Python dependencies
# Uncomment as needed
# requests==2.31.0
# flask==2.3.3
# sqlalchemy==2.0.27
""")
        
        # Create README.md
        with open(os.path.join(workspace_path, 'README.md'), 'w') as f:
            f.write("""# Python Project

This is a Python project template created by Backdoor AI.

## Getting Started

1. Install dependencies: `pip install -r requirements.txt`
2. Run the application: `python src/main.py`
""")
    
    def _apply_node_template(self, workspace_path: str) -> None:
        """Apply Node.js template to a workspace."""
        # Create basic Node project structure
        os.makedirs(os.path.join(workspace_path, 'src'), exist_ok=True)
        os.makedirs(os.path.join(workspace_path, 'public'), exist_ok=True)
        
        # Create package.json
        with open(os.path.join(workspace_path, 'package.json'), 'w') as f:
            f.write("""{
  "name": "node-project",
  "version": "1.0.0",
  "description": "Node.js project created by Backdoor AI",
  "main": "src/index.js",
  "scripts": {
    "start": "node src/index.js",
    "test": "echo \\"Error: no test specified\\" && exit 1"
  },
  "keywords": [],
  "author": "Backdoor AI",
  "license": "MIT"
}
""")
        
        # Create index.js
        with open(os.path.join(workspace_path, 'src', 'index.js'), 'w') as f:
            f.write("""console.log("Hello, Backdoor AI!");
""")
        
        # Create README.md
        with open(os.path.join(workspace_path, 'README.md'), 'w') as f:
            f.write("""# Node.js Project

This is a Node.js project template created by Backdoor AI.

## Getting Started

1. Install dependencies: `npm install`
2. Run the application: `npm start`
""")
    
    def _apply_web_template(self, workspace_path: str) -> None:
        """Apply web template to a workspace."""
        # Create basic web project structure
        os.makedirs(os.path.join(workspace_path, 'css'), exist_ok=True)
        os.makedirs(os.path.join(workspace_path, 'js'), exist_ok=True)
        os.makedirs(os.path.join(workspace_path, 'img'), exist_ok=True)
        
        # Create index.html
        with open(os.path.join(workspace_path, 'index.html'), 'w') as f:
            f.write("""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Backdoor AI Web Project</title>
    <link rel="stylesheet" href="css/style.css">
</head>
<body>
    <div class="container">
        <h1>Welcome to Backdoor AI Web Project</h1>
        <p>This is a simple web project template.</p>
    </div>
    <script src="js/main.js"></script>
</body>
</html>
""")
        
        # Create style.css
        with open(os.path.join(workspace_path, 'css', 'style.css'), 'w') as f:
            f.write("""body {
    font-family: Arial, sans-serif;
    line-height: 1.6;
    margin: 0;
    padding: 0;
    background-color: #f4f4f4;
}

.container {
    width: 80%;
    margin: 30px auto;
    padding: 20px;
    background-color: white;
    border-radius: 5px;
    box-shadow: 0 0 10px rgba(0,0,0,0.1);
}

h1 {
    color: #333;
}
""")
        
        # Create main.js
        with open(os.path.join(workspace_path, 'js', 'main.js'), 'w') as f:
            f.write("""console.log("Backdoor AI Web Project loaded!");
""")
        
        # Create README.md
        with open(os.path.join(workspace_path, 'README.md'), 'w') as f:
            f.write("""# Web Project

This is a simple web project template created by Backdoor AI.

## Getting Started

1. Open `index.html` in your browser
2. Edit the HTML, CSS, and JavaScript files as needed
""")
    
    def start_workspace(self, workspace_id: str, agent_id: str) -> Dict[str, Any]:
        """
        Start a VS Code server for a workspace.
        
        Args:
            workspace_id: ID of the workspace
            agent_id: ID of the agent starting the server
            
        Returns:
            Session information
        """
        if not self.initialized:
            return {
                "success": False,
                "error": "VS Code integration is not initialized"
            }
        
        # Check if workspace exists
        workspace_path = os.path.join(self.workspaces_path, workspace_id)
        if not os.path.exists(workspace_path):
            return {
                "success": False,
                "error": f"Workspace not found: {workspace_id}"
            }
        
        # Read workspace metadata
        try:
            with open(os.path.join(workspace_path, '.vscode', 'workspace-info.json'), 'r') as f:
                workspace_info = json.load(f)
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to read workspace metadata: {str(e)}"
            }
        
        # Generate session ID
        session_id = str(uuid.uuid4())
        
        # Check if there's already a running instance for this workspace
        if workspace_id in self.running_instances:
            # Get existing session info
            for existing_session_id, session_info in self.active_sessions.items():
                if session_info.get('workspace_id') == workspace_id:
                    # Update session info
                    session_info['last_active'] = datetime.now().isoformat()
                    return {
                        "success": True,
                        "session": session_info,
                        "message": "Using existing session"
                    }
        
        # Get an available port
        try:
            port = self._get_available_port()
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
        
        # Mark port as used
        self.used_ports.add(port)
        
        # Generate a unique access token
        access_token = str(uuid.uuid4())
        
        # Start code-server in a separate thread
        threading.Thread(
            target=self._start_code_server,
            args=(workspace_id, session_id, workspace_path, port, access_token, agent_id),
            daemon=True
        ).start()
        
        # Create session info
        session_info = {
            "id": session_id,
            "workspace_id": workspace_id,
            "workspace_name": workspace_info.get("name", "Unknown"),
            "agent_id": agent_id,
            "port": port,
            "access_token": access_token,
            "access_url": f"http://localhost:{port}/?tkn={access_token}",
            "status": "starting",
            "created_at": datetime.now().isoformat(),
            "last_active": datetime.now().isoformat()
        }
        
        # Store session info
        self.active_sessions[session_id] = session_info
        
        # Give it a moment to start
        time.sleep(1)
        
        return {
            "success": True,
            "session": session_info
        }
    
    def _start_code_server(self, workspace_id: str, session_id: str, workspace_path: str, 
                         port: int, access_token: str, agent_id: str) -> None:
        """Start a code-server process for a workspace."""
        try:
            # Command to run code-server
            cmd = [
                self.code_server_path,
                "--auth", "none",
                "--port", str(port),
                "--disable-telemetry",
                "--user-data-dir", os.path.join(self.base_path, 'user-data'),
                workspace_path
            ]
            
            # Log file
            log_file = os.path.join(self.logs_path, f"{session_id}.log")
            with open(log_file, 'w') as f:
                # Update session status
                self.active_sessions[session_id]['status'] = 'starting'
                
                # Start the process
                process = subprocess.Popen(
                    cmd,
                    stdout=f,
                    stderr=subprocess.STDOUT,
                    env=os.environ.copy()
                )
                
                # Store the process
                self.running_instances[workspace_id] = process
                
                # Update session status and info
                self.active_sessions[session_id]['status'] = 'running'
                self.active_sessions[session_id]['pid'] = process.pid
                
                # Wait for the process to finish
                process.wait()
                
                # Process ended, remove it from running instances
                if workspace_id in self.running_instances:
                    del self.running_instances[workspace_id]
                
                # Release the port
                if port in self.used_ports:
                    self.used_ports.remove(port)
                
                # Update session status
                if session_id in self.active_sessions:
                    self.active_sessions[session_id]['status'] = 'stopped'
        
        except Exception as e:
            logger.error(f"Error starting code-server: {e}")
            
            # Update session status
            if session_id in self.active_sessions:
                self.active_sessions[session_id]['status'] = 'error'
                self.active_sessions[session_id]['error'] = str(e)
            
            # Release the port
            if port in self.used_ports:
                self.used_ports.remove(port)
    
    def stop_workspace(self, session_id: str) -> Dict[str, Any]:
        """
        Stop a running VS Code server session.
        
        Args:
            session_id: ID of the session to stop
            
        Returns:
            Result of the operation
        """
        if not self.initialized:
            return {
                "success": False,
                "error": "VS Code integration is not initialized"
            }
        
        # Check if session exists
        if session_id not in self.active_sessions:
            return {
                "success": False,
                "error": f"Session not found: {session_id}"
            }
        
        session_info = self.active_sessions[session_id]
        workspace_id = session_info.get('workspace_id')
        
        # Check if there's a running instance for this workspace
        if workspace_id in self.running_instances:
            process = self.running_instances[workspace_id]
            try:
                # Terminate the process
                process.terminate()
                
                # Give it a moment to terminate
                time.sleep(1)
                
                # Force kill if still running
                if process.poll() is None:
                    process.kill()
                
                # Remove from running instances
                del self.running_instances[workspace_id]
                
                # Release the port
                port = session_info.get('port')
                if port in self.used_ports:
                    self.used_ports.remove(port)
                
                # Update session status
                session_info['status'] = 'stopped'
                
                return {
                    "success": True,
                    "message": "Session stopped successfully"
                }
            
            except Exception as e:
                return {
                    "success": False,
                    "error": f"Failed to stop session: {str(e)}"
                }
        
        # No running instance, just update the status
        session_info['status'] = 'stopped'
        
        return {
            "success": True,
            "message": "Session was not running"
        }
    
    def list_workspaces(self, agent_id: Optional[str] = None) -> Dict[str, Any]:
        """
        List available workspaces.
        
        Args:
            agent_id: Optional agent ID to filter by
            
        Returns:
            List of workspaces
        """
        if not self.initialized:
            return {
                "success": False,
                "error": "VS Code integration is not initialized"
            }
        
        workspaces = []
        
        # Scan workspaces directory
        try:
            for workspace_id in os.listdir(self.workspaces_path):
                workspace_path = os.path.join(self.workspaces_path, workspace_id)
                
                # Skip if not a directory
                if not os.path.isdir(workspace_path):
                    continue
                
                # Try to read metadata
                try:
                    with open(os.path.join(workspace_path, '.vscode', 'workspace-info.json'), 'r') as f:
                        workspace_info = json.load(f)
                        
                        # Skip if filtering by agent_id and it doesn't match
                        if agent_id and workspace_info.get('agent_id') != agent_id:
                            continue
                        
                        # Add to list
                        workspaces.append(workspace_info)
                except Exception as e:
                    logger.warning(f"Failed to read workspace metadata for {workspace_id}: {e}")
        
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to list workspaces: {str(e)}"
            }
        
        return {
            "success": True,
            "workspaces": workspaces,
            "count": len(workspaces)
        }
    
    def list_sessions(self, agent_id: Optional[str] = None) -> Dict[str, Any]:
        """
        List active sessions.
        
        Args:
            agent_id: Optional agent ID to filter by
            
        Returns:
            List of sessions
        """
        if not self.initialized:
            return {
                "success": False,
                "error": "VS Code integration is not initialized"
            }
        
        sessions = []
        
        # Filter sessions by agent_id if provided
        for session_id, session_info in self.active_sessions.items():
            if agent_id and session_info.get('agent_id') != agent_id:
                continue
            
            # Copy session info to avoid modifying the original
            session_data = session_info.copy()
            
            # Add to list
            sessions.append(session_data)
        
        return {
            "success": True,
            "sessions": sessions,
            "count": len(sessions)
        }
    
    def execute_command(self, session_id: str, command: str) -> Dict[str, Any]:
        """
        Execute a command in a workspace.
        
        Args:
            session_id: ID of the session
            command: Command to execute
            
        Returns:
            Result of the command execution
        """
        if not self.initialized:
            return {
                "success": False,
                "error": "VS Code integration is not initialized"
            }
        
        # Check if session exists
        if session_id not in self.active_sessions:
            return {
                "success": False,
                "error": f"Session not found: {session_id}"
            }
        
        session_info = self.active_sessions[session_id]
        workspace_id = session_info.get('workspace_id')
        
        # Get workspace path
        workspace_path = os.path.join(self.workspaces_path, workspace_id)
        if not os.path.exists(workspace_path):
            return {
                "success": False,
                "error": f"Workspace not found: {workspace_id}"
            }
        
        # Execute the command
        try:
            # Create a temporary script to run the command
            script_path = os.path.join(workspace_path, '.vscode', 'temp_command.sh')
            with open(script_path, 'w') as f:
                f.write(f"""#!/bin/bash
cd "{workspace_path}"
{command}
""")
            
            # Make it executable
            os.chmod(script_path, 0o755)
            
            # Run the command
            result = subprocess.run(
                [script_path],
                capture_output=True,
                text=True,
                timeout=30  # 30 second timeout
            )
            
            # Clean up
            try:
                os.remove(script_path)
            except:
                pass
            
            # Update session last active time
            session_info['last_active'] = datetime.now().isoformat()
            
            return {
                "success": True,
                "exit_code": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr
            }
        
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": "Command execution timed out"
            }
        
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to execute command: {str(e)}"
            }
    
    def delete_workspace(self, workspace_id: str) -> Dict[str, Any]:
        """
        Delete a workspace.
        
        Args:
            workspace_id: ID of the workspace to delete
            
        Returns:
            Result of the operation
        """
        if not self.initialized:
            return {
                "success": False,
                "error": "VS Code integration is not initialized"
            }
        
        # Check if workspace exists
        workspace_path = os.path.join(self.workspaces_path, workspace_id)
        if not os.path.exists(workspace_path):
            return {
                "success": False,
                "error": f"Workspace not found: {workspace_id}"
            }
        
        # Stop any running sessions for this workspace
        for session_id, session_info in list(self.active_sessions.items()):
            if session_info.get('workspace_id') == workspace_id:
                self.stop_workspace(session_id)
        
        # Delete the workspace directory
        try:
            shutil.rmtree(workspace_path)
            
            return {
                "success": True,
                "message": "Workspace deleted successfully"
            }
        
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to delete workspace: {str(e)}"
            }

# Create singleton instance
vscode_manager = VSCodeManager()
