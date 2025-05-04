"""
Agent Base Class for Backdoor AI

This module provides the base Agent class for Backdoor AI, inspired by
the OpenHands agent implementation but adapted for Python, Flask, and
SQLAlchemy integration.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Type, ClassVar
import logging
import uuid
from datetime import datetime

from app.database import db
from app.ai.mcp_models import Agent as AgentModel, AgentStatus, AgentRole
from app.ai.agent_fsm import AgentFSM
from app.ai.tool_schema import tool_registry
from app.ai.agent.agent_config import AgentConfig

# Set up logging
logger = logging.getLogger("agent")


class AgentError(Exception):
    """Base error class for agent-related errors."""
    pass


class Agent(ABC):
    """
    This abstract base class is a general interface for an agent dedicated to
    executing a specific instruction and allowing human interaction with the
    agent during execution.
    It tracks the execution status and maintains a history of interactions.
    """
    
    DEPRECATED = False
    _registry: ClassVar[Dict[str, Type['Agent']]] = {}
    
    def __init__(
        self,
        id: str,
        name: str,
        role: AgentRole,
        config: AgentConfig,
        session_id: Optional[str] = None
    ):
        """
        Initialize an agent.
        
        Args:
            id: Unique identifier for the agent
            name: Human-readable name for the agent
            role: Role of the agent (determines permissions)
            config: Configuration for the agent
            session_id: Optional session ID for session-specific agents
        """
        self.id = id
        self.name = name
        self.role = role
        self.config = config
        self.session_id = session_id
        self.fsm = AgentFSM.get_fsm_for_agent(id)
        self._complete = False
        self.tools: List[Dict[str, Any]] = []
        
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
    
    @property
    def complete(self) -> bool:
        """Indicates whether the current instruction execution is complete.

        Returns:
        - complete (bool): True if execution is complete; False otherwise.
        """
        return self._complete
    
    @abstractmethod
    async def step(self, state: Any) -> Any:
        """Performs one step using the agent.

        This method should be implemented by subclasses to define the specific execution logic.
        
        Args:
            state: The current state of the agent's execution
            
        Returns:
            The result of the step
        """
        pass
    
    def reset(self) -> None:
        """Resets the agent's execution status and clears the history. This method can be used
        to prepare the agent for restarting the instruction or cleaning up before destruction.
        """
        self._complete = False
        
        # Reset the FSM
        self.fsm = AgentFSM.get_fsm_for_agent(self.id)
    
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
            
            # Update agent memory with confirmation request
            if agent.memory is None:
                agent.memory = {}
            
            if 'confirmations' not in agent.memory:
                agent.memory['confirmations'] = []
            
            agent.memory['confirmations'].append({
                'id': confirmation_id,
                'agent_id': self.id,
                'confirmation_type': 'tool_execution',
                'description': f"Execute tool: {tool_name}",
                'data': {
                    'tool_name': tool_name,
                    'parameters': parameters
                },
                'created_at': datetime.utcnow().isoformat()
            })
            
            db.session.add(agent)
            db.session.commit()
            
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
            import traceback
            traceback.print_exc()
            
            return {
                "success": False,
                "error": str(e),
                "error_type": "execution"
            }
    
    def get_system_message(self) -> Optional[Dict[str, Any]]:
        """
        Returns a system message containing the system prompt and tools.
        This will be used as the first message in a conversation.

        Returns:
            Dict containing the system message content and tools, or None if error
        """
        try:
            # Get system message content (to be implemented by subclasses)
            system_message = self._get_system_message_content()
            
            # Get tools if available
            tools = getattr(self, 'tools', None)
            
            return {
                "content": system_message,
                "tools": tools,
                "agent_class": self.__class__.__name__
            }
        except Exception as e:
            logger.warning(f"[{self.__class__.__name__}] Failed to generate system message: {e}")
            return None
    
    def _get_system_message_content(self) -> str:
        """
        Get the content for the system message.
        This should be implemented by subclasses to provide agent-specific system messages.
        
        Returns:
            The system message content as a string
        """
        return f"You are {self.name}, a helpful AI assistant."
    
    @classmethod
    def register(cls, name: str, agent_cls: Type['Agent']) -> None:
        """Registers an agent class in the registry.

        Parameters:
        - name (str): The name to register the class under.
        - agent_cls (Type['Agent']): The class to register.

        Raises:
        - AgentError: If name already registered
        """
        if name in cls._registry:
            raise AgentError(f"Agent already registered: {name}")
        cls._registry[name] = agent_cls
    
    @classmethod
    def get_cls(cls, name: str) -> Type['Agent']:
        """Retrieves an agent class from the registry.

        Parameters:
        - name (str): The name of the class to retrieve

        Returns:
        - agent_cls (Type['Agent']): The class registered under the specified name.

        Raises:
        - AgentError: If name not registered
        """
        if name not in cls._registry:
            raise AgentError(f"Agent not registered: {name}")
        return cls._registry[name]
    
    @classmethod
    def list_agents(cls) -> List[str]:
        """Retrieves the list of all agent names from the registry.

        Returns:
            List of agent names
            
        Raises:
            AgentError: If no agent is registered
        """
        if not bool(cls._registry):
            raise AgentError("No agents registered")
        return list(cls._registry.keys())


class AgentManager:
    """
    Manager for agents in Backdoor AI.
    
    This class provides functions for creating, retrieving, and managing agents.
    """
    
    def __init__(self):
        """Initialize the agent manager."""
        self.agents: Dict[str, Agent] = {}
    
    def create_agent(self, 
                    name: str, 
                    role: AgentRole,
                    agent_class: str,
                    config: Optional[AgentConfig] = None,
                    session_id: Optional[str] = None,
                    agent_id: Optional[str] = None) -> Agent:
        """
        Create a new agent.
        
        Args:
            name: Name for the agent
            role: Role of the agent
            agent_class: Class name of the agent to create
            config: Optional configuration for the agent
            session_id: Optional session ID for session-specific agents
            agent_id: Optional ID for the agent, generated if not provided
            
        Returns:
            The created agent
            
        Raises:
            AgentError: If agent class not found
        """
        # Generate agent ID if not provided
        if agent_id is None:
            agent_id = str(uuid.uuid4())
        
        # Get the agent class
        try:
            agent_cls = Agent.get_cls(agent_class)
        except AgentError:
            raise AgentError(f"Agent class not found: {agent_class}")
        
        # Use default config if not provided
        if config is None:
            config = AgentConfig()
        
        # Create the agent
        agent = agent_cls(
            id=agent_id,
            name=name,
            role=role,
            config=config,
            session_id=session_id
        )
        
        # Store in local cache
        self.agents[agent_id] = agent
        
        return agent
    
    def get_agent(self, agent_id: str) -> Optional[Agent]:
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
            # We need to know the agent class to create the right instance
            # For now, we'll assume it's stored in the memory field
            memory = agent_record.memory or {}
            agent_class = memory.get('agent_class', 'DefaultAgent')
            
            try:
                # Get the agent class
                agent_cls = Agent.get_cls(agent_class)
                
                # Create agent instance with default config
                agent = agent_cls(
                    id=agent_record.id,
                    name=agent_record.name,
                    role=agent_record.role,
                    config=AgentConfig(),
                    session_id=agent_record.session_id
                )
                
                # Store in local cache
                self.agents[agent_id] = agent
                
                return agent
            except AgentError:
                logger.error(f"Agent class not found: {agent_class}")
                return None
        
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
                memory = agent.memory or {}
                result.append({
                    "id": agent.id,
                    "name": agent.name,
                    "role": agent.role,
                    "session_id": agent.session_id,
                    "status": agent.status,
                    "last_active": agent.last_active.isoformat() if agent.last_active else None,
                    "tool_permissions": agent.tool_permissions,
                    "agent_class": memory.get('agent_class', 'Unknown'),
                    "has_pending_confirmations": bool(memory and 
                                                    memory.get('confirmations') and 
                                                    len(memory['confirmations']) > 0)
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
agent_manager = AgentManager()

