"""
MCP Agent System

This module provides agent creation and management capabilities for the Model Context Protocol (MCP) server.
Agents are AI-powered entities that can use tools and perform tasks autonomously or under guidance.

Each agent has access to tools like VS Code, Python, bash, and other utilities, allowing them
to interact with code, execute commands, and perform complex operations based on user requests.
"""

import json
import os
import uuid
import logging
import time
import threading
from typing import Dict, List, Any, Optional, Union, Callable
from datetime import datetime
from enum import Enum

# Import tool-related modules
from app.ai.tools import tool_registry, ToolType, BaseTool
from app.ai.behavior_tracker import behavior_tracker
from app.ai.mcp_server import mcp_server

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("mcp_agents")

class AgentStatus(str, Enum):
    """Status values for an agent."""
    INITIALIZING = "initializing"
    READY = "ready"
    BUSY = "busy"
    ERROR = "error"
    TERMINATED = "terminated"

class AgentRole(str, Enum):
    """Roles that an agent can have."""
    ASSISTANT = "assistant"     # General purpose AI assistant
    DEVELOPER = "developer"     # Code-focused developer agent
    ANALYST = "analyst"         # Data analysis specialist
    EXECUTOR = "executor"       # Command execution specialist
    BROWSER = "browser"         # Web browsing specialist
    CUSTOM = "custom"           # Custom role with specific capabilities

