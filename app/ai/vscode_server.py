"""
VS Code Server Integration for Backdoor AI - DEPRECATED

NOTE: This module is deprecated. Please use vscode_integration.py instead.
This file is kept for reference purposes only.

The new VS Code integration in vscode_integration.py provides improved
functionality based on the VS-Server codebase.
"""

import os
import json
import uuid
import logging
import subprocess
import socket
import time
import threading
import shutil
from typing import Dict, List, Any, Optional, Union, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path

from flask import current_app

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("vscode_server")

@dataclass
class VSCodeWorkspace:
    """Class representing a VS Code workspace."""
    id: str
    name: str
    path: str
    created_at: datetime
    owner_id: str
    owner_type: str  # 'agent', 'user', etc.
    settings: Dict[str, Any]
    access_url: str
    status: str
    last_active: datetime
    metadata: Dict[str, Any]

@dataclass
class VSCodeSession:
    """Class representing an active VS Code session."""
    id: str
    workspace_id: str
    agent_id: Optional[str]
    user_id: Optional[str]
    start_time: datetime
    last_activity: datetime
    status: str
    pid: Optional[int]
    port: int
    access_token: str
    metadata: Dict[str, Any]

class VSCodeServer:
    """
    VS Code Server manager for Backdoor AI.
    
    This class handles creating and managing VS Code server instances,
    workspaces, and sessions. It allows agents to interact with VS Code
    through a standardized API.
    """
    
    def __init__(self):
        """Initialize the VS Code server manager."""
        self.workspaces: Dict[str, VSCodeWorkspace] = {}
        self.sessions: Dict[str, VSCodeSession] = {}
        self.base_data_dir = '/tmp/vscode-server'
        self.base_port = 8900  # Starting port for VS Code servers
        self.max_sessions = 5  # Maximum number of concurrent sessions
        self.initialized = False
        
        # Load configuration
        self.config = {
            'vscode_executable': os.environ.get('VSCODE_SERVER_PATH', 'code-server'),
            'extension_gallery': os.environ.get('VSCODE_EXTENSION_GALLERY', ''),
            'data_dir': os.environ.get('VSCODE_DATA_DIR', self.base_data_dir),
            'base_url': os.environ.get('VSCODE_BASE_URL', 'http://localhost'),
            'default_settings': {
                'telemetry.enableTelemetry': False,
                'telemetry.enableCrashReporter': False,
                'update.mode': 'none',
                'terminal.integrated.shell.linux': '/bin/bash'
            }
        }
        
        # Ensure base directories exist
        os.makedirs(self.config['data_dir'], exist_ok=True)
        os.makedirs(os.path.join(self.config['data_dir'], 'workspaces'), exist_ok=True)
        os.makedirs(os.path.join(self.config['data_dir'], 'extensions'), exist_ok=True)
        os.makedirs(os.path.join(self.config['data_dir'], 'sessions'), exist_ok=True)
        
        # Load existing workspaces and sessions
        self._load_workspaces()
        self._load_sessions()
        
        # Track managed processes
        self.processes = {}  # session_id -> process object
        
        # Check if VS Code server is available
        if not self._check_vscode_available():
            logger.warning("VS Code server executable not found or not working")
            return
            
        self.initialized = True
        logger.info("VS Code Server manager initialized")
    
    def _check_vscode_available(self) -> bool:
        """Check if VS Code server is available and working."""
        try:
            result = subprocess.run(
                [self.config['vscode_executable'], '--version'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                logger.info(f"VS Code server available: {result.stdout.strip()}")
                return True
            else:
                logger.error(f"VS Code server check failed: {result.stderr}")
                return False
        except Exception as e:
            logger.error(f"Error checking VS Code server: {str(e)}")
            return False
    
    def _find_available_port(self) -> int:
        """Find an available port for a new VS Code server instance."""
        port = self.base_port
        
        # Check if any sessions are using this port
        used_ports = [session.port for session in self.sessions.values()]
        
        while port in used_ports or not self._is_port_available(port):
            port += 1
        
        return port
    
    def _is_port_available(self, port: int) -> bool:
        """Check if a port is available."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            return s.connect_ex(('localhost', port)) != 0
    
    def _load_workspaces(self) -> None:
        """Load existing workspaces from disk."""
        try:
            workspace_dir = os.path.join(self.config['data_dir'], 'workspaces')
            for ws_id in os.listdir(workspace_dir):
                ws_path = os.path.join(workspace_dir, ws_id)
                if os.path.isdir(ws_path):
                    # Check for metadata file
                    metadata_file = os.path.join(ws_path, '.vscode', 'workspace.json')
                    if os.path.exists(metadata_file):
                        with open(metadata_file, 'r') as f:
                            try:
                                data = json.load(f)
                                # Convert string dates back to datetime objects
                                created_at = datetime.fromisoformat(data.get('created_at', datetime.now().isoformat()))
                                last_active = datetime.fromisoformat(data.get('last_active', datetime.now().isoformat()))
                                
                                workspace = VSCodeWorkspace(
                                    id=ws_id,
                                    name=data.get('name', ws_id),
                                    path=ws_path,
                                    created_at=created_at,
                                    owner_id=data.get('owner_id', ''),
                                    owner_type=data.get('owner_type', 'user'),
                                    settings=data.get('settings', {}),
                                    access_url=data.get('access_url', ''),
                                    status=data.get('status', 'inactive'),
                                    last_active=last_active,
                                    metadata=data.get('metadata', {})
                                )
                                self.workspaces[ws_id] = workspace
                                logger.info(f"Loaded workspace: {ws_id} ({data.get('name', ws_id)})")
                            except json.JSONDecodeError:
                                logger.error(f"Error parsing workspace metadata: {metadata_file}")
                    else:
                        logger.warning(f"Workspace metadata file not found: {metadata_file}")
        except Exception as e:
            logger.error(f"Error loading workspaces: {str(e)}")
    
    def _load_sessions(self) -> None:
        """Load existing sessions from disk."""
        try:
            session_dir = os.path.join(self.config['data_dir'], 'sessions')
            for session_file in os.listdir(session_dir):
                if session_file.endswith('.json'):
                    with open(os.path.join(session_dir, session_file), 'r') as f:
                        try:
                            data = json.load(f)
                            session_id = data.get('id')
                            if session_id:
                                # Convert string dates back to datetime objects
                                start_time = datetime.fromisoformat(data.get('start_time', datetime.now().isoformat()))
                                last_activity = datetime.fromisoformat(data.get('last_activity', datetime.now().isoformat()))
                                
                                session = VSCodeSession(
                                    id=session_id,
                                    workspace_id=data.get('workspace_id', ''),
                                    agent_id=data.get('agent_id'),
                                    user_id=data.get('user_id'),
                                    start_time=start_time,
                                    last_activity=last_activity,
                                    status=data.get('status', 'inactive'),
                                    pid=data.get('pid'),
                                    port=data.get('port', 0),
                                    access_token=data.get('access_token', ''),
                                    metadata=data.get('metadata', {})
                                )
                                
                                # Only add if it's recent (last 24 hours) and has valid data
                                time_diff = (datetime.now() - last_activity).total_seconds()
                                if time_diff < 86400 and session.workspace_id in self.workspaces:
                                    self.sessions[session_id] = session
                                    logger.info(f"Loaded session: {session_id} for workspace {session.workspace_id}")
                        except json.JSONDecodeError:
                            logger.error(f"Error parsing session data: {session_file}")
        except Exception as e:
            logger.error(f"Error loading sessions: {str(e)}")
    
    def _save_workspace(self, workspace: VSCodeWorkspace) -> bool:
        """Save workspace metadata to disk."""
        try:
            ws_dir = os.path.join(workspace.path, '.vscode')
            os.makedirs(ws_dir, exist_ok=True)
            
            metadata_file = os.path.join(ws_dir, 'workspace.json')
            
            # Convert to dict and handle datetime serialization
            workspace_dict = asdict(workspace)
            workspace_dict['created_at'] = workspace.created_at.isoformat()
            workspace_dict['last_active'] = workspace.last_active.isoformat()
            
            with open(metadata_file, 'w') as f:
                json.dump(workspace_dict, f, indent=2)
            
            return True
        except Exception as e:
            logger.error(f"Error saving workspace metadata: {str(e)}")
            return False
    
    def _save_session(self, session: VSCodeSession) -> bool:
        """Save session data to disk."""
        try:
            session_dir = os.path.join(self.config['data_dir'], 'sessions')
            os.makedirs(session_dir, exist_ok=True)
            
            session_file = os.path.join(session_dir, f"{session.id}.json")
            
            # Convert to dict and handle datetime serialization
            session_dict = asdict(session)
            session_dict['start_time'] = session.start_time.isoformat()
            session_dict['last_activity'] = session.last_activity.isoformat()
            
            with open(session_file, 'w') as f:
                json.dump(session_dict, f, indent=2)
            
            return True
        except Exception as e:
            logger.error(f"Error saving session data: {str(e)}")
            return False
    
    def create_workspace(self, name: str, owner_id: str, owner_type: str = 'agent', 
                       template: Optional[str] = None, settings: Optional[Dict[str, Any]] = None) -> Optional[VSCodeWorkspace]:
        """
        Create a new VS Code workspace.
        
        Args:
            name: Name of the workspace
            owner_id: ID of the owner (agent or user)
            owner_type: Type of owner ('agent' or 'user')
            template: Optional template to initialize workspace with
            settings: Optional workspace settings
            
        Returns:
            Created workspace or None if creation failed
        """
        if not self.initialized:
            logger.error("VS Code server not initialized")
            return None
        
        try:
            # Generate a unique ID for the workspace
            ws_id = str(uuid.uuid4())
            
            # Create workspace directory
            ws_path = os.path.join(self.config['data_dir'], 'workspaces', ws_id)
            os.makedirs(ws_path, exist_ok=True)
            
            # Initialize with template if provided
            if template:
                template_path = os.path.join(self.config['data_dir'], 'templates', template)
                if os.path.exists(template_path):
                    # Copy template files to workspace
                    for item in os.listdir(template_path):
                        src = os.path.join(template_path, item)
                        dst = os.path.join(ws_path, item)
                        if os.path.isdir(src):
                            shutil.copytree(src, dst)
                        else:
                            shutil.copy2(src, dst)
            
            # Create .vscode directory
            vscode_dir = os.path.join(ws_path, '.vscode')
            os.makedirs(vscode_dir, exist_ok=True)
            
            # Create settings.json
            merged_settings = self.config['default_settings'].copy()
            if settings:
                merged_settings.update(settings)
            
            with open(os.path.join(vscode_dir, 'settings.json'), 'w') as f:
                json.dump(merged_settings, f, indent=2)
            
            # Create workspace object
            workspace = VSCodeWorkspace(
                id=ws_id,
                name=name,
                path=ws_path,
                created_at=datetime.now(),
                owner_id=owner_id,
                owner_type=owner_type,
                settings=merged_settings,
                access_url='',  # Will be set when a session is created
                status='ready',
                last_active=datetime.now(),
                metadata={
                    'template': template,
                    'created_by': owner_id
                }
            )
            
            # Save metadata
            self._save_workspace(workspace)
            
            # Add to workspaces dict
            self.workspaces[ws_id] = workspace
            
            logger.info(f"Created workspace: {ws_id} ({name})")
            return workspace
        except Exception as e:
            logger.error(f"Error creating workspace: {str(e)}")
            return None
    
    def start_session(self, workspace_id: str, agent_id: Optional[str] = None, 
                    user_id: Optional[str] = None) -> Optional[VSCodeSession]:
        """
        Start a new VS Code session for a workspace.
        
        Args:
            workspace_id: ID of the workspace to start a session for
            agent_id: Optional agent ID if an agent is starting the session
            user_id: Optional user ID if a user is starting the session
            
        Returns:
            Created session or None if creation failed
        """
        if not self.initialized:
            logger.error("VS Code server not initialized")
            return None
        
        # Check if the workspace exists
        if workspace_id not in self.workspaces:
            logger.error(f"Workspace not found: {workspace_id}")
            return None
        
        # Check if we have reached the maximum number of sessions
        if len(self.sessions) >= self.max_sessions:
            logger.error(f"Maximum number of sessions reached ({self.max_sessions})")
            return None
        
        # Check if there's already an active session for this workspace
        for session in self.sessions.values():
            if session.workspace_id == workspace_id and session.status == 'active':
                logger.info(f"Found existing active session for workspace {workspace_id}: {session.id}")
                # Update session metadata
                session.last_activity = datetime.now()
                if agent_id and not session.agent_id:
                    session.agent_id = agent_id
                if user_id and not session.user_id:
                    session.user_id = user_id
                self._save_session(session)
                return session
        
        try:
            # Generate a unique ID for the session
            session_id = str(uuid.uuid4())
            
            # Find an available port
            port = self._find_available_port()
            
            # Generate access token
            access_token = str(uuid.uuid4())
            
            # Create session object
            session = VSCodeSession(
                id=session_id,
                workspace_id=workspace_id,
                agent_id=agent_id,
                user_id=user_id,
                start_time=datetime.now(),
                last_activity=datetime.now(),
                status='starting',
                pid=None,
                port=port,
                access_token=access_token,
                metadata={}
            )
            
            # Add to sessions dict
            self.sessions[session_id] = session
            
            # Save session data
            self._save_session(session)
            
            # Start VS Code server process
            workspace = self.workspaces[workspace_id]
            
            # Start in a separate thread to avoid blocking
            thread = threading.Thread(
                target=self._start_vscode_process,
                args=(session, workspace)
            )
            thread.daemon = True
            thread.start()
            
            logger.info(f"Starting session: {session_id} for workspace {workspace_id} on port {port}")
            
            # Wait a bit for the process to start
            time.sleep(2)
            
            return session
        except Exception as e:
            logger.error(f"Error starting session: {str(e)}")
            return None
    
    def _start_vscode_process(self, session: VSCodeSession, workspace: VSCodeWorkspace) -> None:
        """Start the VS Code server process for a session."""
        try:
            # Build command
            cmd = [
                self.config['vscode_executable'],
                '--port', str(session.port),
                '--auth', 'none',  # Use our own token validation
                '--disable-telemetry',
                '--disable-update-check',
                '--disable-workspace-trust',
                workspace.path
            ]
            
            # Set environment variables
            env = os.environ.copy()
            env['VSCODE_CLI'] = '1'
            env['VSCODE_PARENT_PID'] = str(os.getpid())
            
            # Start process
            process = subprocess.Popen(
                cmd,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True
            )
            
            # Store process
            self.processes[session.id] = process
            
            # Update session with PID
            session.pid = process.pid
            session.status = 'active'
            
            # Update workspace access URL
            workspace.access_url = f"{self.config['base_url']}:{session.port}/?tkn={session.access_token}"
            workspace.status = 'active'
            workspace.last_active = datetime.now()
            
            # Save session and workspace data
            self._save_session(session)
            self._save_workspace(workspace)
            
            logger.info(f"VS Code server started on port {session.port} with PID {process.pid}")
            
            # Monitor process output
            for line in process.stdout:
                pass  # Just consume output to prevent blocking
            
            # Process ended
            return_code = process.wait()
            
            # Update session and workspace status
            session.status = 'inactive'
            session.pid = None
            workspace.status = 'inactive'
            
            # Save session and workspace data
            self._save_session(session)
            self._save_workspace(workspace)
            
            logger.info(f"VS Code server process exited with code {return_code}")
            
            # Clean up
            if session.id in self.processes:
                del self.processes[session.id]
                
        except Exception as e:
            logger.error(f"Error in VS Code server process: {str(e)}")
            
            # Update session status
            if session.id in self.sessions:
                session.status = 'error'
                self._save_session(session)
            
            # Clean up
            if session.id in self.processes:
                del self.processes[session.id]
    
    def stop_session(self, session_id: str) -> bool:
        """
        Stop a VS Code session.
        
        Args:
            session_id: ID of the session to stop
            
        Returns:
            True if successful, False otherwise
        """
        if not self.initialized:
            logger.error("VS Code server not initialized")
            return False
        
        # Check if the session exists
        if session_id not in self.sessions:
            logger.error(f"Session not found: {session_id}")
            return False
        
        session = self.sessions[session_id]
        
        try:
            # Check if the process is running
            if session.id in self.processes:
                process = self.processes[session.id]
                
                # Try to terminate gracefully
                process.terminate()
                
                # Wait for process to terminate
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    # Force kill if it didn't terminate
                    process.kill()
                
                # Remove from processes dict
                del self.processes[session.id]
            
            # Update session status
            session.status = 'inactive'
            session.pid = None
            
            # Save session data
            self._save_session(session)
            
            # Update workspace status
            workspace_id = session.workspace_id
            if workspace_id in self.workspaces:
                workspace = self.workspaces[workspace_id]
                workspace.status = 'inactive'
                self._save_workspace(workspace)
            
            logger.info(f"Stopped session: {session_id}")
            return True
        except Exception as e:
            logger.error(f"Error stopping session: {str(e)}")
            return False
    
    def get_workspace(self, workspace_id: str) -> Optional[Dict[str, Any]]:
        """
        Get details of a workspace.
        
        Args:
            workspace_id: ID of the workspace to get
            
        Returns:
            Workspace details or None if not found
        """
        if not self.initialized:
            logger.error("VS Code server not initialized")
            return None
        
        # Check if the workspace exists
        if workspace_id not in self.workspaces:
            logger.error(f"Workspace not found: {workspace_id}")
            return None
        
        workspace = self.workspaces[workspace_id]
        
        # Convert to dict and handle datetime serialization
        workspace_dict = asdict(workspace)
        workspace_dict['created_at'] = workspace.created_at.isoformat()
        workspace_dict['last_active'] = workspace.last_active.isoformat()
        
        return workspace_dict
    
    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get details of a session.
        
        Args:
            session_id: ID of the session to get
            
        Returns:
            Session details or None if not found
        """
        if not self.initialized:
            logger.error("VS Code server not initialized")
            return None
        
        # Check if the session exists
        if session_id not in self.sessions:
            logger.error(f"Session not found: {session_id}")
            return None
        
        session = self.sessions[session_id]
        
        # Convert to dict and handle datetime serialization
        session_dict = asdict(session)
        session_dict['start_time'] = session.start_time.isoformat()
        session_dict['last_activity'] = session.last_activity.isoformat()
        
        return session_dict
    
    def list_workspaces(self, owner_id: Optional[str] = None, 
                      owner_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        List workspaces, optionally filtered by owner.
        
        Args:
            owner_id: Optional owner ID to filter by
            owner_type: Optional owner type to filter by
            
        Returns:
            List of workspace details
        """
        if not self.initialized:
            logger.error("VS Code server not initialized")
            return []
        
        workspaces = []
        
        for workspace in self.workspaces.values():
            # Apply filters
            if owner_id and workspace.owner_id != owner_id:
                continue
            if owner_type and workspace.owner_type != owner_type:
                continue
            
            # Convert to dict and handle datetime serialization
            workspace_dict = asdict(workspace)
            workspace_dict['created_at'] = workspace.created_at.isoformat()
            workspace_dict['last_active'] = workspace.last_active.isoformat()
            
            workspaces.append(workspace_dict)
        
        return workspaces
    
    def list_sessions(self, workspace_id: Optional[str] = None, 
                    agent_id: Optional[str] = None, 
                    user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        List sessions, optionally filtered by workspace, agent, or user.
        
        Args:
            workspace_id: Optional workspace ID to filter by
            agent_id: Optional agent ID to filter by
            user_id: Optional user ID to filter by
            
        Returns:
            List of session details
        """
        if not self.initialized:
            logger.error("VS Code server not initialized")
            return []
        
        sessions = []
        
        for session in self.sessions.values():
            # Apply filters
            if workspace_id and session.workspace_id != workspace_id:
                continue
            if agent_id and session.agent_id != agent_id:
                continue
            if user_id and session.user_id != user_id:
                continue
            
            # Convert to dict and handle datetime serialization
            session_dict = asdict(session)
            session_dict['start_time'] = session.start_time.isoformat()
            session_dict['last_activity'] = session.last_activity.isoformat()
            
            sessions.append(session_dict)
        
        return sessions
    
    def execute_command(self, session_id: str, command: str) -> Dict[str, Any]:
        """
        Execute a command in a workspace.
        
        Args:
            session_id: ID of the session to execute in
            command: Command to execute
            
        Returns:
            Result of the command execution
        """
        if not self.initialized:
            logger.error("VS Code server not initialized")
            return {"success": False, "error": "VS Code server not initialized"}
        
        # Check if the session exists
        if session_id not in self.sessions:
            logger.error(f"Session not found: {session_id}")
            return {"success": False, "error": f"Session not found: {session_id}"}
        
        session = self.sessions[session_id]
        
        # Check if the session is active
        if session.status != 'active':
            logger.error(f"Session not active: {session_id}")
            return {"success": False, "error": f"Session not active: {session_id}"}
        
        # Get the workspace
        workspace_id = session.workspace_id
        if workspace_id not in self.workspaces:
            logger.error(f"Workspace not found: {workspace_id}")
            return {"success": False, "error": f"Workspace not found: {workspace_id}"}
        
        workspace = self.workspaces[workspace_id]
        
        try:
            # Execute the command in the workspace directory
            result = subprocess.run(
                command,
                shell=True,
                cwd=workspace.path,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            # Update last activity times
            session.last_activity = datetime.now()
            workspace.last_active = datetime.now()
            
            # Save session and workspace data
            self._save_session(session)
            self._save_workspace(workspace)
            
            # Return the result
            return {
                "success": True,
                "exit_code": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr
            }
        except subprocess.TimeoutExpired:
            logger.error(f"Command timed out: {command}")
            return {"success": False, "error": "Command timed out"}
        except Exception as e:
            logger.error(f"Error executing command: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def delete_workspace(self, workspace_id: str) -> bool:
        """
        Delete a workspace.
        
        Args:
            workspace_id: ID of the workspace to delete
            
        Returns:
            True if successful, False otherwise
        """
        if not self.initialized:
            logger.error("VS Code server not initialized")
            return False
        
        # Check if the workspace exists
        if workspace_id not in self.workspaces:
            logger.error(f"Workspace not found: {workspace_id}")
            return False
        
        workspace = self.workspaces[workspace_id]
        
        try:
            # Stop any active sessions for this workspace
            for session_id, session in list(self.sessions.items()):
                if session.workspace_id == workspace_id:
                    self.stop_session(session_id)
                    del self.sessions[session_id]
            
            # Delete workspace directory
            shutil.rmtree(workspace.path, ignore_errors=True)
            
            # Remove from workspaces dict
            del self.workspaces[workspace_id]
            
            logger.info(f"Deleted workspace: {workspace_id}")
            return True
        except Exception as e:
            logger.error(f"Error deleting workspace: {str(e)}")
            return False
    
    def cleanup(self) -> None:
        """Clean up resources and stop all sessions."""
        if not self.initialized:
            return
        
        logger.info("Cleaning up VS Code server resources")
        
        # Stop all sessions
        for session_id in list(self.sessions.keys()):
            self.stop_session(session_id)
        
        # Clear dictionaries
        self.sessions.clear()
        self.workspaces.clear()
        self.processes.clear()

# Singleton instance
vscode_server = VSCodeServer()
