"""
Agent Controller for Backdoor AI

This module provides the AgentController class for Backdoor AI, inspired by
the OpenHands agent controller implementation but adapted for Python, Flask, and
SQLAlchemy integration.
"""

from __future__ import annotations

import asyncio
import logging
import time
import traceback
from typing import Dict, List, Any, Optional, Tuple, ClassVar, Type
from datetime import datetime

from app.database import db
from app.ai.mcp_models import Agent as AgentModel, AgentStatus
from app.ai.agent.agent import Agent, AgentError
from app.ai.tool_schema import tool_registry

# Set up logging
logger = logging.getLogger("agent_controller")


class AgentController:
    """
    Controller for managing agent execution and state.
    
    This class manages the execution of an agent, handling state transitions,
    error handling, and interaction with the database.
    """
    
    def __init__(
        self,
        agent: Agent,
        max_iterations: int = 10,
        max_budget: Optional[float] = None,
        session_id: Optional[str] = None,
        confirmation_mode: bool = False,
        parent: Optional['AgentController'] = None,
        is_delegate: bool = False,
        headless_mode: bool = True
    ):
        """
        Initialize an agent controller.
        
        Args:
            agent: The agent to control
            max_iterations: Maximum number of iterations to run
            max_budget: Maximum budget (in tokens or cost) for the agent
            session_id: Optional session ID for tracking
            confirmation_mode: Whether to require confirmation for actions
            parent: Optional parent controller for delegation
            is_delegate: Whether this controller is a delegate
            headless_mode: Whether to run in headless mode (no UI)
        """
        self.id = session_id or agent.session_id or agent.id
        self.agent = agent
        self.max_iterations = max_iterations
        self.max_budget = max_budget
        self.confirmation_mode = confirmation_mode
        self.parent = parent
        self.is_delegate = is_delegate
        self.headless_mode = headless_mode
        
        # State tracking
        self.iteration = 0
        self.start_time = time.time()
        self.last_action_time = self.start_time
        self.state = self._load_or_create_state()
        
        # Delegation
        self.delegate: Optional[AgentController] = None
        
        # Pending action tracking
        self._pending_action_info: Optional[Tuple[Any, float]] = None  # (action, timestamp)
        self._closed = False
    
    def _load_or_create_state(self) -> Dict[str, Any]:
        """Load agent state from database or create if not exists."""
        try:
            # Try to load agent
            agent_model = db.session.query(AgentModel).filter(AgentModel.id == self.agent.id).first()
            
            if agent_model and agent_model.memory:
                # Get state from memory
                state = agent_model.memory.get('controller_state', {})
                logger.debug(f"Loaded controller state from database for agent: {self.agent.id}")
                return state
            else:
                # Create new state
                state = {
                    'iteration': 0,
                    'start_time': self.start_time,
                    'last_action_time': self.last_action_time,
                    'history': [],
                    'metrics': {
                        'token_usage': {
                            'prompt_tokens': 0,
                            'completion_tokens': 0,
                            'total_tokens': 0
                        },
                        'cost': 0.0
                    }
                }
                
                # Save to database
                self._save_state(state)
                
                logger.info(f"Created new controller state for agent: {self.agent.id}")
                return state
        except Exception as e:
            logger.error(f"Error loading/creating controller state: {e}")
            # Return default state
            return {
                'iteration': 0,
                'start_time': self.start_time,
                'last_action_time': self.last_action_time,
                'history': [],
                'metrics': {
                    'token_usage': {
                        'prompt_tokens': 0,
                        'completion_tokens': 0,
                        'total_tokens': 0
                    },
                    'cost': 0.0
                }
            }
    
    def _save_state(self, state: Dict[str, Any]) -> None:
        """Save agent state to database."""
        try:
            agent_model = db.session.query(AgentModel).filter(AgentModel.id == self.agent.id).first()
            
            if agent_model:
                # Initialize memory if needed
                if agent_model.memory is None:
                    agent_model.memory = {}
                
                # Update state
                agent_model.memory['controller_state'] = state
                
                # Update last active
                agent_model.last_active = datetime.utcnow()
                
                db.session.add(agent_model)
                db.session.commit()
                
                logger.debug(f"Saved controller state for agent: {self.agent.id}")
            else:
                logger.error(f"Agent not found in database: {self.agent.id}")
        except Exception as e:
            logger.error(f"Error saving controller state: {e}")
            db.session.rollback()
    
    async def step(self) -> Tuple[bool, Any]:
        """
        Perform one step of agent execution.
        
        Returns:
            Tuple of (continue, result) where:
            - continue: Whether to continue execution
            - result: The result of the step
        """
        # Check if we've reached the maximum number of iterations
        if self.iteration >= self.max_iterations:
            logger.info(f"Reached maximum iterations ({self.max_iterations}) for agent: {self.agent.id}")
            return False, {"status": "max_iterations_reached"}
        
        # Check if we've exceeded the maximum budget
        if self.max_budget is not None and self.state['metrics']['cost'] > self.max_budget:
            logger.info(f"Exceeded maximum budget ({self.max_budget}) for agent: {self.agent.id}")
            return False, {"status": "max_budget_exceeded"}
        
        # Check if the agent is complete
        if self.agent.complete:
            logger.info(f"Agent is complete: {self.agent.id}")
            return False, {"status": "agent_complete"}
        
        # Update state before step
        self.iteration += 1
        self.state['iteration'] = self.iteration
        self.last_action_time = time.time()
        self.state['last_action_time'] = self.last_action_time
        
        try:
            # Execute the agent step
            result = await self.agent.step(self.state)
            
            # Update state after step
            self._update_state_after_step(result)
            
            return True, result
        except Exception as e:
            logger.error(f"Error executing agent step: {e}")
            traceback.print_exc()
            
            # Update state with error
            self._update_state_with_error(e)
            
            return False, {"status": "error", "error": str(e)}
    
    def _update_state_after_step(self, result: Any) -> None:
        """Update state after a successful step."""
        # Add result to history
        self.state['history'].append({
            'timestamp': time.time(),
            'iteration': self.iteration,
            'type': 'step',
            'result': result
        })
        
        # Save state
        self._save_state(self.state)
    
    def _update_state_with_error(self, error: Exception) -> None:
        """Update state after an error."""
        # Add error to history
        self.state['history'].append({
            'timestamp': time.time(),
            'iteration': self.iteration,
            'type': 'error',
            'error': str(error)
        })
        
        # Save state
        self._save_state(self.state)
    
    async def run(self, max_steps: Optional[int] = None) -> Dict[str, Any]:
        """
        Run the agent for up to max_steps steps or until completion.
        
        Args:
            max_steps: Maximum number of steps to run, defaults to max_iterations
            
        Returns:
            The final state of the agent
        """
        if max_steps is None:
            max_steps = self.max_iterations
        
        steps_taken = 0
        continue_execution = True
        
        while continue_execution and steps_taken < max_steps:
            continue_execution, result = await self.step()
            steps_taken += 1
            
            # If the agent is delegating, run the delegate
            if hasattr(result, 'get') and result.get('status') == 'delegating':
                delegate_result = await self._handle_delegation(result)
                
                # Update state with delegation result
                self.state['history'].append({
                    'timestamp': time.time(),
                    'iteration': self.iteration,
                    'type': 'delegation',
                    'result': delegate_result
                })
                
                # Save state
                self._save_state(self.state)
        
        # Close the controller
        await self.close()
        
        return {
            'steps_taken': steps_taken,
            'max_steps': max_steps,
            'complete': self.agent.complete,
            'state': self.state
        }
    
    async def _handle_delegation(self, delegation_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle delegation to another agent.
        
        Args:
            delegation_info: Information about the delegation
            
        Returns:
            The result of the delegation
        """
        # Extract delegation information
        delegate_agent_class = delegation_info.get('agent_class')
        delegate_inputs = delegation_info.get('inputs', {})
        
        if not delegate_agent_class:
            raise AgentError("Missing agent_class in delegation info")
        
        try:
            # Get the agent class
            agent_cls = Agent.get_cls(delegate_agent_class)
            
            # Create the delegate agent
            from app.ai.agent.agent import agent_manager
            delegate_agent = agent_manager.create_agent(
                name=f"Delegate-{delegate_agent_class}",
                role=self.agent.role,
                agent_class=delegate_agent_class,
                session_id=self.id
            )
            
            # Create the delegate controller
            self.delegate = AgentController(
                agent=delegate_agent,
                max_iterations=self.max_iterations,
                max_budget=self.max_budget,
                session_id=self.id,
                confirmation_mode=self.confirmation_mode,
                parent=self,
                is_delegate=True,
                headless_mode=self.headless_mode
            )
            
            # Run the delegate
            delegate_result = await self.delegate.run()
            
            # Clean up
            self.delegate = None
            
            return delegate_result
        except Exception as e:
            logger.error(f"Error handling delegation: {e}")
            traceback.print_exc()
            
            return {
                'status': 'error',
                'error': str(e)
            }
    
    async def close(self) -> None:
        """Close the controller and clean up resources."""
        if self._closed:
            return
        
        # Close any delegate
        if self.delegate:
            await self.delegate.close()
            self.delegate = None
        
        # Update final state
        self.state['end_time'] = time.time()
        self.state['duration'] = self.state['end_time'] - self.state['start_time']
        
        # Save final state
        self._save_state(self.state)
        
        self._closed = True
        logger.info(f"Closed controller for agent: {self.agent.id}")
    
    def __del__(self):
        """Ensure resources are cleaned up."""
        if not self._closed:
            asyncio.create_task(self.close())

