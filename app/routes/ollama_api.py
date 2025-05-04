"""
API routes for managing Ollama LLM.
"""
import json
import os
import uuid
from flask import Blueprint, jsonify, request, session, current_app
from typing import Dict, Any, Optional, List

from app.backdoor.core.config import get_config
from app.backdoor.core.logger import get_logger
from app.backdoor.llm.ollama_client import OllamaClient
from app.backdoor.llm.ollama_helper import ollama_helper

bp = Blueprint('ollama_api', __name__, url_prefix='/api/ollama')
logger = get_logger("routes.ollama_api")

# Store Ollama clients by session ID
ollama_clients: Dict[str, OllamaClient] = {}

def get_session_id() -> str:
    """Get the session ID from the request.
    
    Returns:
        The session ID.
    """
    session_id = session.get('session_id')
    if not session_id:
        session_id = str(uuid.uuid4())
        session['session_id'] = session_id
    
    return session_id

def get_ollama_client(session_id: Optional[str] = None) -> OllamaClient:
    """Get or create an Ollama client for the session.
    
    Args:
        session_id: The session ID. If None, use the current session ID.
        
    Returns:
        The Ollama client.
    """
    if session_id is None:
        session_id = get_session_id()
    
    if session_id not in ollama_clients:
        # Create a new Ollama client
        api_base = os.environ.get("OLLAMA_API_BASE", "http://localhost:11434")
        model = os.environ.get("OLLAMA_MODEL", "llama4:latest")
        ollama_clients[session_id] = OllamaClient(model=model, api_base=api_base)
    
    return ollama_clients[session_id]

@bp.route('/status', methods=['GET'])
def get_status():
    """Get Ollama status.
    
    Returns:
        The status of Ollama.
    """
    try:
        client = get_ollama_client()
        helper = ollama_helper
        
        is_installed = helper.is_installed()
        is_running = helper.is_running()
        
        return jsonify({
            "status": "success",
            "is_installed": is_installed,
            "is_running": is_running,
            "client_status": client.get_status()
        })
    except Exception as e:
        logger.error(f"Error getting Ollama status: {e}")
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500

@bp.route('/install', methods=['POST'])
def install_ollama():
    """Install Ollama.
    
    Returns:
        The result of the installation.
    """
    try:
        helper = ollama_helper
        
        if helper.is_installed():
            return jsonify({
                "status": "success",
                "message": "Ollama is already installed",
                "installed": True
            })
        
        installed = helper.install()
        
        if installed:
            return jsonify({
                "status": "success",
                "message": "Ollama installed successfully",
                "installed": True
            })
        else:
            instructions = helper.get_installation_instructions()
            return jsonify({
                "status": "warning",
                "message": "Automatic installation failed. Please install Ollama manually.",
                "instructions": instructions,
                "installed": False
            })
    except Exception as e:
        logger.error(f"Error installing Ollama: {e}")
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500

@bp.route('/start', methods=['POST'])
def start_ollama():
    """Start Ollama server.
    
    Returns:
        The result of starting Ollama.
    """
    try:
        helper = ollama_helper
        
        if not helper.is_installed():
            return jsonify({
                "status": "error",
                "message": "Ollama is not installed",
                "instructions": helper.get_installation_instructions()
            }), 400
        
        if helper.is_running():
            return jsonify({
                "status": "success",
                "message": "Ollama is already running",
                "running": True
            })
        
        started = helper.start()
        
        if started:
            return jsonify({
                "status": "success",
                "message": "Ollama started successfully",
                "running": True
            })
        else:
            return jsonify({
                "status": "error",
                "message": "Failed to start Ollama",
                "running": False
            }), 500
    except Exception as e:
        logger.error(f"Error starting Ollama: {e}")
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500

