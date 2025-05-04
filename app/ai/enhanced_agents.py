"""
Enhanced Agent System for Backdoor AI

This module provides an enhanced agent system for Backdoor AI, inspired by
the Cloudflare AI agent implementations but adapted for Python, Flask, and
SQLAlchemy integration.
"""

import json
import uuid
import logging
import asyncio
from typing import Dict, List, Any, Optional, Union, Callable, Type, TypeVar
from enum import Enum
from datetime import datetime
import traceback

from app.database import db
from app.ai.mcp_models import Agent as AgentModel, AgentStatus, AgentRole
from app.ai.agent_fsm import AgentFSM
from app.ai.tool_schema import tool_registry

# Set up logging
logger = logging.getLogger("enhanced_agents")

class AgentError(Exception):
    """Base error class for agent-related errors."""
    pass

class ConfirmationType(str, Enum):
    """Types of confirmations that an agent might request."""
    TOOL_EXECUTION = "tool_execution"
    TASK_EXECUTION = "task_execution"
    STATE_CHANGE = "state_change"
    DATA_ACCESS = "data_access"
    DECISION = "decision"

class Confirmation:
    """A confirmation request from an agent."""
    
    def __init__(
        self,
        id: str,
        agent_id: str,
        confirmation_type: ConfirmationType,
        description: str,
        data: Dict[str, Any],
        created_at: datetime = None
    ):
        """
        Initialize a confirmation request.
        
        Args:
            id: Unique identifier for the confirmation
            agent_id: ID of the agent requesting confirmation
            confirmation_type: Type of confirmation
            description: Human-readable description of what's being confirmed
            data: Additional data relevant to the confirmation
            created_at: When the confirmation was created, defaults to now
        """
        self.id = id
        self.agent_id = agent_id
        self.confirmation_type = confirmation_type
        self.description = description
        self.data = data
        self.created_at = created_at or datetime.utcnow()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "id": self.id,
            "agent_id": self.agent_id,
            "confirmation_type": self.confirmation_type,
            "description": self.description,
            "data": self.data,
            "created_at": self.created_at.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Confirmation':
        """Create a Confirmation from a dictionary."""
        return cls(
            id=data["id"],
            agent_id=data["agent_id"],
            confirmation_type=data["confirmation_type"],
            description=data["description"],
            data=data["data"],
            created_at=datetime.fromisoformat(data["created_at"])
        )

