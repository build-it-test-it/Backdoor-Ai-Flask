"""
Database models for the Model Context Protocol (MCP) in Backdoor AI.

This module defines the database models used for storing context items,
agent data, tool usage information, and task records.
"""

import json
import uuid
from datetime import datetime
from enum import Enum
from typing import Dict, List, Any, Optional, Union
from sqlalchemy.ext.mutable import MutableDict

from app.database import db

class AgentRole(str, Enum):
    """Role of an agent in the system."""
    DEFAULT = "default"
    SYSTEM = "system"
    ASSISTANT = "assistant"
    USER = "user"
    TOOL = "tool"
    ADMIN = "admin"

class AgentStatus(str, Enum):
    """Status of an agent in the system."""
    READY = "ready"
    BUSY = "busy"
    IDLE = "idle"
    ERROR = "error"
    OFFLINE = "offline"

class ContextItem(db.Model):
    """Model for storing context items in the MCP."""
    __tablename__ = 'context_items'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    item_type = db.Column(db.String(50), nullable=False, index=True)
    data = db.Column(MutableDict.as_mutable(db.JSON), nullable=False)
    priority = db.Column(db.Integer, default=0)
    ttl = db.Column(db.Integer, default=3600)  # Time to live in seconds
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    session_id = db.Column(db.String(36), nullable=True, index=True)
    is_expired = db.Column(db.Boolean, default=False, index=True)
    
    def __repr__(self):
        return f"<ContextItem id={self.id} type={self.item_type}>"

class Agent(db.Model):
    """Model for storing agent information."""
    __tablename__ = 'agents'
    
    id = db.Column(db.String(36), primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    role = db.Column(db.Enum(AgentRole), nullable=False)
    status = db.Column(db.Enum(AgentStatus), nullable=False, default=AgentStatus.READY)
    session_id = db.Column(db.String(36), nullable=True, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_active = db.Column(db.DateTime, default=datetime.utcnow)
    memory = db.Column(MutableDict.as_mutable(db.JSON), default=dict)
    tool_permissions = db.Column(MutableDict.as_mutable(db.JSON), default=dict)
    
    # Relationships
    tasks = db.relationship('Task', back_populates='agent', lazy='dynamic')
    tool_usages = db.relationship('ToolUsage', back_populates='agent', lazy='dynamic')
    
    def __repr__(self):
        return f"<Agent id={self.id} name={self.name} role={self.role}>"

class ToolResult(db.Model):
    """Model for storing tool execution results."""
    __tablename__ = 'tool_results'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    result_data = db.Column(MutableDict.as_mutable(db.JSON), nullable=False)
    output_text = db.Column(db.Text, nullable=True)
    exit_code = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationship
    tool_usage = db.relationship('ToolUsage', uselist=False, back_populates='result')
    
    def __repr__(self):
        return f"<ToolResult id={self.id}>"

class ToolUsage(db.Model):
    """Model for storing tool usage information."""
    __tablename__ = 'tool_usages'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tool_type = db.Column(db.String(50), nullable=False, index=True)
    params = db.Column(MutableDict.as_mutable(db.JSON), nullable=False)
    success = db.Column(db.Boolean, default=True)
    error_message = db.Column(db.Text, nullable=True)
    execution_time = db.Column(db.Float, nullable=True)  # in seconds
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    session_id = db.Column(db.String(36), nullable=True, index=True)
    agent_id = db.Column(db.String(36), db.ForeignKey('agents.id'), nullable=True)
    result_id = db.Column(db.String(36), db.ForeignKey('tool_results.id'), nullable=True)
    
    # Relationships
    agent = db.relationship('Agent', back_populates='tool_usages')
    result = db.relationship('ToolResult', back_populates='tool_usage')
    
    def __repr__(self):
        return f"<ToolUsage id={self.id} tool_type={self.tool_type}>"

class Task(db.Model):
    """Model for storing task information."""
    __tablename__ = 'tasks'
    
    id = db.Column(db.String(36), primary_key=True)
    description = db.Column(db.String(255), nullable=False)
    data = db.Column(MutableDict.as_mutable(db.JSON), default=dict)
    status = db.Column(db.String(50), default='pending')
    start_time = db.Column(db.DateTime, default=datetime.utcnow)
    end_time = db.Column(db.DateTime, nullable=True)
    result = db.Column(MutableDict.as_mutable(db.JSON), nullable=True)
    session_id = db.Column(db.String(36), nullable=True, index=True)
    agent_id = db.Column(db.String(36), db.ForeignKey('agents.id'), nullable=True)
    
    # Relationships
    agent = db.relationship('Agent', back_populates='tasks')
    
    def __repr__(self):
        return f"<Task id={self.id} status={self.status}>"
