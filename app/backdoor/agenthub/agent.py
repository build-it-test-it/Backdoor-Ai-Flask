"""
Base agent implementation for Backdoor.
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Union

from app.backdoor.core.config import AppConfig
from app.backdoor.core.logger import get_logger

logger = get_logger("agenthub.agent")

class Agent(ABC):
    """Base agent class for Backdoor."""
    
    def __init__(self, config: AppConfig, session_id: str):
        """Initialize the agent.
        
        Args:
            config: The application configuration.
            session_id: The session ID.
        """
        self.config = config
        self.session_id = session_id
        self.tools = []
        self.conversation_history = []
        self.tool_results = {}
        self.initialized = False
    
    @abstractmethod
    def initialize(self):
        """Initialize the agent."""
        pass
    
    @abstractmethod
    def process_message(self, message: str) -> Dict[str, Any]:
        """Process a message.
        
        Args:
            message: The message to process.
            
        Returns:
            The response.
        """
        pass
    
    @abstractmethod
    def execute_tool(self, tool_name: str, tool_args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool.
        
        Args:
            tool_name: The name of the tool to execute.
            tool_args: The arguments for the tool.
            
        Returns:
            The tool execution result.
        """
        pass
    
    @abstractmethod
    def get_status(self) -> Dict[str, Any]:
        """Get the agent status.
        
        Returns:
            The agent status.
        """
        pass
    
    def register_tool(self, tool: Dict[str, Any]):
        """Register a tool.
        
        Args:
            tool: The tool to register.
        """
        self.tools.append(tool)
        logger.info(f"Registered tool: {tool['name']}")
    
    def register_tools(self, tools: List[Dict[str, Any]]):
        """Register multiple tools.
        
        Args:
            tools: The tools to register.
        """
        for tool in tools:
            self.register_tool(tool)
    
    def add_to_conversation(self, role: str, content: str):
        """Add a message to the conversation history.
        
        Args:
            role: The role of the message sender.
            content: The message content.
        """
        self.conversation_history.append({
            "role": role,
            "content": content
        })
    
    def get_conversation_history(self) -> List[Dict[str, str]]:
        """Get the conversation history.
        
        Returns:
            The conversation history.
        """
        return self.conversation_history
    
    def clear_conversation_history(self):
        """Clear the conversation history."""
        self.conversation_history = []
        self.tool_results = {}
    
    def save_tool_result(self, tool_name: str, tool_args: Dict[str, Any], result: Any):
        """Save a tool execution result.
        
        Args:
            tool_name: The name of the tool.
            tool_args: The arguments for the tool.
            result: The tool execution result.
        """
        tool_id = f"{tool_name}_{len(self.tool_results)}"
        self.tool_results[tool_id] = {
            "tool_name": tool_name,
            "tool_args": tool_args,
            "result": result
        }
    
    def get_tool_result(self, tool_id: str) -> Optional[Dict[str, Any]]:
        """Get a tool execution result.
        
        Args:
            tool_id: The ID of the tool execution.
            
        Returns:
            The tool execution result.
        """
        return self.tool_results.get(tool_id)