class EnhancedAgent:
    """
    Enhanced agent with state management and human-in-the-loop capabilities.
    
    This class provides a more powerful agent implementation with robust
    state management and confirmation flows.
    """
    
    def __init__(self, id: str, name: str, role: AgentRole, session_id: Optional[str] = None):
        """
        Initialize an enhanced agent.
        
        Args:
            id: Unique identifier for the agent
            name: Human-readable name for the agent
            role: Role of the agent (determines permissions)
            session_id: Optional session ID for session-specific agents
        """
        self.id = id
        self.name = name
        self.role = role
        self.session_id = session_id
        self.fsm = AgentFSM.get_fsm_for_agent(id)
        self.confirmations: List[Confirmation] = []
        
        # Load agent from database or create if not exists
        self._load_or_create_agent()
    
    def _load_or_create_agent(self) -> None:
        """Load agent from database or create if not exists."""
        try:
            # Try to load agent
            agent = db.session.query(AgentModel).filter(AgentModel.id == self.id).first()
            
            if agent:
                # Update existing agent
                self.name = agent.name
                self.role = agent.role
                self.session_id = agent.session_id
                
                # Load confirmations from memory
                if agent.memory and 'confirmations' in agent.memory:
                    self.confirmations = [
                        Confirmation.from_dict(conf) 
                        for conf in agent.memory['confirmations']
                    ]
                
                logger.debug(f"Loaded agent from database: {self.name} ({self.id})")
            else:
                # Create new agent
                agent = AgentModel(
                    id=self.id,
                    name=self.name,
                    role=self.role,
                    session_id=self.session_id,
                    status=AgentStatus.READY,
                    memory={},
                    tool_permissions=[]
                )
                
                db.session.add(agent)
                db.session.commit()
                
                logger.info(f"Created new agent in database: {self.name} ({self.id})")
        except Exception as e:
            logger.error(f"Error loading/creating agent: {e}")
            db.session.rollback()
    
    async def execute_tool(self, 
                         tool_name: str, 
                         parameters: Dict[str, Any],
                         require_confirmation: bool = False) -> Dict[str, Any]:
        """
        Execute a tool with the given parameters.
        
        Args:
            tool_name: Name of the tool to execute
            parameters: Parameters for the tool
            require_confirmation: Whether to require human confirmation before execution
            
        Returns:
            Result of the tool execution
            
        Raises:
            AgentError: If tool execution fails or is not permitted
        """
        # Check if agent can execute tools (must be in READY state)
        if not await self.fsm.can_trigger("execute_tool"):
            current_state = self.fsm.get_current_state()
            raise AgentError(f"Agent cannot execute tools in state: {current_state}")
        
        # Get the tool
        tool = tool_registry.get_tool(tool_name)
        if not tool:
            raise AgentError(f"Tool not found: {tool_name}")
        
        # Check permissions
        agent = db.session.query(AgentModel).filter(AgentModel.id == self.id).first()
        if not agent:
            raise AgentError(f"Agent not found in database: {self.id}")
        
        # Ensure tool_permissions is a list
        if agent.tool_permissions is None:
            agent.tool_permissions = []
        
        if tool_name not in agent.tool_permissions:
            raise AgentError(f"Agent does not have permission to use tool: {tool_name}")
        
        # If confirmation is required, create a confirmation request
        if require_confirmation:
            confirmation_id = str(uuid.uuid4())
            confirmation = Confirmation(
                id=confirmation_id,
                agent_id=self.id,
                confirmation_type=ConfirmationType.TOOL_EXECUTION,
                description=f"Execute tool: {tool_name}",
                data={
                    "tool_name": tool_name,
                    "parameters": parameters
                }
            )
            
            # Store confirmation
            self.confirmations.append(confirmation)
            
            # Update agent memory
            self._update_confirmations()
            
            # Return confirmation ID
            return {
                "status": "confirmation_required",
                "confirmation_id": confirmation_id,
                "message": f"Confirmation required to execute tool: {tool_name}"
            }
        
        # Transition to BUSY state
        await self.fsm.trigger("execute_tool")
        
        try:
            # Execute the tool
            result = tool_registry.execute_tool(
                name=tool_name,
                parameters=parameters,
                agent_id=self.id
            )
            
            # Transition back to READY state
            await self.fsm.trigger("complete")
            
            return result
        except Exception as e:
            # Transition to ERROR state
            await self.fsm.trigger("error")
            
            # Log the error
            logger.error(f"Error executing tool {tool_name}: {e}")
            traceback.print_exc()
            
            return {
                "success": False,
                "error": str(e),
                "error_type": "execution"
            }
    
    async def execute_confirmation(self, confirmation_id: str) -> Dict[str, Any]:
        """
        Execute a previously requested confirmation.
        
        Args:
            confirmation_id: ID of the confirmation to execute
            
        Returns:
            Result of the executed action
            
        Raises:
            AgentError: If confirmation not found or execution fails
        """
        # Find the confirmation
        confirmation = next((c for c in self.confirmations if c.id == confirmation_id), None)
        if not confirmation:
            raise AgentError(f"Confirmation not found: {confirmation_id}")
        
        # Process based on confirmation type
        if confirmation.confirmation_type == ConfirmationType.TOOL_EXECUTION:
            # Execute the tool
            tool_name = confirmation.data.get("tool_name")
            parameters = confirmation.data.get("parameters", {})
            
            # Remove the confirmation
            self.confirmations = [c for c in self.confirmations if c.id != confirmation_id]
            self._update_confirmations()
            
            # Execute the tool
            return await self.execute_tool(tool_name, parameters, require_confirmation=False)
        
        elif confirmation.confirmation_type == ConfirmationType.TASK_EXECUTION:
            # Execute the task (to be implemented)
            pass
        
        elif confirmation.confirmation_type == ConfirmationType.STATE_CHANGE:
            # Change state
            new_state = confirmation.data.get("new_state")
            event = confirmation.data.get("event")
            
            # Remove the confirmation
            self.confirmations = [c for c in self.confirmations if c.id != confirmation_id]
            self._update_confirmations()
            
            # Trigger the state change
            success = await self.fsm.trigger(event)
            
            return {
                "success": success,
                "message": f"State change to {new_state}" + (" successful" if success else " failed")
            }
        
        # Default case
        return {
            "success": False,
            "error": f"Unknown confirmation type: {confirmation.confirmation_type}"
        }
    
    def _update_confirmations(self) -> None:
        """Update agent confirmations in the database."""
        try:
            agent = db.session.query(AgentModel).filter(AgentModel.id == self.id).first()
            if agent:
                # Ensure memory is initialized
                if agent.memory is None:
                    agent.memory = {}
                
                # Update confirmations
                agent.memory['confirmations'] = [conf.to_dict() for conf in self.confirmations]
                
                db.session.add(agent)
                db.session.commit()
        except Exception as e:
            logger.error(f"Error updating agent confirmations: {e}")
            db.session.rollback()
    
    def get_pending_confirmations(self) -> List[Dict[str, Any]]:
        """
        Get list of pending confirmations.
        
        Returns:
            List of pending confirmations as dictionaries
        """
        return [conf.to_dict() for conf in self.confirmations]