class Agent:
    """
    An AI agent that can use tools and perform tasks.
    
    Agents are context-aware entities that can execute tools, maintain state,
    and communicate with the AI model to complete user requests.
    """
    
    def __init__(self, agent_id: str = None, name: str = None, role: AgentRole = AgentRole.ASSISTANT, 
                session_id: str = None, tool_permissions: List[str] = None):
        """
        Initialize an agent.
        
        Args:
            agent_id: Unique identifier for the agent (auto-generated if None)
            name: Display name for the agent
            role: Role that defines the agent's capabilities
            session_id: Session ID this agent belongs to
            tool_permissions: List of tool types this agent can use
        """
        self.id = agent_id or str(uuid.uuid4())
        self.name = name or f"Agent-{self.id[:8]}"
        self.role = role
        self.session_id = session_id
        self.status = AgentStatus.INITIALIZING
        self.created_at = datetime.now()
        self.last_active = self.created_at
        self.task_history = []
        self.memory = {}  # Agent's working memory
        self.active_task = None
        self.results_queue = []
        
        # Set up tool permissions (default all tools if None)
        self.tool_permissions = tool_permissions or [t.value for t in ToolType]
        
        # Initialize the agent's context in the MCP server
        self._initialize_agent_context()
        
        # Set status to ready
        self.status = AgentStatus.READY
        logger.info(f"Agent {self.name} ({self.id}) initialized with role {self.role}")
    
    def _initialize_agent_context(self):
        """Initialize the agent's context in the MCP server and database."""
        # Create database entry for this agent
        try:
            from app.ai.mcp_models import Agent as DbAgent, AgentRole, AgentStatus
            from app.database import db, get_or_create
            
            # Create or get agent record
            agent_db, created = get_or_create(
                DbAgent,
                id=self.id,
                defaults={
                    'name': self.name,
                    'role': AgentRole(self.role),
                    'session_id': self.session_id,
                    'status': AgentStatus(self.status),
                    'memory': self.memory,
                    'tool_permissions': self.tool_permissions,
                    'last_active': self.last_active
                }
            )
            
            if not created:
                # Update existing agent
                agent_db.name = self.name
                agent_db.role = AgentRole(self.role)
                agent_db.session_id = self.session_id
                agent_db.status = AgentStatus(self.status)
                agent_db.memory = self.memory
                agent_db.tool_permissions = self.tool_permissions
                agent_db.last_active = self.last_active
                db.session.add(agent_db)
                db.session.commit()
                
            logger.debug(f"{'Created' if created else 'Updated'} agent in database: {self.name} ({self.id})")
            
            # Also store in MCP context for quick access
            agent_data = {
                'id': self.id,
                'name': self.name,
                'role': self.role,
                'status': self.status,
                'created_at': self.created_at.isoformat(),
                'tool_permissions': self.tool_permissions
            }
            
            # Store in MCP server
            mcp_server.add_context_item(
                item_type='agent',
                data=agent_data,
                ttl=86400,  # 24 hours
                session_id=self.session_id
            )
        except Exception as e:
            logger.error(f"Error initializing agent in database: {str(e)}")
    
    def update_status(self, status: AgentStatus):
        """Update the agent's status."""
        self.status = status
        self.last_active = datetime.now()
        
        # Update in database
        try:
            from app.ai.mcp_models import Agent as DbAgent, AgentStatus as DbAgentStatus
            from app.database import db
            
            # Find agent in database
            agent_db = db.session.query(DbAgent).filter(DbAgent.id == self.id).first()
            if agent_db:
                # Update status and last_active
                agent_db.status = DbAgentStatus(status)
                agent_db.last_active = self.last_active
                db.session.add(agent_db)
                db.session.commit()
                logger.debug(f"Updated agent status in database: {self.name} ({self.id}) -> {status}")
            
            # Also update in MCP context for quick access
            # Get current agent context
            agent_contexts = mcp_server.get_context_by_type(
                item_type='agent',
                session_id=self.session_id
            )
            
            for agent_context in agent_contexts:
                if agent_context.get('id') == self.id:
                    # Update status
                    agent_context['status'] = status
                    agent_context['last_active'] = self.last_active.isoformat()
                    
                    # Update in MCP server
                    mcp_server.update_context_item(
                        item_id=agent_context.get('_context_id', ''),  # Internal ID from MCP
                        data=agent_context,
                        session_id=self.session_id
                    )
                    break
        except Exception as e:
            logger.error(f"Error updating agent status: {str(e)}")
    
    def execute_tool(self, tool_type: str, **kwargs) -> Dict[str, Any]:
        """
        Execute a tool with the given parameters.
        
        Args:
            tool_type: Type of tool to execute
            **kwargs: Parameters for the tool
            
        Returns:
            Result of the tool execution
        """
        # Check if agent has permission to use this tool
        if tool_type not in self.tool_permissions:
            error_msg = f"Agent {self.name} does not have permission to use tool {tool_type}"
            logger.error(error_msg)
            return {
                "success": False,
                "error": error_msg
            }
        
        # Update status
        self.update_status(AgentStatus.BUSY)
        
        # Execute the tool
        start_time = time.time()
        try:
            # First record the intent to use this tool
            from app.ai.mcp_models import ToolUsage
            from app.database import db
            
            # Execute the tool
            result = tool_registry.execute_tool(tool_type, **kwargs)
            execution_time = time.time() - start_time
            
            # Set success flag if not present
            if 'success' not in result:
                result['success'] = True
            
            # Record in database through MCP server
            try:
                mcp_server.record_tool_usage(
                    tool_type=tool_type,
                    params=kwargs,
                    result=result,
                    session_id=self.session_id,
                    agent_id=self.id
                )
            except Exception as e:
                logger.error(f"Error recording tool usage in database: {str(e)}")
            
            # Add execution time to the result
            result['execution_time'] = execution_time
            
            # Store in agent's local history
            self._store_tool_result(tool_type, kwargs, result)
            
            # Update status
            self.update_status(AgentStatus.READY)
            
            return result
        except Exception as e:
            error_details = traceback.format_exc()
            error_msg = f"Error executing tool {tool_type}: {str(e)}"
            logger.error(error_msg)
            
            # Update status
            self.update_status(AgentStatus.ERROR)
            
            error_result = {
                "success": False,
                "error": error_msg,
                "details": error_details,
                "execution_time": time.time() - start_time
            }
            
            # Record failed execution in database
            try:
                mcp_server.record_tool_usage(
                    tool_type=tool_type,
                    params=kwargs,
                    result=error_result,
                    session_id=self.session_id,
                    agent_id=self.id
                )
            except Exception as ex:
                logger.error(f"Error recording failed tool usage: {str(ex)}")
            
            # Store in agent's local history
            self._store_tool_result(tool_type, kwargs, error_result)
            
            return error_result
    
    def _record_tool_usage(self, tool_type: str, params: Dict[str, Any]):
        """Record the intent to use a tool in the agent's history."""
        usage = {
            'tool_type': tool_type,
            'params': params,
            'timestamp': datetime.now().isoformat()
        }
        
        self.task_history.append(usage)
        
        # Also record in MCP server
        try:
            mcp_server.add_context_item(
                item_type='tool_usage',
                data={
                    'agent_id': self.id,
                    'agent_name': self.name,
                    'tool_type': tool_type,
                    'params': params,
                    'timestamp': datetime.now().isoformat()
                },
                ttl=86400,  # 24 hours
                session_id=self.session_id
            )
        except Exception as e:
            logger.error(f"Error recording tool usage in MCP: {str(e)}")
    
    def _store_tool_result(self, tool_type: str, params: Dict[str, Any], result: Dict[str, Any]):
        """Store the result of a tool execution in the agent's history."""
        tool_result = {
            'tool_type': tool_type,
            'params': params,
            'result': result,
            'timestamp': datetime.now().isoformat()
        }
        
        # Add to results queue
        self.results_queue.append(tool_result)
        
        # Also record in MCP server
        try:
            mcp_server.add_context_item(
                item_type='tool_result',
                data={
                    'agent_id': self.id,
                    'agent_name': self.name,
                    'tool_type': tool_type,
                    'params': params,
                    'result': result,
                    'timestamp': datetime.now().isoformat()
                },
                ttl=86400,  # 24 hours
                session_id=self.session_id
            )
        except Exception as e:
            logger.error(f"Error storing tool result in MCP: {str(e)}")
    
    def get_next_result(self) -> Optional[Dict[str, Any]]:
        """Get the next result from the queue, or None if queue is empty."""
        if self.results_queue:
            return self.results_queue.pop(0)
        return None
    
    def execute_task(self, task_description: str, task_data: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Execute a complex task that might involve multiple tool usages.
        
        Args:
            task_description: Description of the task to execute
            task_data: Additional data for the task
            
        Returns:
            Result of the task execution
        """
        # Update status
        self.update_status(AgentStatus.BUSY)
        
        # Generate task ID
        task_id = str(uuid.uuid4())
        start_time = datetime.now()
        
        # Record task in database
        try:
            from app.ai.mcp_models import Task as DbTask
            from app.database import db
            
            # Create task record
            task_db = DbTask(
                id=task_id,
                description=task_description,
                data=task_data or {},
                status='in_progress',
                start_time=start_time,
                agent_id=self.id,
                session_id=self.session_id
            )
            
            db.session.add(task_db)
            db.session.commit()
            logger.debug(f"Created task in database: {task_id}")
        except Exception as e:
            logger.error(f"Error recording task in database: {str(e)}")
        
        # Store in agent's memory
        task = {
            'id': task_id,
            'description': task_description,
            'data': task_data or {},
            'start_time': start_time.isoformat(),
            'status': 'in_progress'
        }
        
        self.active_task = task
        
        # Also record in MCP context for quick access
        try:
            mcp_server.add_context_item(
                item_type='task',
                data={
                    'agent_id': self.id,
                    'agent_name': self.name,
                    'task_id': task_id,
                    'description': task_description,
                    'data': task_data or {},
                    'status': 'in_progress',
                    'timestamp': start_time.isoformat()
                },
                ttl=86400,  # 24 hours
                session_id=self.session_id
            )
        except Exception as e:
            logger.error(f"Error recording task in MCP context: {str(e)}")
        
        # Placeholder for task execution logic
        # In a real implementation, this would involve breaking down the task,
        # planning tool usage, and executing tools in sequence
        
        # For now, return a simple response
        end_time = datetime.now()
        result = {
            'task_id': task_id,
            'status': 'completed',
            'message': f"Task '{task_description}' executed by agent {self.name}",
            'timestamp': end_time.isoformat(),
            'execution_time': (end_time - start_time).total_seconds()
        }
        
        # Update task in database
        try:
            from app.ai.mcp_models import Task as DbTask
            from app.database import db
            
            # Find task in database
            task_db = db.session.query(DbTask).filter(DbTask.id == task_id).first()
            if task_db:
                # Update task
                task_db.status = 'completed'
                task_db.end_time = end_time
                task_db.result = result
                db.session.add(task_db)
                db.session.commit()
                logger.debug(f"Updated task in database: {task_id} -> completed")
        except Exception as e:
            logger.error(f"Error updating task in database: {str(e)}")
        
        # Update task in agent's memory
        task['status'] = 'completed'
        task['end_time'] = end_time.isoformat()
        task['result'] = result
        
        # Also update in MCP context
        try:
            # Get current task context
            task_contexts = mcp_server.get_context_by_type(
                item_type='task',
                session_id=self.session_id
            )
            
            for task_context in task_contexts:
                if task_context.get('task_id') == task_id:
                    # Update status
                    task_context['status'] = 'completed'
                    task_context['result'] = result
                    task_context['end_time'] = end_time.isoformat()
                    
                    # Update in MCP server
                    mcp_server.update_context_item(
                        item_id=task_context.get('_context_id', ''),
                        data=task_context,
                        session_id=self.session_id
                    )
                    break
        except Exception as e:
            logger.error(f"Error updating task in MCP context: {str(e)}")
        
        # Reset active task
        self.active_task = None
        
        # Update status
        self.update_status(AgentStatus.READY)
        
        return result
    
    def get_context(self) -> Dict[str, Any]:
        """Get the agent's context information."""
        return {
            'id': self.id,
            'name': self.name,
            'role': self.role,
            'status': self.status,
            'created_at': self.created_at.isoformat(),
            'last_active': self.last_active.isoformat(),
            'task_history': self.task_history,
            'memory': self.memory,
            'active_task': self.active_task,
            'tool_permissions': self.tool_permissions
        }

class AgentManager:
    """
    Manages the creation, tracking, and coordination of agents.
    
    The AgentManager is responsible for creating agents, assigning them tasks,
    and coordinating their activities to complete user requests.
    """
    
    def __init__(self):
        """Initialize the agent manager."""
        self.agents: Dict[str, Agent] = {}  # agent_id -> Agent
        self.session_agents: Dict[str, List[str]] = {}  # session_id -> [agent_id]
        self.default_agents: Dict[str, str] = {}  # session_id -> default_agent_id
    
    def create_agent(self, name: str = None, role: AgentRole = AgentRole.ASSISTANT, 
                   session_id: str = None, tool_permissions: List[str] = None) -> Agent:
        """
        Create a new agent.
        
        Args:
            name: Display name for the agent
            role: Role that defines the agent's capabilities
            session_id: Session ID this agent belongs to
            tool_permissions: List of tool types this agent can use
            
        Returns:
            The created agent
        """
        # Create the agent
        agent = Agent(
            name=name,
            role=role,
            session_id=session_id,
            tool_permissions=tool_permissions
        )
        
        # Register the agent
        self.agents[agent.id] = agent
        
        # Add to session agents
        if session_id:
            if session_id not in self.session_agents:
                self.session_agents[session_id] = []
            self.session_agents[session_id].append(agent.id)
            
            # Set as default agent for session if it's the first one
            if session_id not in self.default_agents:
                self.default_agents[session_id] = agent.id
        
        logger.info(f"Created agent {agent.name} ({agent.id}) with role {agent.role}")
        return agent
    
    def get_agent(self, agent_id: str) -> Optional[Agent]:
        """Get an agent by ID."""
        return self.agents.get(agent_id)
    
    def get_agents_for_session(self, session_id: str) -> List[Agent]:
        """Get all agents for a session."""
        agent_ids = self.session_agents.get(session_id, [])
        return [self.agents.get(agent_id) for agent_id in agent_ids if agent_id in self.agents]
    
    def get_default_agent(self, session_id: str) -> Optional[Agent]:
        """Get the default agent for a session."""
        agent_id = self.default_agents.get(session_id)
        if agent_id:
            return self.agents.get(agent_id)
        return None
    
    def set_default_agent(self, session_id: str, agent_id: str) -> bool:
        """Set the default agent for a session."""
        if agent_id in self.agents and (session_id in self.session_agents and agent_id in self.session_agents[session_id]):
            self.default_agents[session_id] = agent_id
            return True
        return False
    
    def terminate_agent(self, agent_id: str) -> bool:
        """Terminate an agent."""
        if agent_id in self.agents:
            agent = self.agents[agent_id]
            agent.update_status(AgentStatus.TERMINATED)
            
            # Remove from session_agents
            if agent.session_id and agent.session_id in self.session_agents:
                if agent_id in self.session_agents[agent.session_id]:
                    self.session_agents[agent.session_id].remove(agent_id)
                
                # If this was the default agent, set a new one if available
                if agent.session_id in self.default_agents and self.default_agents[agent.session_id] == agent_id:
                    if self.session_agents[agent.session_id]:
                        self.default_agents[agent.session_id] = self.session_agents[agent.session_id][0]
                    else:
                        del self.default_agents[agent.session_id]
            
            # Remove from agents
            del self.agents[agent_id]
            
            logger.info(f"Terminated agent {agent.name} ({agent_id})")
            return True
        
        return False
    
    def execute_tool_with_agent(self, agent_id: str, tool_type: str, **kwargs) -> Dict[str, Any]:
        """
        Execute a tool with a specific agent.
        
        Args:
            agent_id: ID of the agent to use
            tool_type: Type of tool to execute
            **kwargs: Parameters for the tool
            
        Returns:
            Result of the tool execution
        """
        # Get the agent
        agent = self.get_agent(agent_id)
        if not agent:
            error_msg = f"Agent with ID {agent_id} not found"
            logger.error(error_msg)
            return {
                "success": False,
                "error": error_msg
            }
        
        # Execute the tool with the agent
        return agent.execute_tool(tool_type, **kwargs)
    
    def execute_tool_with_default_agent(self, session_id: str, tool_type: str, **kwargs) -> Dict[str, Any]:
        """
        Execute a tool with the default agent for a session.
        
        Args:
            session_id: Session ID
            tool_type: Type of tool to execute
            **kwargs: Parameters for the tool
            
        Returns:
            Result of the tool execution
        """
        # Get the default agent
        agent = self.get_default_agent(session_id)
        if not agent:
            # Create a new default agent if none exists
            agent = self.create_agent(
                name="Default Agent",
                role=AgentRole.ASSISTANT,
                session_id=session_id
            )
            self.default_agents[session_id] = agent.id
        
        # Execute the tool with the agent
        return agent.execute_tool(tool_type, **kwargs)
    
    def execute_task_with_agent(self, agent_id: str, task_description: str, 
                             task_data: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Execute a task with a specific agent.
        
        Args:
            agent_id: ID of the agent to use
            task_description: Description of the task to execute
            task_data: Additional data for the task
            
        Returns:
            Result of the task execution
        """
        # Get the agent
        agent = self.get_agent(agent_id)
        if not agent:
            error_msg = f"Agent with ID {agent_id} not found"
            logger.error(error_msg)
            return {
                "success": False,
                "error": error_msg
            }
        
        # Execute the task with the agent
        return agent.execute_task(task_description, task_data)
    
    def get_agent_status(self, agent_id: str) -> Dict[str, Any]:
        """Get the status of an agent."""
        agent = self.get_agent(agent_id)
        if not agent:
            return {
                "success": False,
                "error": f"Agent with ID {agent_id} not found"
            }
        
        return {
            "success": True,
            "agent_id": agent.id,
            "agent_name": agent.name,
            "status": agent.status,
            "role": agent.role,
            "last_active": agent.last_active.isoformat()
        }
    
    def get_all_agent_statuses(self, session_id: str = None) -> List[Dict[str, Any]]:
        """
        Get the status of all agents.
        
        Args:
            session_id: Optional session ID to filter by
            
        Returns:
            List of agent statuses
        """
        if session_id:
            # Get agents for this session
            agents = self.get_agents_for_session(session_id)
        else:
            # Get all agents
            agents = list(self.agents.values())
        
        # Build status list
        statuses = []
        for agent in agents:
            statuses.append({
                "agent_id": agent.id,
                "agent_name": agent.name,
                "status": agent.status,
                "role": agent.role,
                "last_active": agent.last_active.isoformat()
            })
        
        return statuses

# Singleton instance
agent_manager = AgentManager()
