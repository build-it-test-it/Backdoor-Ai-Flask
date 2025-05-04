"""
Finite State Machine (FSM) for Agent State Management

This module provides a Finite State Machine implementation for managing agent states
and transitions in the Backdoor AI system. Inspired by the Cloudflare AI FSM implementation,
but adapted for Python and SQLAlchemy integration.
"""

import logging
import asyncio
from typing import Dict, List, Any, Optional, Union, Callable, TypeVar, Generic, Awaitable
from enum import Enum
from datetime import datetime

from app.database import db
from app.ai.mcp_models import Agent, AgentStatus

# Set up logging
logger = logging.getLogger("agent_fsm")

# Type variables for type hints
T = TypeVar('T')
StateType = TypeVar('StateType', bound=str)
EventType = TypeVar('EventType', bound=str)

class Transition:
    """A transition in the Finite State Machine."""
    
    def __init__(
        self, 
        from_state: Union[str, List[str]], 
        event: str, 
        to_state: Union[str, Callable[..., str]],
        guards: Optional[List[Callable[..., bool]]] = None
    ):
        """
        Initialize a transition in the FSM.
        
        Args:
            from_state: The state(s) this transition can occur from
            event: The event that triggers this transition
            to_state: The destination state or a function that returns the destination state
            guards: Optional list of guard functions that must all return True for the transition to occur
        """
        self.from_state = from_state if isinstance(from_state, list) else [from_state]
        self.event = event
        self.to_state = to_state
        self.guards = guards or []
    
    def can_transition(self, current_state: str, *args, **kwargs) -> bool:
        """
        Check if this transition can occur given the current state and optional args.
        
        Args:
            current_state: The current state
            *args, **kwargs: Arguments to pass to guard functions
            
        Returns:
            True if transition is possible, False otherwise
        """
        if current_state not in self.from_state:
            return False
        
        # Check all guards
        return all(guard(*args, **kwargs) for guard in self.guards)
    
    def get_target_state(self, *args, **kwargs) -> str:
        """
        Get the target state for this transition.
        
        Args:
            *args, **kwargs: Arguments to pass to the to_state function if it's callable
            
        Returns:
            The target state as a string
        """
        if callable(self.to_state):
            return self.to_state(*args, **kwargs)
        return self.to_state


class StateMachine(Generic[StateType, EventType]):
    """
    A generic finite state machine implementation.
    
    This class manages state transitions according to defined rules and
    can execute hooks before and after transitions.
    """
    
    def __init__(
        self,
        initial_state: StateType,
        transitions: List[Transition],
        on_transition: Optional[Callable[[StateType, EventType, StateType, Any], None]] = None,
        on_invalid_transition: Optional[Callable[[StateType, EventType, Any], None]] = None
    ):
        """
        Initialize the state machine.
        
        Args:
            initial_state: The initial state
            transitions: A list of Transition objects defining valid state transitions
            on_transition: Optional callback for successful transitions
            on_invalid_transition: Optional callback for invalid transitions
        """
        self.current_state = initial_state
        self.transitions = transitions
        self.on_transition = on_transition
        self.on_invalid_transition = on_invalid_transition
        self.transition_lock = asyncio.Lock()
        
        # Build a map of event -> list of possible transitions for faster lookup
        self.transition_map: Dict[str, List[Transition]] = {}
        for transition in transitions:
            if transition.event not in self.transition_map:
                self.transition_map[transition.event] = []
            self.transition_map[transition.event].append(transition)
    
    async def trigger(self, event: EventType, *args, **kwargs) -> bool:
        """
        Trigger an event and transition to the appropriate state if possible.
        
        Args:
            event: The event to trigger
            *args, **kwargs: Arguments to pass to guard functions and to_state functions
            
        Returns:
            True if transition occurred, False otherwise
        """
        async with self.transition_lock:
            # Find all transitions for this event
            possible_transitions = self.transition_map.get(event, [])
            
            # Find the first valid transition
            for transition in possible_transitions:
                if transition.can_transition(self.current_state, *args, **kwargs):
                    # Get the target state
                    new_state = transition.get_target_state(*args, **kwargs)
                    
                    # Log the transition
                    logger.info(f"Transitioning from {self.current_state} to {new_state} on event {event}")
                    
                    # Save the old state for the callback
                    old_state = self.current_state
                    
                    # Update the state
                    self.current_state = new_state
                    
                    # Call the transition callback if provided
                    if self.on_transition:
                        self.on_transition(old_state, event, new_state, {"args": args, "kwargs": kwargs})
                    
                    return True
            
            # No valid transition found
            logger.warning(f"No valid transition found for event {event} in state {self.current_state}")
            
            # Call the invalid transition callback if provided
            if self.on_invalid_transition:
                self.on_invalid_transition(self.current_state, event, {"args": args, "kwargs": kwargs})
            
            return False
    
    def can_trigger(self, event: EventType, *args, **kwargs) -> bool:
        """
        Check if an event can be triggered in the current state.
        
        Args:
            event: The event to check
            *args, **kwargs: Arguments to pass to guard functions
            
        Returns:
            True if the event can be triggered, False otherwise
        """
        # Find all transitions for this event
        possible_transitions = self.transition_map.get(event, [])
        
        # Check if any transition is valid
        for transition in possible_transitions:
            if transition.can_transition(self.current_state, *args, **kwargs):
                return True
        
        return False
    
    def get_current_state(self) -> StateType:
        """Get the current state of the FSM."""
        return self.current_state


