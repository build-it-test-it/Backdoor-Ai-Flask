"""
Code Agent for Backdoor AI

This module provides a code agent for Backdoor AI, inspired by
the OpenHands CodeAct agent implementation but adapted for Python, Flask, and
SQLAlchemy integration.
"""

import logging
import os
from typing import Dict, List, Any, Optional
from collections import deque

from app.ai.agent.agent import Agent, AgentError
from app.ai.agent.agent_config import AgentConfig
from app.ai.mcp_models import AgentRole
from app.ai.memory.conversation_memory import ConversationMemory, Message
from app.ai.memory.condenser import Condenser, NoOpCondenser
from app.ai.function_calling import response_to_actions, execute_tool_call
from app.ai.tool_schema import tool_registry

# Set up logging
logger = logging.getLogger("code_agent")


class CodeAgent(Agent):
    """
    A code-focused agent for Backdoor AI.
    
    This agent is designed to help with coding tasks, providing assistance
    with code generation, debugging, and explanation.
    """
    
    def __init__(
        self,
        id: str,
        name: str,
        role: AgentRole,
        config: AgentConfig,
        session_id: Optional[str] = None
    ):
        """
        Initialize a code agent.
        
        Args:
            id: Unique identifier for the agent
            name: Human-readable name for the agent
            role: Role of the agent (determines permissions)
            config: Configuration for the agent
            session_id: Optional session ID for session-specific agents
        """
        super().__init__(id, name, role, config, session_id)
        
        # Initialize conversation memory
        self.conversation_memory = ConversationMemory(max_messages=100)
        
        # Initialize condenser
        self.condenser = NoOpCondenser()
        
        # Initialize tools
        self.tools = self._get_tools()
        
        # Initialize pending actions queue
        self.pending_actions = deque()
    
    def _get_tools(self) -> List[Dict[str, Any]]:
        """Get the tools available to this agent."""
        tools = []
        
        # Add tools based on configuration
        if self.config.enable_cmd:
            tools.append(tool_registry.get_tool_schema("run_command"))
        
        if self.config.enable_editor:
            tools.append(tool_registry.get_tool_schema("file_edit"))
            tools.append(tool_registry.get_tool_schema("file_read"))
        
        if self.config.enable_browsing:
            tools.append(tool_registry.get_tool_schema("web_search"))
            tools.append(tool_registry.get_tool_schema("web_read"))
        
        return tools
    
    def _get_system_message_content(self) -> str:
        """Get the system message content for this agent."""
        return f"""You are {self.name}, an AI coding assistant that helps with programming tasks.
        
You can help with:
- Writing code in various programming languages
- Debugging existing code
- Explaining code concepts
- Suggesting improvements to code
- Answering programming questions

You have access to the following tools:
- run_command: Run shell commands
- file_edit: Edit files
- file_read: Read files
- web_search: Search the web
- web_read: Read web pages

Always be helpful, accurate, and clear in your explanations.
"""
    
    async def step(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Perform one step of agent execution.
        
        Args:
            state: The current state of the agent's execution
            
        Returns:
            The result of the step
        """
        # Continue with pending actions if any
        if self.pending_actions:
            return self.pending_actions.popleft()
        
        # Check if we're done
        if self._complete:
            return {"type": "complete", "message": "Task complete"}
        
        # Get the conversation history
        history = state.get('history', [])
        
        # Process history into messages
        messages = self.conversation_memory.process_events(history)
        
        # Condense messages if needed
        condensed_messages = self.condenser.condense(messages)
        
        # Ensure we have a system message
        system_message = self.conversation_memory.get_system_message()
        if not system_message:
            system_message = Message(
                role="system",
                content=self._get_system_message_content()
            )
            condensed_messages.insert(0, system_message)
        
        # Format messages for the model
        formatted_messages = [msg.to_dict() for msg in condensed_messages]
        
        # Get model service
        from app.ai.model_service import model_service
        
        # Call the model
        response = model_service.chat_completion(
            messages=formatted_messages,
            tools=self.tools
        )
        
        # Check for errors
        if "error" in response:
            logger.error(f"Error from model service: {response['error']}")
            return {
                "type": "error",
                "error": response["error"],
                "error_type": "model_service"
            }
        
        # Process the response into actions
        available_tools = [tool["function"]["name"] for tool in self.tools]
        actions = response_to_actions(response, available_tools)
        
        # Queue up actions
        for action in actions:
            self.pending_actions.append(action)
        
        # Return the first action
        if self.pending_actions:
            return self.pending_actions.popleft()
        else:
            # Fallback if no actions were generated
            return {
                "type": "message",
                "content": "I'm not sure how to proceed. Could you provide more information?"
            }
    
    def reset(self) -> None:
        """Reset the agent."""
        super().reset()
        self.conversation_memory.clear()
        self.pending_actions.clear()


# Register the agent
Agent.register("CodeAgent", CodeAgent)

