"""
Conversation Memory for Backdoor AI

This module provides a conversation memory system for Backdoor AI, inspired by
the OpenHands conversation memory implementation but adapted for Python, Flask, and
SQLAlchemy integration.
"""

import logging
from typing import Dict, List, Any, Optional, Union
from datetime import datetime

# Set up logging
logger = logging.getLogger("conversation_memory")


class Message:
    """A message in a conversation."""
    
    def __init__(
        self,
        role: str,
        content: str,
        name: Optional[str] = None,
        tool_calls: Optional[List[Dict[str, Any]]] = None,
        tool_call_id: Optional[str] = None,
        timestamp: Optional[datetime] = None
    ):
        """
        Initialize a message.
        
        Args:
            role: The role of the message sender (system, user, assistant, tool)
            content: The content of the message
            name: Optional name of the message sender
            tool_calls: Optional list of tool calls in the message
            tool_call_id: Optional ID of the tool call this message is responding to
            timestamp: Optional timestamp of the message
        """
        self.role = role
        self.content = content
        self.name = name
        self.tool_calls = tool_calls
        self.tool_call_id = tool_call_id
        self.timestamp = timestamp or datetime.utcnow()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        result = {
            "role": self.role,
            "content": self.content
        }
        
        if self.name:
            result["name"] = self.name
        
        if self.tool_calls:
            result["tool_calls"] = self.tool_calls
        
        if self.tool_call_id:
            result["tool_call_id"] = self.tool_call_id
        
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Message':
        """Create a Message from a dictionary."""
        return cls(
            role=data["role"],
            content=data["content"],
            name=data.get("name"),
            tool_calls=data.get("tool_calls"),
            tool_call_id=data.get("tool_call_id"),
            timestamp=datetime.fromisoformat(data["timestamp"]) if "timestamp" in data else None
        )
    
    def __str__(self) -> str:
        """String representation of the message."""
        if self.role == "tool":
            return f"[{self.role}] {self.name}: {self.content}"
        elif self.name:
            return f"[{self.role}] {self.name}: {self.content}"
        else:
            return f"[{self.role}] {self.content}"


class ConversationMemory:
    """
    Manages conversation history and provides methods for processing and retrieving messages.
    """
    
    def __init__(self, max_messages: int = 100):
        """
        Initialize conversation memory.
        
        Args:
            max_messages: Maximum number of messages to store
        """
        self.messages: List[Message] = []
        self.max_messages = max_messages
    
    def add_message(self, message: Union[Message, Dict[str, Any]]) -> None:
        """
        Add a message to the conversation history.
        
        Args:
            message: The message to add, either a Message object or a dictionary
        """
        if isinstance(message, dict):
            message = Message.from_dict(message)
        
        self.messages.append(message)
        
        # Trim if needed
        if len(self.messages) > self.max_messages:
            self.messages = self.messages[-self.max_messages:]
    
    def get_messages(self, 
                    start_index: Optional[int] = None, 
                    end_index: Optional[int] = None,
                    as_dict: bool = False) -> List[Union[Message, Dict[str, Any]]]:
        """
        Get messages from the conversation history.
        
        Args:
            start_index: Optional start index (inclusive)
            end_index: Optional end index (exclusive)
            as_dict: Whether to return messages as dictionaries
            
        Returns:
            List of messages or message dictionaries
        """
        messages = self.messages[start_index:end_index]
        
        if as_dict:
            return [msg.to_dict() for msg in messages]
        else:
            return messages
    
    def clear(self) -> None:
        """Clear the conversation history."""
        self.messages = []
    
    def get_last_user_message(self) -> Optional[Message]:
        """Get the last user message in the conversation."""
        for message in reversed(self.messages):
            if message.role == "user":
                return message
        return None
    
    def get_last_assistant_message(self) -> Optional[Message]:
        """Get the last assistant message in the conversation."""
        for message in reversed(self.messages):
            if message.role == "assistant":
                return message
        return None
    
    def get_system_message(self) -> Optional[Message]:
        """Get the system message in the conversation."""
        for message in self.messages:
            if message.role == "system":
                return message
        return None
    
    def process_events(self, events: List[Dict[str, Any]]) -> List[Message]:
        """
        Process events into messages.
        
        Args:
            events: List of events to process
            
        Returns:
            List of processed messages
        """
        messages = []
        
        for event in events:
            event_type = event.get("type")
            
            if event_type == "message":
                # Process message event
                role = event.get("source", "user")
                if role == "agent":
                    role = "assistant"
                
                content = event.get("content", "")
                
                message = Message(
                    role=role,
                    content=content,
                    timestamp=datetime.fromisoformat(event.get("timestamp")) if "timestamp" in event else None
                )
                
                messages.append(message)
                self.add_message(message)
            
            elif event_type == "tool_call":
                # Process tool call event
                tool_name = event.get("tool_name", "unknown_tool")
                tool_input = event.get("input", {})
                
                # Create assistant message with tool call
                message = Message(
                    role="assistant",
                    content="",
                    tool_calls=[{
                        "id": event.get("id", ""),
                        "type": "function",
                        "function": {
                            "name": tool_name,
                            "arguments": tool_input
                        }
                    }],
                    timestamp=datetime.fromisoformat(event.get("timestamp")) if "timestamp" in event else None
                )
                
                messages.append(message)
                self.add_message(message)
            
            elif event_type == "tool_result":
                # Process tool result event
                tool_call_id = event.get("tool_call_id", "")
                content = event.get("result", "")
                
                # Create tool message
                message = Message(
                    role="tool",
                    content=content,
                    name=event.get("tool_name", "unknown_tool"),
                    tool_call_id=tool_call_id,
                    timestamp=datetime.fromisoformat(event.get("timestamp")) if "timestamp" in event else None
                )
                
                messages.append(message)
                self.add_message(message)
        
        return messages
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "messages": [msg.to_dict() for msg in self.messages],
            "max_messages": self.max_messages
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ConversationMemory':
        """Create a ConversationMemory from a dictionary."""
        memory = cls(max_messages=data.get("max_messages", 100))
        
        for msg_data in data.get("messages", []):
            memory.add_message(Message.from_dict(msg_data))
        
        return memory

