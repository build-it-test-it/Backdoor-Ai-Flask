"""
Ollama helper module for installing and managing Ollama.
"""
import os
import platform
import subprocess
import time
import requests
from typing import List, Dict, Any, Optional, Tuple

from app.backdoor.core.logger import get_logger

logger = get_logger("llm.ollama_helper")

class OllamaHelper:
    """Helper class for installing and managing Ollama."""
    
    DEFAULT_API_BASE = "http://localhost:11434"
    
    def __init__(self, api_base: str = DEFAULT_API_BASE):
        """Initialize the Ollama helper.
        
        Args:
            api_base: The base URL for the Ollama API.
        """
        self.api_base = api_base
    
    def is_installed(self) -> bool:
        """Check if Ollama is installed.
        
        Returns:
            True if Ollama is installed, False otherwise.
        """
        try:
            # Try to run ollama command to check if it's installed
            if platform.system() == "Windows":
                result = subprocess.run(
                    ["where", "ollama"], 
                    stdout=subprocess.PIPE, 
                    stderr=subprocess.PIPE, 
                    text=True,
                    check=False
                )
            else:
                result = subprocess.run(
                    ["which", "ollama"], 
                    stdout=subprocess.PIPE, 
                    stderr=subprocess.PIPE, 
                    text=True,
                    check=False
                )
            
            return result.returncode == 0
        except Exception as e:
            logger.error(f"Error checking if Ollama is installed: {e}")
            return False
    
    def is_running(self) -> bool:
        """Check if Ollama is running.
        
        Returns:
            True if Ollama is running, False otherwise.
        """
        try:
            response = requests.get(f"{self.api_base}/api/tags", timeout=2)
            return response.status_code == 200
        except Exception:
            return False
    
    def install(self) -> bool:
        """Install Ollama.
        
        Returns:
            True if installation was successful, False otherwise.
        """
        try:
            system = platform.system()
            
            if system == "Linux":
                # Install Ollama on Linux
                logger.info("Installing Ollama on Linux...")
                process = subprocess.run(
                    ["curl", "-fsSL", "https://ollama.com/install.sh", "|", "sh"],
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    check=False
                )
                
                if process.returncode != 0:
                    logger.error(f"Error installing Ollama: {process.stderr}")
                    return False
                
                logger.info("Ollama installed successfully on Linux")
                return True
                
            elif system == "Darwin":  # macOS
                logger.info("Please install Ollama on macOS using:")
                logger.info("brew install ollama")
                logger.info("Or download from https://ollama.com/download")
                return False
                
            elif system == "Windows":
                logger.info("Please install Ollama on Windows by downloading from:")
                logger.info("https://ollama.com/download")
                return False
                
            else:
                logger.error(f"Unsupported platform: {system}")
                return False
                
        except Exception as e:
            logger.error(f"Error installing Ollama: {e}")
            return False
    
    def start(self) -> bool:
        """Start the Ollama server.
        
        Returns:
            True if the server was started successfully, False otherwise.
        """
        try:
            if self.is_running():
                logger.info("Ollama is already running")
                return True
            
            logger.info("Starting Ollama server...")
            
            # Start Ollama server in the background
            if platform.system() == "Windows":
                # On Windows, use start to run in background
                subprocess.Popen(
                    ["start", "ollama", "serve"],
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
            else:
                # On Linux/macOS
                subprocess.Popen(
                    ["ollama", "serve"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
            
            # Wait for Ollama to start
            for _ in range(10):
                time.sleep(1)
                if self.is_running():
                    logger.info("Ollama server started successfully")
                    return True
            
            logger.error("Failed to start Ollama server")
            return False
            
        except Exception as e:
            logger.error(f"Error starting Ollama: {e}")
            return False
    
    def pull_model(self, model: str) -> bool:
        """Pull a model from Ollama.
        
        Args:
            model: The model to pull.
            
        Returns:
            True if the model was pulled successfully, False otherwise.
        """
        try:
            logger.info(f"Pulling model {model}...")
            
            # Pull the model
            process = subprocess.run(
                ["ollama", "pull", model],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False
            )
            
            if process.returncode != 0:
                logger.error(f"Error pulling model {model}: {process.stderr}")
                return False
            
            logger.info(f"Model {model} pulled successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error pulling model {model}: {e}")
            return False
    
    def list_models(self) -> List[Dict[str, Any]]:
        """List the models available locally.
        
        Returns:
            A list of models.
        """
        try:
            if not self.is_running():
                if not self.start():
                    return []
            
            response = requests.get(f"{self.api_base}/api/tags", timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                models = []
                
                for model in data.get("models", []):
                    models.append({
                        "id": model.get("name"),
                        "name": model.get("name"),
                        "size": model.get("size"),
                        "modified_at": model.get("modified_at"),
                        "installed": True,
                        "provider": "ollama"
                    })
                
                return models
            else:
                logger.error(f"Error listing models: {response.status_code} {response.text}")
                return []
        except Exception as e:
            logger.error(f"Error listing models: {e}")
            return []
    
    def ensure_model_available(self, model: str) -> bool:
        """Ensure a model is available, pulling it if necessary.
        
        Args:
            model: The model to ensure is available.
            
        Returns:
            True if the model is available, False otherwise.
        """
        try:
            # Check if Ollama is installed
            if not self.is_installed():
                logger.warning("Ollama is not installed")
                installed = self.install()
                if not installed:
                    logger.error("Failed to install Ollama")
                    return False
            
            # Check if Ollama is running
            if not self.is_running():
                started = self.start()
                if not started:
                    logger.error("Failed to start Ollama")
                    return False
            
            # Check if the model is available
            models = self.list_models()
            model_ids = [m["id"] for m in models]
            
            # Extract the model name without the tag if needed
            model_base = model.split(":")[0] if ":" in model else model
            
            if model in model_ids or model_base in model_ids:
                logger.info(f"Model {model} is already available")
                return True
            
            # Pull the model
            return self.pull_model(model)
            
        except Exception as e:
            logger.error(f"Error ensuring model {model} is available: {e}")
            return False
    
    def get_installation_instructions(self) -> str:
        """Get installation instructions for the current platform.
        
        Returns:
            Installation instructions.
        """
        system = platform.system()
        
        if system == "Linux":
            return "curl -fsSL https://ollama.com/install.sh | sh"
        elif system == "Darwin":  # macOS
            return "brew install ollama\n# Or download from https://ollama.com/download"
        elif system == "Windows":
            return "Download from https://ollama.com/download"
        else:
            return f"Unsupported platform: {system}"

# Create a singleton instance
ollama_helper = OllamaHelper()
