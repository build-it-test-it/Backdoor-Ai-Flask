"""
Enhanced Agent Handler for Backdoor AI

This module provides an improved agent handling system based on the Mentat codebase.
It implements a more sophisticated approach to agent management, context handling,
and command execution.

Features:
- Better context management
- Improved command execution
- Enhanced agent autonomy
"""

import os
import json
import logging
import shlex
import subprocess
import asyncio
import uuid
from pathlib import Path
from typing import Dict, List, Any, Optional, Union, Tuple, Set
from datetime import datetime

from flask import current_app

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("enhanced_agent_handler")

class CodeFeature:
    """
    Represents a code feature (file or directory) in the codebase.
    Based on Mentat's code_feature.py.
    """
    
    def __init__(self, path: Path, content: Optional[str] = None):
        self.path = path
        self.content = content
        self.is_directory = path.is_dir() if path.exists() else False
        self.size = path.stat().st_size if path.exists() and not self.is_directory else 0
        self.last_modified = datetime.fromtimestamp(path.stat().st_mtime) if path.exists() else datetime.now()
    
    def load_content(self) -> str:
        """Load the content of the file if not already loaded."""
        if self.content is None and not self.is_directory and self.path.exists():
            try:
                with open(self.path, 'r', encoding='utf-8', errors='replace') as f:
                    self.content = f.read()
            except Exception as e:
                logger.error(f"Error loading content for {self.path}: {e}")
                self.content = f"Error loading content: {str(e)}"
        
        return self.content or ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'path': str(self.path),
            'is_directory': self.is_directory,
            'size': self.size,
            'last_modified': self.last_modified.isoformat(),
            'content': self.content if not self.is_directory else None
        }

class CodeContext:
    """
    Manages code context for agents.
    Based on Mentat's code_context.py.
    """
    
    def __init__(self, base_path: Path):
        self.base_path = base_path
        self.features: Dict[str, CodeFeature] = {}
        self.ignored_patterns: List[str] = [
            '.git', '.github', '__pycache__', '*.pyc', '*.pyo', '*.pyd',
            '.DS_Store', '.env', '.venv', 'env', 'venv', 'ENV', 'env.bak',
            'venv.bak', '.idea', '.vscode', '*.so', '*.dylib', '*.dll',
            'node_modules', 'bower_components', '.pytest_cache', '.coverage',
            'htmlcov', '.tox', '.nox', '.hypothesis', '.egg-info', 'dist',
            'build', '*.egg', '*.whl', '*.log'
        ]
    
    def is_ignored(self, path: Path) -> bool:
        """Check if a path should be ignored."""
        import fnmatch
        
        # Convert to relative path for pattern matching
        rel_path = path.relative_to(self.base_path) if path.is_absolute() else path
        rel_path_str = str(rel_path)
        
        # Check against ignored patterns
        for pattern in self.ignored_patterns:
            if fnmatch.fnmatch(rel_path_str, pattern) or fnmatch.fnmatch(rel_path.name, pattern):
                return True
        
        return False
    
    def add_feature(self, path: Path) -> Optional[CodeFeature]:
        """Add a file or directory to the context."""
        # Normalize path
        if not path.is_absolute():
            path = self.base_path / path
        
        # Check if path exists
        if not path.exists():
            logger.warning(f"Path does not exist: {path}")
            return None
        
        # Check if path should be ignored
        if self.is_ignored(path):
            logger.info(f"Path ignored: {path}")
            return None
        
        # Create feature
        feature = CodeFeature(path)
        
        # Load content for files
        if not feature.is_directory:
            feature.load_content()
        
        # Add to features
        self.features[str(path)] = feature
        
        return feature
    
    def add_directory(self, path: Path, recursive: bool = True, max_depth: int = 3) -> List[CodeFeature]:
        """Add a directory and its contents to the context."""
        # Normalize path
        if not path.is_absolute():
            path = self.base_path / path
        
        # Check if path exists and is a directory
        if not path.exists() or not path.is_dir():
            logger.warning(f"Path does not exist or is not a directory: {path}")
            return []
        
        # Check if path should be ignored
        if self.is_ignored(path):
            logger.info(f"Path ignored: {path}")
            return []
        
        # Add the directory itself
        self.add_feature(path)
        
        added_features = []
        
        # Add contents
        if recursive:
            self._add_directory_recursive(path, added_features, 0, max_depth)
        else:
            for item in path.iterdir():
                if not self.is_ignored(item):
                    feature = self.add_feature(item)
                    if feature:
                        added_features.append(feature)
        
        return added_features
    
    def _add_directory_recursive(self, path: Path, added_features: List[CodeFeature], 
                               current_depth: int, max_depth: int) -> None:
        """Recursively add directory contents to the context."""
        if current_depth > max_depth:
            return
        
        for item in path.iterdir():
            if self.is_ignored(item):
                continue
            
            feature = self.add_feature(item)
            if feature:
                added_features.append(feature)
            
            if item.is_dir():
                self._add_directory_recursive(item, added_features, current_depth + 1, max_depth)
    
    def remove_feature(self, path: Path) -> bool:
        """Remove a feature from the context."""
        # Normalize path
        if not path.is_absolute():
            path = self.base_path / path
        
        path_str = str(path)
        
        if path_str in self.features:
            del self.features[path_str]
            return True
        
        return False
    
    def get_feature(self, path: Path) -> Optional[CodeFeature]:
        """Get a feature from the context."""
        # Normalize path
        if not path.is_absolute():
            path = self.base_path / path
        
        return self.features.get(str(path))
    
    def get_all_features(self) -> List[CodeFeature]:
        """Get all features in the context."""
        return list(self.features.values())
    
    def get_file_content(self, path: Path) -> Optional[str]:
        """Get the content of a file."""
        feature = self.get_feature(path)
        if feature and not feature.is_directory:
            return feature.load_content()
        
        return None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'base_path': str(self.base_path),
            'features': {path: feature.to_dict() for path, feature in self.features.items()},
            'ignored_patterns': self.ignored_patterns
        }

