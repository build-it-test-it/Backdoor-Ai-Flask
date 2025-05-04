"""
Logger module for Backdoor.
Adapted from OpenHands with modifications for Backdoor Flask app.
"""
import logging
import os
import sys
from typing import Optional

# Define log levels
DEBUG = logging.DEBUG
INFO = logging.INFO
WARNING = logging.WARNING
ERROR = logging.ERROR
CRITICAL = logging.CRITICAL

# Custom log levels
DEBUG_RUNTIME = 15
DEBUG_AGENT = 16
DEBUG_LLM = 17

# Register custom log levels
logging.addLevelName(DEBUG_RUNTIME, "DEBUG_RUNTIME")
logging.addLevelName(DEBUG_AGENT, "DEBUG_AGENT")
logging.addLevelName(DEBUG_LLM, "DEBUG_LLM")

class BackdoorLogger(logging.Logger):
    """Custom logger for Backdoor."""
    
    def __init__(self, name: str, level: int = logging.INFO):
        super().__init__(name, level)
        self.setup_handlers()
        
    def setup_handlers(self):
        """Set up handlers for the logger."""
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        ))
        self.addHandler(console_handler)
        
        # File handler
        log_dir = os.path.join('/tmp', 'backdoor', 'logs')
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, 'backdoor.log')
        
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        ))
        self.addHandler(file_handler)
    
    def debug_runtime(self, msg, *args, **kwargs):
        """Log a message with DEBUG_RUNTIME level."""
        self.log(DEBUG_RUNTIME, msg, *args, **kwargs)
    
    def debug_agent(self, msg, *args, **kwargs):
        """Log a message with DEBUG_AGENT level."""
        self.log(DEBUG_AGENT, msg, *args, **kwargs)
    
    def debug_llm(self, msg, *args, **kwargs):
        """Log a message with DEBUG_LLM level."""
        self.log(DEBUG_LLM, msg, *args, **kwargs)

# Create and configure the logger
logging.setLoggerClass(BackdoorLogger)
backdoor_logger = logging.getLogger("backdoor")

# Set log level from environment variable
log_level_str = os.environ.get("MCP_LOG_LEVEL", "INFO")
log_level_map = {
    "DEBUG": DEBUG,
    "INFO": INFO,
    "WARNING": WARNING,
    "ERROR": ERROR,
    "CRITICAL": CRITICAL
}
backdoor_logger.setLevel(log_level_map.get(log_level_str, INFO))

def get_logger(name: Optional[str] = None) -> BackdoorLogger:
    """Get a logger instance.
    
    Args:
        name: The name of the logger. If None, returns the root logger.
        
    Returns:
        A logger instance.
    """
    if name:
        return logging.getLogger(f"backdoor.{name}")
    return backdoor_logger