class EnhancedAgentManager:
    """
    Manager for enhanced agents in Backdoor AI.
    
    This class provides functions for creating, retrieving, and managing agents.
    """
    
    def __init__(self):
        """Initialize the agent manager."""
        self.agents: Dict[str, EnhancedAgent] = {}
    
    def create_agent(self, 
                    name: str, 
                    role: AgentRole, 
                    session_id: Optional[str] = None,
                    agent_id: Optional[str] = None) -> EnhancedAgent:
        """
        Create a new agent.
        
        Args:
            name: Name for the agent
            role: Role of the agent
            session_id: Optional session ID for session-specific agents
            agent_id: Optional ID for the agent, generated if not provided
            
        Returns:
            The created agent
        """
        # Generate agent ID if not provided
        if agent_id is None:
            agent_id = str(uuid.uuid4())
        
        # Create the agent
        agent = EnhancedAgent(
            id=agent_id,
            name=name,
            role=role,
            session_id=session_id
        )
        
        # Store in local cache
        self.agents[agent_id] = agent
        
        return agent
    
    def get_agent(self, agent_id: str) -> Optional[EnhancedAgent]:
        """
        Get an agent by ID.
        
        Args:
            agent_id: ID of the agent to get
            
        Returns:
            The agent if found, None otherwise
        """
        # Check if agent is in local cache
        if agent_id in self.agents:
            return self.agents[agent_id]
        
        # Check if agent exists in database
        agent_record = db.session.query(AgentModel).filter(AgentModel.id == agent_id).first()
        if agent_record:
            # Create agent instance
            agent = EnhancedAgent(
                id=agent_record.id,
                name=agent_record.name,
                role=agent_record.role,
                session_id=agent_record.session_id
            )
            
            # Store in local cache
            self.agents[agent_id] = agent
            
            return agent
        
        return None
    
    def list_agents(self, session_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        List all agents, optionally filtered by session.
        
        Args:
            session_id: Optional session ID to filter by
            
        Returns:
            List of agents as dictionaries
        """
        try:
            # Query the database
            query = db.session.query(AgentModel)
            if session_id:
                query = query.filter(AgentModel.session_id == session_id)
            
            agents = query.all()
            
            # Convert to dictionaries
            result = []
            for agent in agents:
                result.append({
                    "id": agent.id,
                    "name": agent.name,
                    "role": agent.role,
                    "session_id": agent.session_id,
                    "status": agent.status,
                    "last_active": agent.last_active.isoformat() if agent.last_active else None,
                    "tool_permissions": agent.tool_permissions,
                    "has_pending_confirmations": bool(agent.memory and 
                                                    agent.memory.get('confirmations') and 
                                                    len(agent.memory['confirmations']) > 0)
                })
            
            return result
        except Exception as e:
            logger.error(f"Error listing agents: {e}")
            return []
    
    def delete_agent(self, agent_id: str) -> bool:
        """
        Delete an agent.
        
        Args:
            agent_id: ID of the agent to delete
            
        Returns:
            True if the agent was deleted, False otherwise
        """
        try:
            # Remove from local cache
            if agent_id in self.agents:
                del self.agents[agent_id]
            
            # Remove from database
            agent = db.session.query(AgentModel).filter(AgentModel.id == agent_id).first()
            if agent:
                db.session.delete(agent)
                db.session.commit()
                logger.info(f"Deleted agent: {agent_id}")
                return True
            else:
                logger.warning(f"Agent not found: {agent_id}")
                return False
        except Exception as e:
            logger.error(f"Error deleting agent: {e}")
            db.session.rollback()
            return False

# Create singleton instance
enhanced_agent_manager = EnhancedAgentManager()
