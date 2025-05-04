"""
Model Context Protocol (MCP) Client

This module provides a client for interacting with the MCP server,
enabling other parts of the application to easily access and
manipulate context data without direct dependency on the server.
"""

import requests
import json
from typing import Dict, List, Any, Optional, Union
from flask import current_app, session

class MCPClient:
    """Client for interacting with the MCP server."""
    
    def __init__(self, base_url=None):
        """
        Initialize the MCP client.
        
        Args:
            base_url: Base URL for the MCP server (defaults to current app URL)
        """
        self.base_url = base_url or ''  # Will use relative URLs within the same app
    
    def get_status(self) -> Dict[str, Any]:
        """Get the status of the MCP server."""
        try:
            response = requests.get(f"{self.base_url}/api/mcp/status")
            if response.status_code == 200:
                return response.json()
            else:
                return {"success": False, "error": "Failed to get MCP status"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def get_context(self, session_id: Optional[str] = None, token_limit: int = 4000) -> Dict[str, Any]:
        """
        Get context for a session.
        
        Args:
            session_id: Optional session ID (if None, uses current session)
            token_limit: Maximum token limit for context
            
        Returns:
            Context dictionary
        """
        try:
            params = {"token_limit": token_limit}
            if session_id:
                params["session_id"] = session_id
                
            response = requests.get(f"{self.base_url}/api/mcp/context", params=params)
            if response.status_code == 200:
                return response.json().get("context", {})
            else:
                return {}
        except Exception as e:
            print(f"Error getting context: {str(e)}")
            return {}
    
    def add_context(self, item_type: str, content: Dict[str, Any], 
                   ttl: int = 3600, session_id: Optional[str] = None) -> str:
        """
        Add a new context item.
        
        Args:
            item_type: Type of context item
            content: Content to store
            ttl: Time to live in seconds
            session_id: Optional session ID
            
        Returns:
            ID of the created item or error message
        """
        try:
            data = {
                "type": item_type,
                "content": content,
                "ttl": ttl
            }
            
            if session_id:
                data["session_id"] = session_id
                
            response = requests.post(f"{self.base_url}/api/mcp/context/add", json=data)
            if response.status_code == 200:
                return response.json().get("item_id", "")
            else:
                return f"Error: {response.json().get('error', 'Unknown error')}"
        except Exception as e:
            return f"Exception: {str(e)}"
    
    def get_item(self, item_id: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get a specific context item.
        
        Args:
            item_id: ID of the item to retrieve
            session_id: Optional session ID
            
        Returns:
            The item data or empty dict if not found
        """
        try:
            params = {}
            if session_id:
                params["session_id"] = session_id
                
            response = requests.get(f"{self.base_url}/api/mcp/context/{item_id}", params=params)
            if response.status_code == 200:
                return response.json().get("item", {})
            else:
                return {}
        except Exception as e:
            print(f"Error getting item: {str(e)}")
            return {}
    
    def update_item(self, item_id: str, content: Dict[str, Any], 
                   session_id: Optional[str] = None) -> bool:
        """
        Update a context item.
        
        Args:
            item_id: ID of the item to update
            content: New content
            session_id: Optional session ID
            
        Returns:
            True if successful, False otherwise
        """
        try:
            data = {"content": content}
            if session_id:
                data["session_id"] = session_id
                
            response = requests.put(f"{self.base_url}/api/mcp/context/{item_id}", json=data)
            return response.status_code == 200
        except Exception:
            return False
    
    def get_by_type(self, item_type: str, session_id: Optional[str] = None, 
                   max_items: int = 10) -> List[Dict[str, Any]]:
        """
        Get context items by type.
        
        Args:
            item_type: Type of items to retrieve
            session_id: Optional session ID
            max_items: Maximum number of items to return
            
        Returns:
            List of items matching the type
        """
        try:
            params = {"max_items": max_items}
            if session_id:
                params["session_id"] = session_id
                
            response = requests.get(f"{self.base_url}/api/mcp/context/type/{item_type}", params=params)
            if response.status_code == 200:
                return response.json().get("items", [])
            else:
                return []
        except Exception as e:
            print(f"Error getting items by type: {str(e)}")
            return []
    
    def record_behavior(self, action: str, screen: str, 
                      duration: int = 0, details: Dict[str, Any] = None) -> str:
        """
        Record user behavior.
        
        Args:
            action: The action performed
            screen: The screen where it occurred
            duration: Time spent in seconds
            details: Additional details
            
        Returns:
            ID of the created item or error message
        """
        try:
            data = {
                "action": action,
                "screen": screen,
                "duration": duration,
                "details": details or {}
            }
            
            response = requests.post(f"{self.base_url}/api/mcp/behavior", json=data)
            if response.status_code == 200:
                return response.json().get("item_id", "")
            else:
                return f"Error: {response.json().get('error', 'Unknown error')}"
        except Exception as e:
            return f"Exception: {str(e)}"
    
    def record_interaction(self, user_message: str, ai_response: str, 
                         context: Dict[str, Any] = None) -> str:
        """
        Record an AI interaction.
        
        Args:
            user_message: The user's message
            ai_response: The AI's response
            context: Additional context
            
        Returns:
            ID of the created item or error message
        """
        try:
            data = {
                "user_message": user_message,
                "ai_response": ai_response,
                "context": context or {}
            }
            
            response = requests.post(f"{self.base_url}/api/mcp/interaction", json=data)
            if response.status_code == 200:
                return response.json().get("item_id", "")
            else:
                return f"Error: {response.json().get('error', 'Unknown error')}"
        except Exception as e:
            return f"Exception: {str(e)}"
    
    def store_github_info(self, repo_name: str, repo_info: Dict[str, Any]) -> str:
        """
        Store GitHub repository information.
        
        Args:
            repo_name: Name of the repository
            repo_info: Repository information
            
        Returns:
            ID of the created item or error message
        """
        try:
            data = {
                "repo_name": repo_name,
                "repo_info": repo_info
            }
            
            response = requests.post(f"{self.base_url}/api/mcp/github", json=data)
            if response.status_code == 200:
                return response.json().get("item_id", "")
            else:
                return f"Error: {response.json().get('error', 'Unknown error')}"
        except Exception as e:
            return f"Exception: {str(e)}"
    
    def cleanup(self) -> int:
        """
        Clean up expired context items.
        
        Returns:
            Number of items removed
        """
        try:
            response = requests.post(f"{self.base_url}/api/mcp/cleanup")
            if response.status_code == 200:
                return response.json().get("removed_count", 0)
            else:
                return 0
        except Exception:
            return 0
    
    def get_recent_activities(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get recent user activities.
        
        Args:
            limit: Maximum number of activities to return
            
        Returns:
            List of recent activities
        """
        try:
            params = {"limit": limit}
            response = requests.get(f"{self.base_url}/api/mcp/activities", params=params)
            if response.status_code == 200:
                return response.json().get("activities", [])
            else:
                return []
        except Exception as e:
            print(f"Error getting recent activities: {str(e)}")
            return []

# Singleton instance
mcp_client = MCPClient()
