"""
Condenser for Backdoor AI

This module provides a condenser system for Backdoor AI, inspired by
the OpenHands condenser implementation but adapted for Python, Flask, and
SQLAlchemy integration.
"""

import logging
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Union
from datetime import datetime

from app.ai.memory.conversation_memory import Message

# Set up logging
logger = logging.getLogger("condenser")


class Condenser(ABC):
    """
    Abstract base class for condensers.
    
    Condensers are responsible for condensing conversation history to fit within
    context windows and improve the quality of agent responses.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize a condenser.
        
        Args:
            config: Optional configuration for the condenser
        """
        self.config = config or {}
    
    @abstractmethod
    def condense(self, messages: List[Message]) -> List[Message]:
        """
        Condense a list of messages.
        
        Args:
            messages: List of messages to condense
            
        Returns:
            Condensed list of messages
        """
        pass
    
    @classmethod
    def from_config(cls, config: Dict[str, Any]) -> 'Condenser':
        """
        Create a condenser from a configuration.
        
        Args:
            config: Configuration for the condenser
            
        Returns:
            A condenser instance
        """
        condenser_type = config.get("type", "noop")
        
        if condenser_type == "noop":
            return NoOpCondenser(config)
        elif condenser_type == "summary":
            return SummaryCondenser(config)
        else:
            logger.warning(f"Unknown condenser type: {condenser_type}, using NoOpCondenser")
            return NoOpCondenser(config)


class NoOpCondenser(Condenser):
    """
    A condenser that does not modify the messages.
    """
    
    def condense(self, messages: List[Message]) -> List[Message]:
        """
        Return the messages unchanged.
        
        Args:
            messages: List of messages
            
        Returns:
            The same list of messages
        """
        return messages


class SummaryCondenser(Condenser):
    """
    A condenser that summarizes long conversations.
    
    This condenser keeps the system message and recent messages intact,
    but summarizes older messages to reduce context length.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize a summary condenser.
        
        Args:
            config: Optional configuration for the condenser
        """
        super().__init__(config)
        self.max_messages = config.get("max_messages", 10)
        self.keep_system_message = config.get("keep_system_message", True)
        self.keep_last_user_message = config.get("keep_last_user_message", True)
    
    def condense(self, messages: List[Message]) -> List[Message]:
        """
        Condense messages by summarizing older ones.
        
        Args:
            messages: List of messages to condense
            
        Returns:
            Condensed list of messages
        """
        if len(messages) <= self.max_messages:
            return messages
        
        # Keep system message if present and configured
        system_message = None
        if self.keep_system_message:
            for i, msg in enumerate(messages):
                if msg.role == "system":
                    system_message = msg
                    break
        
        # Keep last user message if configured
        last_user_message = None
        if self.keep_last_user_message:
            for msg in reversed(messages):
                if msg.role == "user":
                    last_user_message = msg
                    break
        
        # Calculate how many recent messages to keep
        keep_count = self.max_messages
        if system_message:
            keep_count -= 1
        if last_user_message:
            keep_count -= 1
        
        # Get recent messages
        recent_messages = messages[-keep_count:] if keep_count > 0 else []
        
        # Create summary message for older messages
        older_messages = messages[:-keep_count] if keep_count > 0 else messages
        
        # Filter out messages we're keeping separately
        older_messages = [
            msg for msg in older_messages 
            if (not system_message or msg != system_message) and 
               (not last_user_message or msg != last_user_message)
        ]
        
        if older_messages:
            # Create a simple summary
            summary_content = f"[Conversation history summary: {len(older_messages)} earlier messages omitted]"
            
            summary_message = Message(
                role="system",
                content=summary_content,
                name="summary",
                timestamp=datetime.utcnow()
            )
            
            # Combine messages in the right order
            result = []
            if system_message:
                result.append(system_message)
            
            result.append(summary_message)
            
            if last_user_message and last_user_message not in recent_messages:
                result.append(last_user_message)
            
            result.extend(recent_messages)
            
            return result
        else:
            # No older messages to summarize
            result = []
            if system_message:
                result.append(system_message)
            
            if last_user_message and last_user_message not in recent_messages:
                result.append(last_user_message)
            
            result.extend(recent_messages)
            
            return result

