"""
Token usage tracking model for SQLAlchemy.

This module provides the TokenUsage model for tracking token usage statistics
in the application, enabling performance monitoring and cost tracking.
"""

from sqlalchemy import Column, Integer, String, Float, DateTime, Text, func
from sqlalchemy.ext.mutable import MutableDict
from datetime import datetime
import uuid

from app.database import db

class TokenUsage(db.Model):
    """Model for tracking token usage statistics."""
    __tablename__ = 'token_usage'
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String(36), nullable=True, index=True)
    user_id = Column(String(36), nullable=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    
    # Token usage data
    model = Column(String(100), nullable=False, index=True)
    provider = Column(String(50), nullable=False, index=True)
    prompt_tokens = Column(Integer, default=0)
    completion_tokens = Column(Integer, default=0)
    response_time = Column(Float, nullable=True)  # in seconds
    
    # Request metadata
    request_type = Column(String(50), nullable=True)  # e.g., 'chat', 'completion', etc.
    endpoint = Column(String(255), nullable=True)
    
    # Cost tracking (if enabled)
    cost = Column(Float, nullable=True)
    cost_per_token = Column(Float, nullable=True)
    
    # Request/response data (optional)
    request_data = Column(Text, nullable=True)
    response_data = Column(Text, nullable=True)
    
    @property
    def total_tokens(self):
        """Get the total number of tokens used."""
        return (self.prompt_tokens or 0) + (self.completion_tokens or 0)
    
    @classmethod
    def get_total_usage(cls, session_id=None, user_id=None, days=None):
        """
        Get total token usage statistics.
        
        Args:
            session_id: Optional session ID to filter by
            user_id: Optional user ID to filter by
            days: Optional number of days to limit the query to
            
        Returns:
            Dictionary with total token usage statistics
        """
        query = db.session.query(
            func.sum(cls.prompt_tokens).label('total_prompt'),
            func.sum(cls.completion_tokens).label('total_completion'),
            func.avg(cls.response_time).label('avg_response_time')
        )
        
        # Apply filters
        if session_id:
            query = query.filter(cls.session_id == session_id)
        
        if user_id:
            query = query.filter(cls.user_id == user_id)
        
        if days:
            date_limit = datetime.utcnow() - datetime.timedelta(days=days)
            query = query.filter(cls.timestamp >= date_limit)
        
        # Execute query
        result = query.first()
        
        # Prepare response
        if result:
            return {
                'prompt_tokens': result.total_prompt or 0,
                'completion_tokens': result.total_completion or 0,
                'total_tokens': (result.total_prompt or 0) + (result.total_completion or 0),
                'avg_response_time': result.avg_response_time or 0
            }
        else:
            return {
                'prompt_tokens': 0,
                'completion_tokens': 0,
                'total_tokens': 0,
                'avg_response_time': 0
            }
    
    @classmethod
    def get_daily_usage(cls, days=7, session_id=None, user_id=None):
        """
        Get daily token usage statistics.
        
        Args:
            days: Number of days to include
            session_id: Optional session ID to filter by
            user_id: Optional user ID to filter by
            
        Returns:
            List of dictionaries with daily token usage statistics
        """
        # Create query with date trunc
        query = db.session.query(
            func.date_trunc('day', cls.timestamp).label('date'),
            func.sum(cls.prompt_tokens).label('prompt_tokens'),
            func.sum(cls.completion_tokens).label('completion_tokens'),
            func.avg(cls.response_time).label('avg_response_time')
        ).group_by(func.date_trunc('day', cls.timestamp)).order_by(func.date_trunc('day', cls.timestamp))
        
        # Apply filters
        if session_id:
            query = query.filter(cls.session_id == session_id)
        
        if user_id:
            query = query.filter(cls.user_id == user_id)
        
        # Apply date filter
        if days:
            date_limit = datetime.utcnow() - datetime.timedelta(days=days)
            query = query.filter(cls.timestamp >= date_limit)
        
        # Execute query
        results = query.all()
        
        # Convert to list of dictionaries
        return [
            {
                'date': result.date.strftime('%Y-%m-%d'),
                'prompt_tokens': result.prompt_tokens or 0,
                'completion_tokens': result.completion_tokens or 0,
                'total_tokens': (result.prompt_tokens or 0) + (result.completion_tokens or 0),
                'avg_response_time': result.avg_response_time or 0
            }
            for result in results
        ]
    
    @classmethod
    def get_model_usage(cls, limit=5, session_id=None, user_id=None, days=None):
        """
        Get token usage statistics by model.
        
        Args:
            limit: Maximum number of models to include
            session_id: Optional session ID to filter by
            user_id: Optional user ID to filter by
            days: Optional number of days to limit the query to
            
        Returns:
            List of dictionaries with model usage statistics
        """
        query = db.session.query(
            cls.model,
            cls.provider,
            func.count(cls.id).label('usage_count'),
            func.sum(cls.prompt_tokens).label('prompt_tokens'),
            func.sum(cls.completion_tokens).label('completion_tokens')
        ).group_by(cls.model, cls.provider).order_by(
            (func.sum(cls.prompt_tokens) + func.sum(cls.completion_tokens)).desc()
        )
        
        # Apply filters
        if session_id:
            query = query.filter(cls.session_id == session_id)
        
        if user_id:
            query = query.filter(cls.user_id == user_id)
        
        if days:
            date_limit = datetime.utcnow() - datetime.timedelta(days=days)
            query = query.filter(cls.timestamp >= date_limit)
        
        # Apply limit
        if limit:
            query = query.limit(limit)
        
        # Execute query
        results = query.all()
        
        # Convert to list of dictionaries
        return [
            {
                'model': result.model,
                'provider': result.provider,
                'usage_count': result.usage_count,
                'prompt_tokens': result.prompt_tokens or 0,
                'completion_tokens': result.completion_tokens or 0,
                'total_tokens': (result.prompt_tokens or 0) + (result.completion_tokens or 0)
            }
            for result in results
        ]
    
    @classmethod
    def get_recent_usage(cls, limit=10, session_id=None, user_id=None):
        """
        Get recent token usage records.
        
        Args:
            limit: Maximum number of records to include
            session_id: Optional session ID to filter by
            user_id: Optional user ID to filter by
            
        Returns:
            List of dictionaries with recent token usage records
        """
        query = db.session.query(cls).order_by(cls.timestamp.desc())
        
        # Apply filters
        if session_id:
            query = query.filter(cls.session_id == session_id)
        
        if user_id:
            query = query.filter(cls.user_id == user_id)
        
        # Apply limit
        if limit:
            query = query.limit(limit)
        
        # Execute query
        results = query.all()
        
        # Convert to list of dictionaries
        return [
            {
                'timestamp': result.timestamp.isoformat(),
                'model': result.model,
                'provider': result.provider,
                'prompt_tokens': result.prompt_tokens or 0,
                'completion_tokens': result.completion_tokens or 0,
                'total_tokens': (result.prompt_tokens or 0) + (result.completion_tokens or 0),
                'response_time': result.response_time or 0
            }
            for result in results
        ]
