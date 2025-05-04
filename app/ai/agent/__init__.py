"""
Backdoor Agent System

This module provides a flexible agent system for Backdoor AI, inspired by
the OpenHands agent implementation but adapted for Python, Flask, and
SQLAlchemy integration.
"""

from app.ai.agent.agent import Agent, AgentManager
from app.ai.agent.agent_controller import AgentController
from app.ai.agent.agent_config import AgentConfig

__all__ = [
    'Agent',
    'AgentManager',
    'AgentController',
    'AgentConfig'
]

