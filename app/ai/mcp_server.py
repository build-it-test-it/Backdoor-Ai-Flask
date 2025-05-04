"""
Model Context Protocol (MCP) Server

This module provides a dedicated service for managing model context in a standardized way.
It handles the storage, retrieval, and processing of context for the AI model, enhancing
the quality of responses and improving performance.

The MCP server is designed to work with Render.com's deployment environment, using the
/tmp directory for storage while maintaining persistence where possible.
"""

import json
import os
import time
import uuid
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Union
from threading import Lock
from flask import current_app, session, request

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("mcp_server")

class ContextItem:
    """Base class for context items stored in the MCP server."""
    def __init__(self, item_type: str, data: Dict[str, Any], ttl: int = 3600):
        """
        Initialize a context item.
        
        Args:
            item_type: Type of context item (e.g., 'user_info', 'session', 'behavior')
            data: Actual context data
            ttl: Time to live in seconds (default 1 hour)
        """
        self.id = str(uuid.uuid4())
        self.item_type = item_type
        self.data = data
        self.created_at = datetime.now()
        self.updated_at = self.created_at
        self.ttl = ttl  # Time to live in seconds
        self.priority = self._calculate_priority()
    
    def _calculate_priority(self) -> float:
        """Calculate priority based on recency and type."""
        # Default priority calculation - override in subclasses
        # Range is 0.0-1.0 with higher being more important
        base_priority = {
            'user_info': 0.9,
            'session': 0.8,
            'behavior': 0.7,
            'interaction': 0.6,
            'github': 0.5,
            'environment': 0.4,
            'command': 0.3,
            'history': 0.8,
            'metadata': 0.2
        }.get(self.item_type, 0.1)
        
        # Adjust for recency - newer items get higher priority
        age_factor = max(0.0, 1.0 - (datetime.now() - self.created_at).total_seconds() / self.ttl)
        
        return min(1.0, base_priority * (0.7 + 0.3 * age_factor))
    
    def update(self, data: Dict[str, Any]) -> None:
        """Update the item's data and timestamp."""
        self.data = data
        self.updated_at = datetime.now()
        self.priority = self._calculate_priority()
    
    def is_expired(self) -> bool:
        """Check if the item has expired based on TTL."""
        return (datetime.now() - self.updated_at).total_seconds() > self.ttl
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            'id': self.id,
            'item_type': self.item_type,
            'data': self.data,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'ttl': self.ttl,
            'priority': self.priority
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ContextItem':
        """Create a ContextItem from a dictionary."""
        item = cls(
            item_type=data['item_type'],
            data=data['data'],
            ttl=data.get('ttl', 3600)
        )
        item.id = data['id']
        item.created_at = datetime.fromisoformat(data['created_at'])
        item.updated_at = datetime.fromisoformat(data['updated_at'])
        item.priority = data.get('priority', item._calculate_priority())
        return item