@bp.route('/models', methods=['GET'])
def get_models():
    """Get available Ollama models.
    
    Returns:
        List of available models.
    """
    try:
        helper = ollama_helper
        
        if not helper.is_installed():
            return jsonify({
                "status": "error",
                "message": "Ollama is not installed",
                "instructions": helper.get_installation_instructions()
            }), 400
        
        if not helper.is_running():
            started = helper.start()
            if not started:
                return jsonify({
                    "status": "error",
                    "message": "Failed to start Ollama",
                    "running": False
                }), 500
        
        models = helper.list_models()
        
        # Add recommended models if not already in the list
        recommended_models = [
            "llama4:latest", 
            "llama4-8b:latest", 
            "llama4-code:latest",
            "llama4-tiny:latest",
            "mistral:latest",
            "gemma:latest"
        ]
        
        model_ids = [model["id"] for model in models]
        
        for rec_model in recommended_models:
            if rec_model not in model_ids:
                models.append({
                    "id": rec_model,
                    "name": rec_model,
                    "size": None,
                    "modified_at": None,
                    "installed": False,
                    "provider": "ollama",
                    "recommended": True
                })
        
        return jsonify({
            "status": "success",
            "models": models
        })
    except Exception as e:
        logger.error(f"Error getting models: {e}")
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500

@bp.route('/models/<model>', methods=['POST'])
def pull_model(model):
    """Pull an Ollama model.
    
    Args:
        model: The model to pull.
        
    Returns:
        The result of pulling the model.
    """
    try:
        helper = ollama_helper
        
        if not helper.is_installed():
            return jsonify({
                "status": "error",
                "message": "Ollama is not installed",
                "instructions": helper.get_installation_instructions()
            }), 400
        
        if not helper.is_running():
            started = helper.start()
            if not started:
                return jsonify({
                    "status": "error",
                    "message": "Failed to start Ollama",
                    "running": False
                }), 500
        
        # Pull the model
        pulled = helper.pull_model(model)
        
        if pulled:
            return jsonify({
                "status": "success",
                "message": f"Model {model} pulled successfully",
                "model": model
            })
        else:
            return jsonify({
                "status": "error",
                "message": f"Failed to pull model {model}",
                "model": model
            }), 500
    except Exception as e:
        logger.error(f"Error pulling model: {e}")
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500

@bp.route('/test', methods=['POST'])
def test_model():
    """Test an Ollama model.
    
    Returns:
        The result of testing the model.
    """
    try:
        data = request.json or {}
        model = data.get("model", "llama4:latest")
        prompt = data.get("prompt", "Hello, I'm testing the Ollama LLM. Please respond with a short greeting.")
        
        helper = ollama_helper
        
        # Ensure model is available
        if not helper.ensure_model_available(model):
            return jsonify({
                "status": "error",
                "message": f"Failed to ensure model {model} is available"
            }), 500
        
        # Get Ollama client
        client = get_ollama_client()
        client.set_model(model)
        
        # Create test message
        messages = [
            {"role": "user", "content": prompt}
        ]
        
        # Call Ollama
        response = client.generate(
            messages=messages,
            model=model,
            temperature=data.get("temperature", 0.7),
            max_tokens=data.get("max_tokens", 100),
        )
        
        # Extract response
        content = response["choices"][0]["message"]["content"]
        
        return jsonify({
            "status": "success",
            "content": content,
            "model": model,
            "message": "Ollama test successful"
        })
    except Exception as e:
        logger.error(f"Error testing Ollama: {e}")
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500

@bp.route('/config', methods=['GET'])
def get_config():
    """Get Ollama configuration.
    
    Returns:
        The current Ollama configuration.
    """
    try:
        client = get_ollama_client()
        
        return jsonify({
            "status": "success",
            "config": {
                "model": client.get_model(),
                "api_base": client.get_api_base()
            }
        })
    except Exception as e:
        logger.error(f"Error getting Ollama config: {e}")
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500

@bp.route('/config', methods=['POST'])
def update_config():
    """Update Ollama configuration.
    
    Returns:
        The updated Ollama configuration.
    """
    try:
        data = request.json or {}
        client = get_ollama_client()
        
        if "model" in data:
            client.set_model(data["model"])
        
        if "api_base" in data:
            client.set_api_base(data["api_base"])
        
        return jsonify({
            "status": "success",
            "message": "Ollama configuration updated",
            "config": {
                "model": client.get_model(),
                "api_base": client.get_api_base()
            }
        })
    except Exception as e:
        logger.error(f"Error updating Ollama config: {e}")
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500
