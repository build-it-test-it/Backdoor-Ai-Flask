"""
Backdoor Microagent System

This module provides a microagent system for Backdoor AI, inspired by
the OpenHands microagent implementation but adapted for Python, Flask, and
SQLAlchemy integration.
"""

from app.ai.microagent.microagent import (
    BaseMicroagent,
    KnowledgeMicroagent,
    RepoMicroagent,
    load_microagents_from_dir
)
from app.ai.microagent.types import MicroagentMetadata, MicroagentType

__all__ = [
    'BaseMicroagent',
    'KnowledgeMicroagent',
    'RepoMicroagent',
    'load_microagents_from_dir',
    'MicroagentMetadata',
    'MicroagentType'
]

