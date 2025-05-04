"""
VS Code Tools for Backdoor AI

This module provides tools for interacting with VS Code:
- Creating and managing workspaces
- Starting and stopping VS Code sessions
- Executing commands in workspaces
- Managing files and directories

These tools use the VSCodeManager to interact with VS Code.
"""

import os
import json
import logging
import shutil
from typing import Dict, List, Any, Optional, Union

from app.ai.vscode_integration import vscode_manager
from app.ai.tools import BaseTool, ToolType

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("vscode_tools")

class VSCodeCreateWorkspaceTool(BaseTool):
    """Tool for creating a VS Code workspace."""
    name = ToolType.VSCODE_CREATE_WORKSPACE
    description = "Create a new VS Code workspace for editing code."
    parameters = {
        "properties": {
            "name": {
                "description": "Name of the workspace",
                "type": "string"
            },
            "template": {
                "description": "Optional template to initialize the workspace (e.g. 'python', 'node', 'web', 'empty')",
                "type": "string"
            }
        },
        "required": ["name"],
        "type": "object"
    }
    required = ["name"]

    def execute(self, name: str, template: Optional[str] = None) -> Dict[str, Any]:
        """
        Create a new VS Code workspace.
        
        Args:
            name: Name of the workspace
            template: Optional template to initialize the workspace
            
        Returns:
            Result of workspace creation
        """
        # Get agent ID from context if available
        from flask import g
        agent_id = getattr(g, 'agent_id', 'unknown')
        
        result = vscode_manager.create_workspace(
            name=name,
            agent_id=agent_id,
            template=template
        )
        
        if not result.get('success', False):
            return {
                "success": False,
                "error": result.get('error', 'Failed to create workspace')
            }
        
        # Return success with workspace info
        return {
            "success": True,
            "message": f"Workspace '{name}' created successfully",
            "workspace_id": result.get('workspace', {}).get('id'),
            "workspace_path": result.get('workspace', {}).get('path')
        }

class VSCodeStartSessionTool(BaseTool):
    """Tool for starting a VS Code session for a workspace."""
    name = ToolType.VSCODE_START_SESSION
    description = "Start a new VS Code session for a workspace."
    parameters = {
        "properties": {
            "workspace_id": {
                "description": "ID of the workspace to start a session for",
                "type": "string"
            }
        },
        "required": ["workspace_id"],
        "type": "object"
    }
    required = ["workspace_id"]

    def execute(self, workspace_id: str) -> Dict[str, Any]:
        """
        Start a new VS Code session for a workspace.
        
        Args:
            workspace_id: ID of the workspace to start a session for
            
        Returns:
            Result of session creation
        """
        # Get agent ID from context if available
        from flask import g
        agent_id = getattr(g, 'agent_id', 'unknown')
        
        result = vscode_manager.start_workspace(
            workspace_id=workspace_id,
            agent_id=agent_id
        )
        
        if not result.get('success', False):
            return {
                "success": False,
                "error": result.get('error', 'Failed to start session')
            }
        
        session_info = result.get('session', {})
        
        # Return success with session info
        return {
            "success": True,
            "message": "Session started successfully",
            "session_id": session_info.get('id'),
            "access_url": session_info.get('access_url'),
            "port": session_info.get('port'),
            "status": session_info.get('status')
        }

class VSCodeStopSessionTool(BaseTool):
    """Tool for stopping a VS Code session."""
    name = ToolType.VSCODE_STOP_SESSION
    description = "Stop a VS Code session."
    parameters = {
        "properties": {
            "session_id": {
                "description": "ID of the session to stop",
                "type": "string"
            }
        },
        "required": ["session_id"],
        "type": "object"
    }
    required = ["session_id"]

    def execute(self, session_id: str) -> Dict[str, Any]:
        """
        Stop a VS Code session.
        
        Args:
            session_id: ID of the session to stop
            
        Returns:
            Result of session termination
        """
        result = vscode_manager.stop_workspace(session_id)
        
        if not result.get('success', False):
            return {
                "success": False,
                "error": result.get('error', 'Failed to stop session')
            }
        
        # Return success message
        return {
            "success": True,
            "message": result.get('message', 'Session stopped successfully')
        }