class MCPServer:
    """
    Model Context Protocol Server for managing AI context.
    
    This class provides methods for storing, retrieving, and managing context
    for AI models, improving the quality of responses and enabling
    more sophisticated interactions.
    
    This version uses a PostgreSQL database for persistent storage.
    """
    
    def __init__(self):
        """Initialize the MCP server."""
        self.lock = Lock()  # For thread safety
        self.initialized = False
        
        # Load configuration from environment
        self.log_level = os.environ.get('MCP_LOG_LEVEL', 'INFO')
        self.enabled = os.environ.get('MCP_ENABLED', 'true').lower() == 'true'
        
        # Set log level
        logger.setLevel(getattr(logging, self.log_level))
        
        if not self.enabled:
            logger.warning("MCP server is disabled by configuration")
            return
        
        # Database models will be imported when needed to avoid circular imports
        # The models are registered with SQLAlchemy in app/__init__.py
        
        self.initialized = True
        logger.info("MCP Server initialized with PostgreSQL storage")
    
    def add_context_item(self, item_type: str, data: Dict[str, Any], 
                         ttl: int = 3600, session_id: Optional[str] = None, 
                         agent_id: Optional[str] = None) -> str:
        """
        Add a context item to the server.
        
        Args:
            item_type: Type of context item
            data: Context data to store
            ttl: Time to live in seconds
            session_id: Optional session ID (if None, adds to current session)
            agent_id: Optional agent ID to associate with this context
            
        Returns:
            The ID of the created context item
        """
        if not self.initialized or not self.enabled:
            logger.warning("MCP server is not initialized or disabled")
            return ""
        
        try:
            # Import here to avoid circular imports
            from app.ai.mcp_models import ContextItem as DbContextItem
            from app.database import db
            
            # Determine if this is session-specific or global context
            if session_id is None:
                session_id = session.get('session_id')
            
            # Create the context item in the database
            db_item = DbContextItem(
                item_type=item_type,
                session_id=session_id,
                agent_id=agent_id,
                ttl=ttl,
                data=data,
                is_expired=False
            )
            
            # Calculate priority
            db_item.calculate_priority()
            
            # Save to database
            db.session.add(db_item)
            db.session.commit()
            
            logger.debug(f"Added context item: {item_type}, id={db_item.id}, session={session_id}")
            
            # Add context ID to the data for reference
            data['_context_id'] = db_item.id
            
            return db_item.id
            
        except Exception as e:
            logger.error(f"Error adding context item: {str(e)}")
            return ""
    
    def update_context_item(self, item_id: str, data: Dict[str, Any], 
                           session_id: Optional[str] = None) -> bool:
        """
        Update an existing context item.
        
        Args:
            item_id: ID of the item to update
            data: New data to store
            session_id: Optional session ID (if None, uses current session)
            
        Returns:
            True if successful, False otherwise
        """
        if not self.initialized or not self.enabled:
            logger.warning("MCP server is not initialized or disabled")
            return False
        
        try:
            # Import here to avoid circular imports
            from app.ai.mcp_models import ContextItem as DbContextItem
            from app.database import db
            
            # If session_id not provided, get it from the current session
            if session_id is None:
                session_id = session.get('session_id')
            
            # Query to find the context item
            query = db.session.query(DbContextItem).filter(DbContextItem.id == item_id)
            
            # Add session filter if provided
            if session_id:
                query = query.filter(
                    (DbContextItem.session_id == session_id) | 
                    (DbContextItem.session_id == None)
                )
            
            # Get the context item
            db_item = query.first()
            
            if db_item:
                # Update the data
                db_item.data = data
                db_item.updated_at = datetime.now()
                
                # Recalculate priority
                db_item.calculate_priority()
                
                # Save to database
                db.session.add(db_item)
                db.session.commit()
                
                logger.debug(f"Updated context item: id={item_id}")
                return True
            else:
                logger.warning(f"Context item not found: id={item_id}")
                return False
                
        except Exception as e:
            logger.error(f"Error updating context item: {str(e)}")
            return False
    
    def get_context_item(self, item_id: str, session_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Retrieve a specific context item by ID.
        
        Args:
            item_id: ID of the item to retrieve
            session_id: Optional session ID (if None, uses current session)
            
        Returns:
            The context item data, or None if not found
        """
        if not self.initialized or not self.enabled:
            logger.warning("MCP server is not initialized or disabled")
            return None
        
        try:
            # Import here to avoid circular imports
            from app.ai.mcp_models import ContextItem as DbContextItem
            from app.database import db
            
            # If session_id not provided, get it from the current session
            if session_id is None:
                session_id = session.get('session_id')
            
            # Query to find the context item
            query = db.session.query(DbContextItem).filter(DbContextItem.id == item_id)
            
            # Add session filter if provided
            if session_id:
                query = query.filter(
                    (DbContextItem.session_id == session_id) | 
                    (DbContextItem.session_id == None)
                )
            
            # Get the context item
            db_item = query.first()
            
            if db_item:
                # Check if it's expired
                if db_item.check_expiry():
                    # It's expired, but we'll still return it this time
                    logger.debug(f"Retrieved expired context item: id={item_id}")
                else:
                    logger.debug(f"Retrieved context item: id={item_id}")
                
                return db_item.data
            else:
                logger.debug(f"Context item not found: id={item_id}")
                return None
                
        except Exception as e:
            logger.error(f"Error getting context item: {str(e)}")
            return None
    
    def get_context_by_type(self, item_type: str, session_id: Optional[str] = None, 
                           max_items: int = 10) -> List[Dict[str, Any]]:
        """
        Retrieve context items by type.
        
        Args:
            item_type: Type of context to retrieve
            session_id: Optional session ID (if None, uses current session)
            max_items: Maximum number of items to return
            
        Returns:
            List of context item data matching the type
        """
        if not self.initialized or not self.enabled:
            logger.warning("MCP server is not initialized or disabled")
            return []
        
        try:
            # Import here to avoid circular imports
            from app.ai.mcp_models import ContextItem as DbContextItem
            from app.database import db
            from sqlalchemy import or_
            
            # If session_id not provided, get it from the current session
            if session_id is None:
                session_id = session.get('session_id')
            
            # Query to find the context items
            query = db.session.query(DbContextItem).filter(
                DbContextItem.item_type == item_type,
                DbContextItem.is_expired == False
            )
            
            # Add session filter if provided
            if session_id:
                query = query.filter(
                    or_(
                        DbContextItem.session_id == session_id,
                        DbContextItem.session_id == None
                    )
                )
            
            # Order by priority (descending) and limit to max_items
            query = query.order_by(DbContextItem.priority.desc()).limit(max_items)
            
            # Get the context items
            db_items = query.all()
            
            # Extract the data
            items = [item.data for item in db_items]
            
            logger.debug(f"Retrieved {len(items)} context items of type {item_type}")
            return items
                
        except Exception as e:
            logger.error(f"Error getting context by type: {str(e)}")
            return []
    
    def get_full_context(self, session_id: Optional[str] = None, token_limit: int = 4000) -> Dict[str, Any]:
        """
        Get the full context for AI model processing.
        
        This method assembles context from various sources, prioritizing based on
        relevance, recency, and available token budget.
        
        Args:
            session_id: Optional session ID (if None, uses current session)
            token_limit: Approximate token limit for context
            
        Returns:
            Complete context dictionary organized by context type
        """
        if not self.initialized or not self.enabled:
            logger.warning("MCP server is not initialized or disabled")
            return {"timestamp": datetime.now().isoformat(), "context": {}}
        
        try:
            # Import here to avoid circular imports
            from app.ai.mcp_models import ContextItem as DbContextItem
            from app.database import db
            from sqlalchemy import or_, func
            
            # If session_id not provided, get it from the current session
            if session_id is None:
                session_id = session.get('session_id')
            
            # Collect all non-expired items organized by type
            context_by_type = {}
            
            # Rough estimation: ~4 chars per token (this is approximate)
            char_limit = token_limit * 4
            char_count = 0
            
            # First, get a count of items per type for planning
            type_counts = db.session.query(
                DbContextItem.item_type, 
                func.count(DbContextItem.id)
            ).filter(
                DbContextItem.is_expired == False
            )
            
            if session_id:
                type_counts = type_counts.filter(
                    or_(
                        DbContextItem.session_id == session_id,
                        DbContextItem.session_id == None
                    )
                )
            
            type_counts = dict(type_counts.group_by(DbContextItem.item_type).all())
            
            # Get items for each type, prioritized and limited
            for item_type, count in type_counts.items():
                # Determine how many items to fetch based on type
                # More important types get more items
                type_importance = {
                    'user_info': 1.0,      # Most important - user data
                    'agent': 1.0,          # Agent data
                    'interaction': 0.8,    # User-AI interactions
                    'behavior': 0.8,       # User behavior
                    'github': 0.7,         # GitHub repository data
                    'tool_usage': 0.6,     # Tool usage history
                    'tool_result': 0.6,    # Tool results
                    'task': 0.7,           # Task data
                    'environment': 0.4,    # Environment info
                    'request': 0.3,        # Current request
                    'metadata': 0.2        # Metadata (lowest priority)
                }.get(item_type, 0.5)
                
                # Calculate items to fetch based on importance
                fetch_limit = max(1, min(int(count), int(10 * type_importance)))
                
                # Query for this type
                query = db.session.query(DbContextItem).filter(
                    DbContextItem.item_type == item_type,
                    DbContextItem.is_expired == False
                )
                
                if session_id:
                    query = query.filter(
                        or_(
                            DbContextItem.session_id == session_id,
                            DbContextItem.session_id == None
                        )
                    )
                
                # Order by priority and limit
                items = query.order_by(DbContextItem.priority.desc()).limit(fetch_limit).all()
                
                # Add to context by type
                for item in items:
                    # Skip if we've hit our token budget
                    item_chars = len(json.dumps(item.data))
                    if char_count + item_chars > char_limit:
                        continue
                    
                    # Add to context by type
                    if item.item_type not in context_by_type:
                        context_by_type[item.item_type] = []
                    
                    context_by_type[item.item_type].append(item.data)
                    char_count += item_chars
            
            # Add current request context
            try:
                request_context = {
                    'path': request.path,
                    'method': request.method,
                    'user_agent': request.headers.get('User-Agent', 'Unknown'),
                    'timestamp': datetime.now().isoformat()
                }
                if 'request' not in context_by_type:
                    context_by_type['request'] = []
                context_by_type['request'].append(request_context)
            except RuntimeError:
                # No request context available (outside request context)
                pass
            
            # Organize into a clean structure
            full_context = {
                'timestamp': datetime.now().isoformat(),
                'session_id': session_id,
                'context': context_by_type,
                'char_count': char_count,
                'token_estimate': char_count // 4
            }
            
            logger.debug(f"Retrieved full context with {len(context_by_type)} types, ~{char_count//4} tokens")
            return full_context
                
        except Exception as e:
            logger.error(f"Error getting full context: {str(e)}")
            return {
                "timestamp": datetime.now().isoformat(),
                "session_id": session_id,
                "context": {},
                "error": str(e)
            }
    
    def cleanup_expired_items(self) -> int:
        """
        Mark expired items in the database based on their TTL.
        
        Returns:
            Number of items marked as expired
        """
        if not self.initialized or not self.enabled:
            logger.warning("MCP server is not initialized or disabled")
            return 0
        
        try:
            # Import here to avoid circular imports
            from app.ai.mcp_models import ContextItem as DbContextItem
            from app.database import db
            from sqlalchemy import func, text
            
            # Mark items as expired based on TTL
            with db.session.begin():
                # Find items where current timestamp - updated_at > ttl
                expired_query = db.session.query(DbContextItem).filter(
                    DbContextItem.is_expired == False,
                    func.extract('epoch', func.now() - DbContextItem.updated_at) > DbContextItem.ttl
                )
                
                # Count items to be marked as expired
                count = expired_query.count()
                
                # Mark them as expired
                if count > 0:
                    expired_query.update({DbContextItem.is_expired: True}, synchronize_session=False)
                    
                    logger.info(f"Marked {count} context items as expired")
                    return count
                else:
                    logger.debug("No expired context items found")
                    return 0
                    
        except Exception as e:
            logger.error(f"Error cleaning up expired items: {str(e)}")
            return 0
    
    def delete_expired_items(self, older_than_days: int = 30) -> int:
        """
        Permanently delete expired items that are older than the specified number of days.
        
        Args:
            older_than_days: Delete items older than this many days
            
        Returns:
            Number of items deleted
        """
        if not self.initialized or not self.enabled:
            logger.warning("MCP server is not initialized or disabled")
            return 0
        
        try:
            # Import here to avoid circular imports
            from app.ai.mcp_models import ContextItem as DbContextItem
            from app.database import db
            from sqlalchemy import func, text
            
            # Delete expired items older than the specified number of days
            with db.session.begin():
                # Find items where current timestamp - created_at > older_than_days
                delete_query = db.session.query(DbContextItem).filter(
                    DbContextItem.is_expired == True,
                    func.extract('epoch', func.now() - DbContextItem.created_at) > (older_than_days * 24 * 60 * 60)
                )
                
                # Count items to be deleted
                count = delete_query.count()
                
                # Delete them
                if count > 0:
                    delete_query.delete(synchronize_session=False)
                    
                    logger.info(f"Deleted {count} expired context items older than {older_than_days} days")
                    return count
                else:
                    logger.debug(f"No expired context items older than {older_than_days} days found")
                    return 0
                    
        except Exception as e:
            logger.error(f"Error deleting expired items: {str(e)}")
            return 0
    
    def get_database_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the database.
        
        Returns:
            Dictionary with database statistics
        """
        if not self.initialized or not self.enabled:
            logger.warning("MCP server is not initialized or disabled")
            return {"error": "MCP server is not initialized or disabled"}
        
        try:
            # Import here to avoid circular imports
            from app.ai.mcp_models import (
                ContextItem as DbContextItem,
                Agent as DbAgent, 
                ToolUsage as DbToolUsage,
                ToolResult as DbToolResult,
                Task as DbTask
            )
            from app.database import db
            from sqlalchemy import func, distinct
            
            stats = {}
            
            # Context item stats
            context_count = db.session.query(func.count(DbContextItem.id)).scalar() or 0
            context_type_count = db.session.query(
                func.count(distinct(DbContextItem.item_type))
            ).scalar() or 0
            context_expired_count = db.session.query(
                func.count(DbContextItem.id)
            ).filter(DbContextItem.is_expired == True).scalar() or 0
            
            stats["context_items"] = {
                "total": context_count,
                "types": context_type_count,
                "expired": context_expired_count,
                "active": context_count - context_expired_count
            }
            
            # Agent stats
            agent_count = db.session.query(func.count(DbAgent.id)).scalar() or 0
            agent_role_counts = {}
            for role in AgentRole:
                count = db.session.query(func.count(DbAgent.id)).filter(
                    DbAgent.role == role
                ).scalar() or 0
                agent_role_counts[role.value] = count
            
            stats["agents"] = {
                "total": agent_count,
                "by_role": agent_role_counts
            }
            
            # Tool usage stats
            tool_count = db.session.query(func.count(DbToolUsage.id)).scalar() or 0
            
            tools_by_type = {}
            tool_types = db.session.query(
                DbToolUsage.tool_type, 
                func.count(DbToolUsage.id)
            ).group_by(DbToolUsage.tool_type).all()
            
            for tool_type, count in tool_types:
                tools_by_type[tool_type] = count
            
            stats["tool_usage"] = {
                "total": tool_count,
                "by_type": tools_by_type
            }
            
            # Task stats
            task_count = db.session.query(func.count(DbTask.id)).scalar() or 0
            
            task_status_counts = {}
            task_statuses = db.session.query(
                DbTask.status, 
                func.count(DbTask.id)
            ).group_by(DbTask.status).all()
            
            for status, count in task_statuses:
                task_status_counts[status] = count
            
            stats["tasks"] = {
                "total": task_count,
                "by_status": task_status_counts
            }
            
            return stats
                
        except Exception as e:
            logger.error(f"Error getting database stats: {str(e)}")
            return {"error": str(e)}
    
    def record_user_behavior(self, action: str, screen: str, 
                           duration: int = 0, details: Dict[str, Any] = None) -> str:
        """
        Record user behavior as context.
        
        Args:
            action: The action the user performed
            screen: The screen where the action occurred
            duration: Time spent on the action in seconds
            details: Additional details about the action
            
        Returns:
            ID of the created context item
        """
        behavior_data = {
            'action': action,
            'screen': screen,
            'duration': duration,
            'details': details or {},
            'timestamp': datetime.now().isoformat()
        }
        
        # Add to context with 1-day TTL
        context_id = self.add_context_item('behavior', behavior_data, ttl=86400)
        logger.debug(f"Recorded user behavior: {action} on {screen}, id={context_id}")
        return context_id
    
    def record_interaction(self, user_message: str, ai_response: str, 
                         context: Dict[str, Any] = None) -> str:
        """
        Record an AI interaction as context.
        
        Args:
            user_message: The user's message
            ai_response: The AI's response
            context: Additional context for the interaction
            
        Returns:
            ID of the created context item
        """
        # Truncate very long messages to prevent DB bloat
        max_length = 10000  # Characters
        if len(user_message) > max_length:
            user_message = user_message[:max_length] + "... [truncated]"
        if len(ai_response) > max_length:
            ai_response = ai_response[:max_length] + "... [truncated]"
            
        interaction_data = {
            'user_message': user_message,
            'ai_response': ai_response,
            'context': context or {},
            'timestamp': datetime.now().isoformat()
        }
        
        # Add to context with 3-day TTL
        context_id = self.add_context_item('interaction', interaction_data, ttl=259200)
        logger.debug(f"Recorded AI interaction, id={context_id}")
        return context_id
    
    def store_github_info(self, repo_name: str, repo_info: Dict[str, Any]) -> str:
        """
        Store GitHub repository information as context.
        
        Args:
            repo_name: Name of the repository
            repo_info: Repository information
            
        Returns:
            ID of the created context item
        """
        github_data = {
            'repo_name': repo_name,
            'repo_info': repo_info,
            'timestamp': datetime.now().isoformat()
        }
        
        # Add to context with 7-day TTL
        context_id = self.add_context_item('github', github_data, ttl=604800)
        logger.debug(f"Stored GitHub info for repo {repo_name}, id={context_id}")
        return context_id
    
    def get_recent_activities(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get recent user activities across sessions.
        
        Args:
            limit: Maximum number of activities to return
            
        Returns:
            List of recent user activities
        """
        if not self.initialized or not self.enabled:
            logger.warning("MCP server is not initialized or disabled")
            return []
        
        try:
            # Import here to avoid circular imports
            from app.ai.mcp_models import ContextItem as DbContextItem
            from app.database import db
            
            # Get recent behavior items across all sessions
            query = db.session.query(DbContextItem).filter(
                DbContextItem.item_type == 'behavior',
                DbContextItem.is_expired == False
            ).order_by(DbContextItem.updated_at.desc()).limit(limit)
            
            # Get the items
            items = query.all()
            
            # Extract the data
            activities = [item.data for item in items]
            
            logger.debug(f"Retrieved {len(activities)} recent user activities")
            return activities
                
        except Exception as e:
            logger.error(f"Error getting recent activities: {str(e)}")
            return []
            
    def record_tool_usage(self, tool_type: str, params: Dict[str, Any], 
                        result: Dict[str, Any], session_id: Optional[str] = None,
                        agent_id: Optional[str] = None) -> str:
        """
        Record a tool usage in the MCP context.
        
        Args:
            tool_type: Type of tool that was used
            params: Parameters used for the tool
            result: Result of the tool execution
            session_id: Optional session ID (if None, uses current session)
            agent_id: Optional agent ID that executed the tool
            
        Returns:
            ID of the created context item
        """
        if not self.initialized or not self.enabled:
            logger.warning("MCP server is not initialized or disabled")
            return ""
            
        try:
            # Import here to avoid circular imports
            from app.ai.mcp_models import ToolUsage, ToolResult
            from app.database import db
            
            # If session_id not provided, get it from the current session
            if session_id is None:
                session_id = session.get('session_id')
                
            # Create a tool result record
            tool_result = ToolResult(
                result_data=result,
                output_text=result.get('output', ''),
                exit_code=result.get('exit_code')
            )
            
            # Save the tool result
            db.session.add(tool_result)
            db.session.flush()  # Get the ID without committing
            
            # Create a tool usage record
            tool_usage = ToolUsage(
                tool_type=tool_type,
                params=params,
                success=result.get('success', True),
                error_message=result.get('error', None),
                execution_time=result.get('execution_time', None),
                session_id=session_id,
                agent_id=agent_id,
                result_id=tool_result.id
            )
            
            # Save the tool usage
            db.session.add(tool_usage)
            db.session.commit()
            
            logger.debug(f"Recorded tool usage: {tool_type}, id={tool_usage.id}")
            return tool_usage.id
                
        except Exception as e:
            logger.error(f"Error recording tool usage: {str(e)}")
            return ""

# Singleton instance
mcp_server = MCPServer()
