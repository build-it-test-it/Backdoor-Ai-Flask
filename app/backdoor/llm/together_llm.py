"""
Together AI LLM implementation for Backdoor.
Adapted from OpenHands with modifications for Backdoor Flask app.
"""
import copy
import json
import os
import time
import warnings
from functools import partial
from typing import Any, Callable, Dict, List, Optional, Union

import httpx
import tenacity
from flask import current_app, session

from app.backdoor.core.config import LLMConfig
from app.backdoor.core.exceptions import (
    LLMInvalidRequestError,
    LLMNoResponseError,
    LLMRateLimitError,
    LLMTimeoutError,
)
from app.backdoor.core.logger import get_logger

# Import litellm with warnings suppressed
with warnings.catch_warnings():
    warnings.simplefilter('ignore')
    import litellm

logger = get_logger("llm.together")

# Models that support function calling
FUNCTION_CALLING_SUPPORTED_MODELS = [
    'claude-3-7-sonnet-20250219',
    'claude-3-5-sonnet',
    'claude-3-5-sonnet-20240620',
    'claude-3-5-sonnet-20241022',
    'claude-3.5-haiku',
    'claude-3-5-haiku-20241022',
    'gpt-4o-mini',
    'gpt-4o',
    'o1-2024-12-17',
    'o3-mini-2025-01-31',
    'o3-mini',
    'o3',
    'o3-2025-04-16',
    'o4-mini',
    'o4-mini-2025-04-16',
    'gemini-2.5-pro',
    'gpt-4.1',
    'meta-llama/Llama-3.3-70B-Instruct-Turbo-Free',
]

# Models that support reasoning effort
REASONING_EFFORT_SUPPORTED_MODELS = [
    'o1-2024-12-17',
    'o1',
    'o3',
    'o3-2025-04-16',
    'o3-mini-2025-01-31',
    'o3-mini',
    'o4-mini',
    'o4-mini-2025-04-16',
]

# Models that don't support stop words
MODELS_WITHOUT_STOP_WORDS = [
    'o1-mini',
    'o1-preview',
    'o1',
    'o1-2024-12-17',
]

# Stop words for function calling
STOP_WORDS = [
    "
    "