class EnhancedAgentHandler:
    """
    Enhanced Agent Handler for Backdoor AI.
    Based on Mentat's agent_handler.py.
    """
    
    def __init__(self, agent_id: str, base_path: Path):
        self.agent_id = agent_id
        self.base_path = base_path
        self.code_context = CodeContext(base_path)
        self.agent_enabled = False
        self.agent_file_message = ""
        self.command_history: List[str] = []
        self.last_command_result: Dict[str, Any] = {}
        
        # Load prompts
        self.agent_file_selection_prompt = self._load_prompt("agent_file_selection_prompt.txt")
        self.agent_command_prompt = self._load_prompt("agent_command_selection_prompt.txt")
        
        # Create agent directory
        self.agent_dir = Path('/tmp/backdoor/agents') / agent_id
        os.makedirs(self.agent_dir, exist_ok=True)
    
    def _load_prompt(self, prompt_name: str) -> str:
        """Load a prompt from the prompts directory."""
        # First check if the prompt exists in the app's prompts directory
        app_prompt_path = Path(current_app.root_path) / 'ai' / 'prompts' / prompt_name
        if app_prompt_path.exists():
            with open(app_prompt_path, 'r') as f:
                return f.read()
        
        # If not, use a default prompt
        if prompt_name == "agent_file_selection_prompt.txt":
            return """You are an AI assistant that helps select relevant files for understanding a codebase.
Given a list of files in a repository, select the most important files that would help understand:
1. The overall structure of the codebase
2. How to test changes to the code
3. Key functionality and data models

Return ONLY a list of file paths, one per line, with no additional text or explanation.
"""
        
        elif prompt_name == "agent_command_selection_prompt.txt":
            return """You are an AI assistant that helps determine which commands to run to test code changes.
Based on the files you've examined, suggest commands that would:
1. Run tests relevant to the changes
2. Verify that the application still works correctly
3. Check for any regressions or issues

Return ONLY a list of commands, one per line, with no additional text or explanation.
"""
        
        # Default empty prompt
        return ""
    
    def enable_agent_mode(self) -> Dict[str, Any]:
        """Enable agent mode and select relevant files for context."""
        if self.agent_enabled:
            return {
                "success": True,
                "message": "Agent mode already enabled"
            }
        
        try:
            # Scan the repository for files
            self._scan_repository()
            
            # Get all features
            features = self.code_context.get_all_features()
            
            # Select relevant files using LLM
            from app.ai.model_service import model_service
            
            # Prepare the prompt
            prompt = self.agent_file_selection_prompt
            file_list = "\n".join(str(feature.path.relative_to(self.base_path)) 
                                for feature in features if not feature.is_directory)
            
            # Call the LLM
            response = model_service.generate_text(
                prompt + "\n\n" + file_list,
                temperature=0.2,
                max_tokens=1000
            )
            
            # Parse the response
            selected_files = [line.strip() for line in response.strip().split("\n") if line.strip()]
            
            # Load the selected files
            self.agent_file_message = ""
            loaded_files = []
            
            for file_path in selected_files:
                path = self.base_path / file_path
                if path.exists() and not path.is_dir():
                    content = self.code_context.get_file_content(path)
                    if content:
                        self.agent_file_message += f"{file_path}\n\n{content}\n\n"
                        loaded_files.append(file_path)
            
            # Enable agent mode
            self.agent_enabled = True
            
            return {
                "success": True,
                "message": "Agent mode enabled",
                "selected_files": loaded_files
            }
        
        except Exception as e:
            logger.error(f"Error enabling agent mode: {e}")
            return {
                "success": False,
                "error": f"Failed to enable agent mode: {str(e)}"
            }
    
    def disable_agent_mode(self) -> Dict[str, Any]:
        """Disable agent mode."""
        if not self.agent_enabled:
            return {
                "success": True,
                "message": "Agent mode already disabled"
            }
        
        self.agent_enabled = False
        self.agent_file_message = ""
        
        return {
            "success": True,
            "message": "Agent mode disabled"
        }
    
    def _scan_repository(self) -> None:
        """Scan the repository for files."""
        # Clear existing features
        self.code_context.features = {}
        
        # Add the base directory
        self.code_context.add_directory(self.base_path, recursive=True, max_depth=5)
    
    def determine_commands(self) -> Dict[str, Any]:
        """Determine commands to run based on the context."""
        if not self.agent_enabled:
            return {
                "success": False,
                "error": "Agent mode not enabled"
            }
        
        try:
            # Prepare the prompt
            prompt = self.agent_command_prompt + "\n\n" + self.agent_file_message
            
            # Call the LLM
            from app.ai.model_service import model_service
            
            response = model_service.generate_text(
                prompt,
                temperature=0.3,
                max_tokens=1000
            )
            
            # Parse the response
            commands = [line.strip() for line in response.strip().split("\n") if line.strip()]
            
            return {
                "success": True,
                "commands": commands
            }
        
        except Exception as e:
            logger.error(f"Error determining commands: {e}")
            return {
                "success": False,
                "error": f"Failed to determine commands: {str(e)}"
            }
    
    async def execute_command(self, command: str) -> Dict[str, Any]:
        """Execute a command in the repository."""
        try:
            # Add to command history
            self.command_history.append(command)
            
            # Execute the command
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self.base_path)
            )
            
            stdout, stderr = await process.communicate()
            
            # Store the result
            result = {
                "command": command,
                "exit_code": process.returncode,
                "stdout": stdout.decode('utf-8', errors='replace'),
                "stderr": stderr.decode('utf-8', errors='replace'),
                "timestamp": datetime.now().isoformat()
            }
            
            self.last_command_result = result
            
            return {
                "success": True,
                "result": result
            }
        
        except Exception as e:
            logger.error(f"Error executing command: {e}")
            return {
                "success": False,
                "error": f"Failed to execute command: {str(e)}"
            }
    
    async def run_commands(self, commands: List[str]) -> Dict[str, Any]:
        """Run a list of commands in sequence."""
        results = []
        
        for command in commands:
            result = await self.execute_command(command)
            results.append(result)
            
            # Stop if a command fails
            if not result.get("success", False) or result.get("result", {}).get("exit_code", 0) != 0:
                break
        
        return {
            "success": True,
            "results": results
        }
    
    def get_context_summary(self) -> Dict[str, Any]:
        """Get a summary of the current context."""
        features = self.code_context.get_all_features()
        
        file_count = sum(1 for f in features if not f.is_directory)
        dir_count = sum(1 for f in features if f.is_directory)
        
        return {
            "success": True,
            "agent_enabled": self.agent_enabled,
            "file_count": file_count,
            "directory_count": dir_count,
            "base_path": str(self.base_path),
            "command_history_length": len(self.command_history)
        }
    
    def get_file_content(self, path: str) -> Dict[str, Any]:
        """Get the content of a file in the context."""
        try:
            file_path = Path(path)
            if not file_path.is_absolute():
                file_path = self.base_path / file_path
            
            content = self.code_context.get_file_content(file_path)
            
            if content is None:
                return {
                    "success": False,
                    "error": "File not found in context"
                }
            
            return {
                "success": True,
                "path": str(file_path),
                "content": content
            }
        
        except Exception as e:
            logger.error(f"Error getting file content: {e}")
            return {
                "success": False,
                "error": f"Failed to get file content: {str(e)}"
            }
    
    def add_file_to_context(self, path: str) -> Dict[str, Any]:
        """Add a file to the context."""
        try:
            file_path = Path(path)
            if not file_path.is_absolute():
                file_path = self.base_path / file_path
            
            feature = self.code_context.add_feature(file_path)
            
            if feature is None:
                return {
                    "success": False,
                    "error": "Failed to add file to context"
                }
            
            return {
                "success": True,
                "path": str(file_path),
                "is_directory": feature.is_directory
            }
        
        except Exception as e:
            logger.error(f"Error adding file to context: {e}")
            return {
                "success": False,
                "error": f"Failed to add file to context: {str(e)}"
            }
    
    def remove_file_from_context(self, path: str) -> Dict[str, Any]:
        """Remove a file from the context."""
        try:
            file_path = Path(path)
            if not file_path.is_absolute():
                file_path = self.base_path / file_path
            
            success = self.code_context.remove_feature(file_path)
            
            if not success:
                return {
                    "success": False,
                    "error": "File not found in context"
                }
            
            return {
                "success": True,
                "path": str(file_path)
            }
        
        except Exception as e:
            logger.error(f"Error removing file from context: {e}")
            return {
                "success": False,
                "error": f"Failed to remove file from context: {str(e)}"
            }
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'agent_id': self.agent_id,
            'base_path': str(self.base_path),
            'agent_enabled': self.agent_enabled,
            'command_history': self.command_history,
            'last_command_result': self.last_command_result
        }

# Dictionary to store agent handlers
agent_handlers: Dict[str, EnhancedAgentHandler] = {}