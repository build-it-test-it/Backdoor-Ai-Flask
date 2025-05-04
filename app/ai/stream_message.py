"""
Stream Message System for Backdoor AI

This module provides a streaming message system based on Mentat's session_stream.py.
It enables bidirectional communication between clients and the server.

Features:
- Bidirectional communication
- Message queuing
- Event-based architecture
"""

import asyncio
import json
import logging
import uuid
from enum import Enum
from typing import Dict, List, Any, Optional, AsyncGenerator, Union, Callable, Set

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("stream_message")

class StreamMessageSource(str, Enum):
    """Source of a stream message."""
    CLIENT = "client"
    SERVER = "server"

class StreamMessage:
    """
    Message for bidirectional communication.
    Based on Mentat's StreamMessage class.
    """
    
    def __init__(self, 
                id: str, 
                channel: str, 
                source: StreamMessageSource, 
                data: Any, 
                extra: Optional[Dict[str, Any]] = None):
        """
        Initialize a stream message.
        
        Args:
            id: Unique message ID
            channel: Message channel
            source: Message source (client or server)
            data: Message data
            extra: Extra data
        """
        self.id = id
        self.channel = channel
        self.source = source
        self.data = data
        self.extra = extra or {}
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'StreamMessage':
        """Create a StreamMessage from a dictionary."""
        return cls(
            id=data.get('id', str(uuid.uuid4())),
            channel=data.get('channel', ''),
            source=StreamMessageSource(data.get('source', 'server')),
            data=data.get('data', {}),
            extra=data.get('extra', {})
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'id': self.id,
            'channel': self.channel,
            'source': self.source,
            'data': self.data,
            'extra': self.extra
        }
    
    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict())

class MessageStream:
    """
    Stream for bidirectional communication.
    Based on Mentat's SessionStream class.
    """
    
    def __init__(self):
        """Initialize a message stream."""
        self.queue = asyncio.Queue()
        self.listeners: Dict[str, Set[Callable[[StreamMessage], None]]] = {}
    
    def send_message(self, message: StreamMessage) -> None:
        """Send a message to the stream."""
        # Put the message in the queue
        self.queue.put_nowait(message)
        
        # Notify listeners
        self._notify_listeners(message)
    
    def send(self, channel: str, data: Any, source: StreamMessageSource = StreamMessageSource.SERVER, 
           extra: Optional[Dict[str, Any]] = None) -> None:
        """Send a message to the stream."""
        message = StreamMessage(
            id=str(uuid.uuid4()),
            channel=channel,
            source=source,
            data=data,
            extra=extra or {}
        )
        
        self.send_message(message)
    
    def add_listener(self, channel: str, callback: Callable[[StreamMessage], None]) -> None:
        """Add a listener for a specific channel."""
        if channel not in self.listeners:
            self.listeners[channel] = set()
        
        self.listeners[channel].add(callback)
    
    def remove_listener(self, channel: str, callback: Callable[[StreamMessage], None]) -> None:
        """Remove a listener for a specific channel."""
        if channel in self.listeners:
            self.listeners[channel].discard(callback)
    
    def _notify_listeners(self, message: StreamMessage) -> None:
        """Notify listeners of a message."""
        # Notify channel-specific listeners
        for callback in self.listeners.get(message.channel, set()):
            try:
                callback(message)
            except Exception as e:
                logger.error(f"Error in listener callback: {e}")
        
        # Notify global listeners
        for callback in self.listeners.get('*', set()):
            try:
                callback(message)
            except Exception as e:
                logger.error(f"Error in global listener callback: {e}")
    
    async def listen(self) -> AsyncGenerator[StreamMessage, None]:
        """Listen for messages on the stream."""
        while True:
            message = await self.queue.get()
            yield message
            self.queue.task_done()

# Dictionary to store message streams
message_streams: Dict[str, MessageStream] = {}