"""
Backdoor module for AI agent functionality.
"""
from app.backdoor.core.config import AppConfig, get_config
from app.backdoor.core.logger import get_logger

__version__ = "1.0.0"

# Initialize logger
logger = get_logger()
logger.info(f"Backdoor v{__version__} initialized")

# Get configuration
config = get_config()

__all__ = [
    "AppConfig",
    "get_config",
    "get_logger",
    "config",
    "logger",
]