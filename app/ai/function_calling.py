"""
Function Calling Implementation for Backdoor AI

This module provides a function calling implementation for Backdoor AI, inspired by
the OpenHands function calling implementation but adapted for Python, Flask, and
SQLAlchemy integration.
"""

import json
import logging
from typing import Dict, List, Any, Optional, Union

# Set up logging
logger = logging.getLogger("function_calling")


class FunctionCallError(Exception):
    """Base error class for function call-related errors."""
    pass


class FunctionCallValidationError(FunctionCallError):
    """Error raised when function call validation fails."""
    pass


class FunctionCallNotExistsError(FunctionCallError):
    """Error raised when a function call references a non-existent function."""
    pass


class ToolCallMetadata:
    """Metadata for a tool call."""
    
    def __init__(
        self,
        tool_call_id: str,
        function_name: str,
        model_response: Any,
        total_calls_in_response: int = 1
    ):
        """
        Initialize tool call metadata.
        
        Args:
            tool_call_id: ID of the tool call
            function_name: Name of the function called
            model_response: The full model response
            total_calls_in_response: Total number of calls in the response
        """
        self.tool_call_id = tool_call_id
        self.function_name = function_name
        self.model_response = model_response
        self.total_calls_in_response = total_calls_in_response
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "tool_call_id": self.tool_call_id,
            "function_name": self.function_name,
            "total_calls_in_response": self.total_calls_in_response
        }


def response_to_actions(response: Any, available_tools: List[str]) -> List[Dict[str, Any]]:
    """
    Convert a model response to a list of actions.
    
    Args:
        response: The model response
        available_tools: List of available tool names
        
    Returns:
        List of actions
    """
    actions = []
    
    # Extract the message from the response
    if hasattr(response, 'choices') and response.choices:
        choice = response.choices[0]
        if hasattr(choice, 'message'):
            message = choice.message
        else:
            message = choice
    else:
        message = response
    
    # Check if there are tool calls
    if hasattr(message, 'tool_calls') and message.tool_calls:
        # Extract thought from content if present
        thought = ''
        if hasattr(message, 'content') and message.content:
            thought = message.content
        
        # Process each tool call
        for i, tool_call in enumerate(message.tool_calls):
            try:
                # Parse arguments
                if hasattr(tool_call.function, 'arguments'):
                    try:
                        arguments = json.loads(tool_call.function.arguments)
                    except json.JSONDecodeError as e:
                        raise FunctionCallValidationError(
                            f"Failed to parse tool call arguments: {tool_call.function.arguments}"
                        ) from e
                else:
                    arguments = {}
                
                # Check if the tool exists
                function_name = tool_call.function.name
                if function_name not in available_tools:
                    raise FunctionCallNotExistsError(
                        f"Tool {function_name} is not registered. Available tools: {available_tools}"
                    )
                
                # Create action
                action = {
                    "type": "tool_call",
                    "tool_name": function_name,
                    "parameters": arguments,
                    "tool_call_id": tool_call.id,
                    "thought": thought if i == 0 else ""
                }
                
                actions.append(action)
            except Exception as e:
                logger.error(f"Error processing tool call: {e}")
                # Add error action
                actions.append({
                    "type": "error",
                    "error": str(e),
                    "error_type": "tool_call_processing"
                })
    else:
        # No tool calls, treat as a message
        content = message.content if hasattr(message, 'content') else str(message)
        actions.append({
            "type": "message",
            "content": content
        })
    
    return actions


def execute_tool_call(tool_call: Dict[str, Any], tool_registry: Any) -> Dict[str, Any]:
    """
    Execute a tool call.
    
    Args:
        tool_call: The tool call to execute
        tool_registry: The tool registry to use
        
    Returns:
        The result of the tool execution
    """
    try:
        tool_name = tool_call.get("tool_name")
        parameters = tool_call.get("parameters", {})
        
        if not tool_name:
            raise FunctionCallValidationError("Missing tool_name in tool call")
        
        # Execute the tool
        result = tool_registry.execute_tool(
            name=tool_name,
            parameters=parameters
        )
        
        return {
            "type": "tool_result",
            "tool_name": tool_name,
            "tool_call_id": tool_call.get("tool_call_id"),
            "result": result
        }
    except Exception as e:
        logger.error(f"Error executing tool call: {e}")
        return {
            "type": "error",
            "error": str(e),
            "error_type": "tool_execution"
        }