class AgentFSM(StateMachine):
    """
    A Finite State Machine specialized for Backdoor AI agents.
    
    This class extends the generic StateMachine with agent-specific functionality
    and database integration.
    """
    
    def __init__(
        self,
        agent_id: str,
        initial_state: AgentStatus = AgentStatus.READY,
        transitions: Optional[List[Transition]] = None
    ):
        """
        Initialize the agent FSM.
        
        Args:
            agent_id: The ID of the agent
            initial_state: The initial state, defaults to READY
            transitions: Optional list of transitions, defaults to standard agent transitions
        """
        self.agent_id = agent_id
        
        # Default transitions if none provided
        if transitions is None:
            transitions = [
                # From READY
                Transition(AgentStatus.READY, "execute_tool", AgentStatus.BUSY),
                Transition(AgentStatus.READY, "execute_task", AgentStatus.BUSY),
                Transition(AgentStatus.READY, "pause", AgentStatus.IDLE),
                
                # From BUSY
                Transition(AgentStatus.BUSY, "complete", AgentStatus.READY),
                Transition(AgentStatus.BUSY, "error", AgentStatus.ERROR),
                
                # From IDLE
                Transition(AgentStatus.IDLE, "resume", AgentStatus.READY),
                
                # From ERROR
                Transition(AgentStatus.ERROR, "reset", AgentStatus.READY),
                Transition(AgentStatus.ERROR, "offline", AgentStatus.OFFLINE),
                
                # From OFFLINE
                Transition(AgentStatus.OFFLINE, "online", AgentStatus.READY)
            ]
        
        # Call parent init
        super().__init__(
            initial_state=initial_state, 
            transitions=transitions,
            on_transition=self._on_agent_transition,
            on_invalid_transition=self._on_invalid_agent_transition
        )
    
    def _on_agent_transition(
        self,
        old_state: AgentStatus,
        event: str,
        new_state: AgentStatus,
        context: Any
    ) -> None:
        """
        Callback when an agent transitions to a new state.
        
        Args:
            old_state: The previous state
            event: The event that triggered the transition
            new_state: The new state
            context: Additional context data
        """
        try:
            # Update the agent in the database
            agent = db.session.query(Agent).filter(Agent.id == self.agent_id).first()
            if agent:
                agent.status = new_state
                agent.last_active = datetime.utcnow()
                
                # Log the transition in the agent's memory
                if agent.memory is None:
                    agent.memory = {}
                
                # Add transition to state history
                if 'state_history' not in agent.memory:
                    agent.memory['state_history'] = []
                
                agent.memory['state_history'].append({
                    'from_state': old_state,
                    'to_state': new_state,
                    'event': event,
                    'timestamp': datetime.utcnow().isoformat()
                })
                
                # Limit history size
                if len(agent.memory['state_history']) > 20:
                    agent.memory['state_history'] = agent.memory['state_history'][-20:]
                
                db.session.add(agent)
                db.session.commit()
                
                logger.info(f"Agent {self.agent_id} transitioned from {old_state} to {new_state} on event {event}")
            else:
                logger.error(f"Agent {self.agent_id} not found in database")
        except Exception as e:
            logger.error(f"Error updating agent state in database: {e}")
            db.session.rollback()
    
    def _on_invalid_agent_transition(
        self,
        current_state: AgentStatus,
        event: str,
        context: Any
    ) -> None:
        """
        Callback when an invalid transition is attempted.
        
        Args:
            current_state: The current state
            event: The event that was attempted
            context: Additional context data
        """
        logger.warning(f"Invalid transition attempted for agent {self.agent_id}: {current_state} -> {event}")
        
        # Log the invalid transition in the database
        try:
            agent = db.session.query(Agent).filter(Agent.id == self.agent_id).first()
            if agent:
                # Add to invalid transitions log
                if agent.memory is None:
                    agent.memory = {}
                
                if 'invalid_transitions' not in agent.memory:
                    agent.memory['invalid_transitions'] = []
                
                agent.memory['invalid_transitions'].append({
                    'state': current_state,
                    'event': event,
                    'timestamp': datetime.utcnow().isoformat()
                })
                
                # Limit log size
                if len(agent.memory['invalid_transitions']) > 10:
                    agent.memory['invalid_transitions'] = agent.memory['invalid_transitions'][-10:]
                
                db.session.add(agent)
                db.session.commit()
        except Exception as e:
            logger.error(f"Error logging invalid transition in database: {e}")
            db.session.rollback()
    
    @classmethod
    def get_fsm_for_agent(cls, agent_id: str) -> 'AgentFSM':
        """
        Get or create an FSM for an agent.
        
        Args:
            agent_id: The ID of the agent
            
        Returns:
            An AgentFSM instance for the agent
        """
        try:
            # Get the agent from the database
            agent = db.session.query(Agent).filter(Agent.id == agent_id).first()
            if agent:
                # Create FSM with current agent state
                return cls(agent_id, initial_state=agent.status)
            else:
                logger.warning(f"Agent {agent_id} not found, creating FSM with default state")
                return cls(agent_id)
        except Exception as e:
            logger.error(f"Error getting FSM for agent {agent_id}: {e}")
            return cls(agent_id)