class VSCodeListWorkspacesTool(BaseTool):
    """Tool for listing VS Code workspaces."""
    name = ToolType.VSCODE_LIST_WORKSPACES
    description = "List available VS Code workspaces."
    parameters = {
        "properties": {
            "agent_id": {
                "description": "Optional agent ID to filter by",
                "type": "string"
            }
        },
        "type": "object"
    }
    required = []

    def execute(self, agent_id: Optional[str] = None) -> Dict[str, Any]:
        """
        List VS Code workspaces.
        
        Args:
            agent_id: Optional agent ID to filter by
            
        Returns:
            List of workspaces
        """
        # Get agent ID from context if not provided
        if not agent_id:
            from flask import g
            agent_id = getattr(g, 'agent_id', None)
        
        result = vscode_manager.list_workspaces(agent_id)
        
        if not result.get('success', False):
            return {
                "success": False,
                "error": result.get('error', 'Failed to list workspaces')
            }
        
        # Return list of workspaces
        return {
            "success": True,
            "workspaces": result.get('workspaces', []),
            "count": result.get('count', 0)
        }

class VSCodeListSessionsTool(BaseTool):
    """Tool for listing VS Code sessions."""
    name = ToolType.VSCODE_LIST_SESSIONS
    description = "List active VS Code sessions."
    parameters = {
        "properties": {
            "agent_id": {
                "description": "Optional agent ID to filter by",
                "type": "string"
            }
        },
        "type": "object"
    }
    required = []

    def execute(self, agent_id: Optional[str] = None) -> Dict[str, Any]:
        """
        List VS Code sessions.
        
        Args:
            agent_id: Optional agent ID to filter by
            
        Returns:
            List of sessions
        """
        # Get agent ID from context if not provided
        if not agent_id:
            from flask import g
            agent_id = getattr(g, 'agent_id', None)
        
        result = vscode_manager.list_sessions(agent_id)
        
        if not result.get('success', False):
            return {
                "success": False,
                "error": result.get('error', 'Failed to list sessions')
            }
        
        # Return list of sessions
        return {
            "success": True,
            "sessions": result.get('sessions', []),
            "count": result.get('count', 0)
        }

class VSCodeExecuteCommandTool(BaseTool):
    """Tool for executing a command in a VS Code workspace."""
    name = ToolType.VSCODE_EXECUTE_COMMAND
    description = "Execute a command in a VS Code workspace."
    parameters = {
        "properties": {
            "session_id": {
                "description": "ID of the session to execute the command in",
                "type": "string"
            },
            "command": {
                "description": "Command to execute",
                "type": "string"
            }
        },
        "required": ["session_id", "command"],
        "type": "object"
    }
    required = ["session_id", "command"]

    def execute(self, session_id: str, command: str) -> Dict[str, Any]:
        """
        Execute a command in a VS Code workspace.
        
        Args:
            session_id: ID of the session to execute the command in
            command: Command to execute
            
        Returns:
            Result of command execution
        """
        result = vscode_manager.execute_command(session_id, command)
        
        if not result.get('success', False):
            return {
                "success": False,
                "error": result.get('error', 'Failed to execute command')
            }
        
        # Return command execution result
        return {
            "success": True,
            "exit_code": result.get('exit_code'),
            "stdout": result.get('stdout', ''),
            "stderr": result.get('stderr', '')
        }

class VSCodeDeleteWorkspaceTool(BaseTool):
    """Tool for deleting a VS Code workspace."""
    name = ToolType.VSCODE_DELETE_WORKSPACE
    description = "Delete a VS Code workspace."
    parameters = {
        "properties": {
            "workspace_id": {
                "description": "ID of the workspace to delete",
                "type": "string"
            }
        },
        "required": ["workspace_id"],
        "type": "object"
    }
    required = ["workspace_id"]

    def execute(self, workspace_id: str) -> Dict[str, Any]:
        """
        Delete a VS Code workspace.
        
        Args:
            workspace_id: ID of the workspace to delete
            
        Returns:
            Result of workspace deletion
        """
        result = vscode_manager.delete_workspace(workspace_id)
        
        if not result.get('success', False):
            return {
                "success": False,
                "error": result.get('error', 'Failed to delete workspace')
            }
        
        # Return success message
        return {
            "success": True,
            "message": result.get('message', 'Workspace deleted successfully')
        }

def register_vscode_tools():
    """Register VS Code tools with the tool registry."""
    from app.ai.tools import tool_registry
    
    # Register tools with the registry
    tools = [
        VSCodeCreateWorkspaceTool(),
        VSCodeStartSessionTool(),
        VSCodeStopSessionTool(),
        VSCodeListWorkspacesTool(),
        VSCodeListSessionsTool(),
        VSCodeExecuteCommandTool(),
        VSCodeDeleteWorkspaceTool()
    ]
    
    for tool in tools:
        tool_registry.register_tool(tool)
    
    logger.info(f"Registered {len(tools)} VS Code tools")
