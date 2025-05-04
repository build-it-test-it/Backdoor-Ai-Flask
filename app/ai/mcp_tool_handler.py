"""
MCP Tool Handler

This module provides tool handling capabilities for the Model Context Protocol (MCP) server.
It acts as a bridge between the MCP server and the tool registry, allowing for centralized
tool execution and tracking.

All tool usage should go through this handler to ensure proper tracking, permissions,
and context management.
"""

import json
import os
import logging
import time
import traceback
from typing import Dict, List, Any, Optional, Union
from datetime import datetime

from app.ai.tools import tool_registry, ToolType, BaseTool
from app.ai.mcp_server import mcp_server
from app.ai.mcp_agents import agent_manager, AgentRole
from app.database import db

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("mcp_tool_handler")

class MCPToolHandler:
    """
    Handles tool execution through the MCP server.
    
    This class provides methods for executing tools, managing permissions,
    and tracking tool usage across the application.
    """
    
    def __init__(self):
        """Initialize the MCP tool handler."""
        self.enabled_tools = {t.value for t in ToolType}  # All tools enabled by default
        self.tool_usage_history = []
        self.permissions = {}  # role -> {tool_type: bool}
        
        # Set up default permissions
        self._init_default_permissions()
    
    def _init_default_permissions(self):
        """Initialize default tool permissions for different roles."""
        # Set up default permissions for different roles
        self.permissions = {
            # Assistant role can use all tools
            AgentRole.ASSISTANT: {t.value: True for t in ToolType},
            
            # Developer role can use code-related tools
            AgentRole.DEVELOPER: {
                ToolType.EXECUTE_BASH: True,
                ToolType.THINK: True,
                ToolType.FINISH: True,
                ToolType.STR_REPLACE_EDITOR: True,
                ToolType.EXECUTE_IPYTHON_CELL: True,
                ToolType.WEB_READ: True,
                ToolType.BROWSER: False  # Restricted for security
            },
            
            # Analyst role can use data analysis tools
            AgentRole.ANALYST: {
                ToolType.EXECUTE_BASH: False,  # Restricted
                ToolType.THINK: True,
                ToolType.FINISH: True,
                ToolType.WEB_READ: True,
                ToolType.EXECUTE_IPYTHON_CELL: True,
                ToolType.STR_REPLACE_EDITOR: True,
                ToolType.BROWSER: False  # Restricted
            },
            
            # Executor role can execute commands but not edit files
            AgentRole.EXECUTOR: {
                ToolType.EXECUTE_BASH: True,
                ToolType.THINK: True,
                ToolType.FINISH: True,
                ToolType.WEB_READ: True,
                ToolType.EXECUTE_IPYTHON_CELL: True,
                ToolType.STR_REPLACE_EDITOR: False,  # Restricted
                ToolType.BROWSER: False  # Restricted
            },
            
            # Browser role can browse the web but not execute commands
            AgentRole.BROWSER: {
                ToolType.EXECUTE_BASH: False,  # Restricted
                ToolType.THINK: True,
                ToolType.FINISH: True,
                ToolType.WEB_READ: True,
                ToolType.EXECUTE_IPYTHON_CELL: False,  # Restricted
                ToolType.STR_REPLACE_EDITOR: False,  # Restricted
                ToolType.BROWSER: True
            }
        }
    
    def enable_tool(self, tool_type: str) -> bool:
        """
        Enable a tool type for all agents.
        
        Args:
            tool_type: Type of tool to enable
            
        Returns:
            True if the tool was enabled, False otherwise
        """
        if tool_type not in [t.value for t in ToolType]:
            return False
        
        self.enabled_tools.add(tool_type)
        logger.info(f"Enabled tool: {tool_type}")
        return True
    
    def disable_tool(self, tool_type: str) -> bool:
        """
        Disable a tool type for all agents.
        
        Args:
            tool_type: Type of tool to disable
            
        Returns:
            True if the tool was disabled, False otherwise
        """
        if tool_type not in [t.value for t in ToolType]:
            return False
        
        if tool_type in self.enabled_tools:
            self.enabled_tools.remove(tool_type)
            logger.info(f"Disabled tool: {tool_type}")
            return True
        
        return False
    
    def set_role_permission(self, role: str, tool_type: str, allowed: bool) -> bool:
        """
        Set permission for a role to use a specific tool.
        
        Args:
            role: Role to set permission for
            tool_type: Type of tool
            allowed: Whether the role is allowed to use the tool
            
        Returns:
            True if the permission was set, False otherwise
        """
        if role not in self.permissions:
            self.permissions[role] = {}
        
        if tool_type not in [t.value for t in ToolType]:
            return False
        
        self.permissions[role][tool_type] = allowed
        logger.info(f"Set permission for role {role} to use tool {tool_type}: {allowed}")
        return True
    
    def check_permission(self, role: str, tool_type: str) -> bool:
        """
        Check if a role has permission to use a specific tool.
        
        Args:
            role: Role to check permission for
            tool_type: Type of tool
            
        Returns:
            True if the role has permission, False otherwise
        """
        # Check if tool is enabled globally
        if tool_type not in self.enabled_tools:
            return False
        
        # Check role-specific permission
        if role in self.permissions and tool_type in self.permissions[role]:
            return self.permissions[role][tool_type]
        
        # Default deny
        return False
    
    def execute_tool(self, tool_type: str, agent_id: str = None, session_id: str = None, **kwargs) -> Dict[str, Any]:
        """
        Execute a tool with the given parameters.
        
        This method provides a centralized way to execute tools through the MCP,
        ensuring proper permissions, tracking, and context management.
        
        Args:
            tool_type: Type of tool to execute
            agent_id: Optional agent ID to execute the tool with
            session_id: Optional session ID (required if agent_id not provided)
            **kwargs: Parameters for the tool
            
        Returns:
            Result of the tool execution
        """
        # Check if tool is enabled globally
        if tool_type not in self.enabled_tools:
            error_msg = f"Tool {tool_type} is disabled globally"
            logger.error(error_msg)
            return {
                "success": False,
                "error": error_msg
            }
        
        # Execute with agent if agent_id is provided
        if agent_id:
            return agent_manager.execute_tool_with_agent(agent_id, tool_type, **kwargs)
        
        # Execute with default agent if session_id is provided
        if session_id:
            return agent_manager.execute_tool_with_default_agent(session_id, tool_type, **kwargs)
        
        # If neither agent_id nor session_id is provided, execute directly
        # This is for backward compatibility and should be avoided in new code
        logger.warning("Executing tool without agent or session context")
        
        # Record the tool usage
        timestamp = datetime.now().isoformat()
        usage = {
            'tool_type': tool_type,
            'params': kwargs,
            'timestamp': timestamp,
            'agent_id': None,
            'session_id': None
        }
        
        self.tool_usage_history.append(usage)
        
        # Execute the tool
        start_time = time.time()
        try:
            result = tool_registry.execute_tool(tool_type, **kwargs)
            execution_time = time.time() - start_time
            
            # Set success flag if not present
            if 'success' not in result:
                result['success'] = True
                
            # Record in database through MCP server
            try:
                mcp_server.record_tool_usage(
                    tool_type=tool_type,
                    params=kwargs,
                    result=result,
                    session_id=session_id,
                    agent_id=agent_id
                )
            except Exception as e:
                logger.error(f"Error recording tool usage in database: {str(e)}")
            
            # Add execution time to the result
            result['execution_time'] = execution_time
            
            return result
        except Exception as e:
            error_details = traceback.format_exc()
            error_msg = f"Error executing tool {tool_type}: {str(e)}"
            logger.error(f"{error_msg}\n{error_details}")
            
            error_result = {
                "success": False,
                "error": error_msg,
                "details": error_details,
                "execution_time": time.time() - start_time
            }
            
            # Record failed execution in database
            try:
                mcp_server.record_tool_usage(
                    tool_type=tool_type,
                    params=kwargs,
                    result=error_result,
                    session_id=session_id,
                    agent_id=agent_id
                )
            except Exception as ex:
                logger.error(f"Error recording failed tool usage: {str(ex)}")
            
            return error_result
    
    def get_tools_schema(self) -> List[Dict[str, Any]]:
        """
        Get the schema for all enabled tools.
        
        Returns:
            List of tool schemas
        """
        # Get schemas for enabled tools only
        schemas = []
        for tool_type in self.enabled_tools:
            schema = tool_registry.get_tool_schema(tool_type)
            if schema:
                schemas.append(schema)
        
        return schemas
    
    def get_tool_usage_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get the tool usage history.
        
        Args:
            limit: Maximum number of entries to return
            
        Returns:
            List of tool usage history entries
        """
        return self.tool_usage_history[-limit:]
    
    def get_tool_types(self) -> List[str]:
        """
        Get all available tool types.
        
        Returns:
            List of tool types
        """
        return [t.value for t in ToolType]

# Singleton instance
mcp_tool_handler = MCPToolHandler()
