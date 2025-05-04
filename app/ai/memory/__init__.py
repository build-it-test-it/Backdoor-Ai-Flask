"""
Memory Management System for Backdoor AI

This module provides a memory management system for Backdoor AI, inspired by
the OpenHands memory management implementation but adapted for Python, Flask, and
SQLAlchemy integration.
"""

from app.ai.memory.conversation_memory import ConversationMemory
from app.ai.memory.condenser import Condenser, NoOpCondenser, SummaryCondenser

__all__ = [
    'ConversationMemory',
    'Condenser',
    'NoOpCondenser',
    'SummaryCondenser'
]

