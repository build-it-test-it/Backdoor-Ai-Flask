"""
API routes for Backdoor agent.
"""
import json
import os
import uuid
from flask import Blueprint, jsonify, request, session, current_app
from typing import Dict, Any, Optional, List

from app.backdoor.core.config import get_config
from app.backdoor.core.logger import get_logger
from app.backdoor.agenthub import CodeActAgent
from app.backdoor.llm import TogetherClient, MultiProviderLLMClient

bp = Blueprint('backdoor_api', __name__, url_prefix='/api/backdoor')
logger = get_logger("routes.backdoor_api")

# Store agents and LLM clients by session ID
agents: Dict[str, CodeActAgent] = {}
llm_clients: Dict[str, MultiProviderLLMClient] = {}

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

def get_llm_client(session_id: Optional[str] = None) -> MultiProviderLLMClient:
    """Get or create an LLM client for the session.
    
    Args:
        session_id: The session ID. If None, use the current session ID.
        
    Returns:
        The LLM client.
    """
    if session_id is None:
        session_id = get_session_id()
    
    if session_id not in llm_clients:
        # Create a new LLM client
        config = get_config()
        llm_clients[session_id] = MultiProviderLLMClient(config)
    
    return llm_clients[session_id]

def get_agent(session_id: Optional[str] = None) -> CodeActAgent:
    """Get or create an agent for the session.
    
    Args:
        session_id: The session ID. If None, use the current session ID.
        
    Returns:
        The agent.
    """
    if session_id is None:
        session_id = get_session_id()
    
    if session_id not in agents:
        # Create a new agent
        config = get_config()
        agents[session_id] = CodeActAgent(config, session_id=session_id)
    
    return agents[session_id]

@bp.route('/status', methods=['GET'])
def status():
    """Get the status of the Backdoor agent."""
    try:
        agent = get_agent()
        status = agent.get_status()
        
        return jsonify({
            "status": "success",
            "agent": status
        })
    except Exception as e:
        logger.error(f"Error getting agent status: {e}")
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500

@bp.route('/initialize', methods=['POST'])
def initialize():
    """Initialize the Backdoor agent."""
    try:
        data = request.json or {}
        
        # Get LLM configuration
        provider = data.get('provider')
        api_key = data.get('api_key')
        model = data.get('model')
        api_base = data.get('api_base')
        
        # If no API key provided, use the one from app config
        if not api_key:
            if provider == 'together' or not provider:
                api_key = current_app.config.get('TOGETHER_API_KEY')
            elif provider == 'openai':
                api_key = current_app.config.get('OPENAI_API_KEY')
            elif provider == 'anthropic':
                api_key = current_app.config.get('ANTHROPIC_API_KEY')
            elif provider == 'google':
                api_key = current_app.config.get('GOOGLE_API_KEY')
            elif provider == 'mistral':
                api_key = current_app.config.get('MISTRAL_API_KEY')
            elif provider == 'cohere':
                api_key = current_app.config.get('COHERE_API_KEY')
            elif provider == 'custom':
                api_key = current_app.config.get('CUSTOM_API_KEY')
        
        # Get LLM client
        llm_client = get_llm_client()
        
        # Update LLM configuration
        llm_config = {}
        if provider:
            llm_config['provider'] = provider
        if api_key:
            llm_config['api_key'] = api_key
        if model:
            llm_config['model'] = model
        if api_base:
            llm_config['api_base'] = api_base
        
        if llm_config:
            llm_client.update_config(llm_config)
        
        # Initialize agent
        agent = get_agent()
        agent.initialize()
        
        return jsonify({
            "status": "success",
            "message": "Agent initialized successfully",
            "agent": agent.get_status(),
            "llm": {
                "provider": llm_client.provider,
                "model": llm_client.model,
                "api_base": llm_client.api_base
            }
        })
    except Exception as e:
        logger.error(f"Error initializing agent: {e}")
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500

@bp.route('/chat', methods=['POST'])
def chat():
    """Chat with the Backdoor agent."""
    try:
        data = request.json or {}
        message = data.get('message')
        
        if not message:
            return jsonify({
                "status": "error",
                "error": "Message is required"
            }), 400
        
        # Get agent
        agent = get_agent()
        
        # Process message
        response = agent.process_message(message)
        
        return jsonify({
            "status": "success",
            "response": response
        })
    except Exception as e:
        logger.error(f"Error processing message: {e}")
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500

@bp.route('/execute_tool', methods=['POST'])
def execute_tool():
    """Execute a tool."""
    try:
        data = request.json or {}
        tool_name = data.get('tool_name')
        tool_args = data.get('tool_args', {})
        
        if not tool_name:
            return jsonify({
                "status": "error",
                "error": "Tool name is required"
            }), 400
        
        # Get agent
        agent = get_agent()
        
        # Execute tool
        result = agent.execute_tool(tool_name, tool_args)
        
        return jsonify({
            "status": "success",
            "result": result
        })
    except Exception as e:
        logger.error(f"Error executing tool: {e}")
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500

@bp.route('/conversation', methods=['GET'])
def get_conversation():
    """Get the conversation history."""
    try:
        agent = get_agent()
        conversation = agent.get_conversation_history()
        
        return jsonify({
            "status": "success",
            "conversation": conversation
        })
    except Exception as e:
        logger.error(f"Error getting conversation: {e}")
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500

@bp.route('/conversation', methods=['DELETE'])
def clear_conversation():
    """Clear the conversation history."""
    try:
        agent = get_agent()
        agent.clear_conversation_history()
        
        return jsonify({
            "status": "success",
            "message": "Conversation cleared"
        })
    except Exception as e:
        logger.error(f"Error clearing conversation: {e}")
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500

@bp.route('/tools', methods=['GET'])
def get_tools():
    """Get the available tools."""
    try:
        agent = get_agent()
        tools = agent.tools
        
        return jsonify({
            "status": "success",
            "tools": tools
        })
    except Exception as e:
        logger.error(f"Error getting tools: {e}")
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500

@bp.route('/llm/providers', methods=['GET'])
def get_llm_providers():
    """Get the available LLM providers."""
    try:
        config = get_config()
        
        providers = []
        for provider_id, provider_config in config.llm.providers.items():
            # Skip custom provider if no API base is set
            if provider_id == "custom" and not provider_config.api_base:
                continue
                
            providers.append({
                "id": provider_id,
                "name": provider_config.name,
                "api_base": provider_config.api_base,
                "default_model": provider_config.default_model,
                "models_count": len(provider_config.models),
            })
        
        # Get current provider
        llm_client = get_llm_client()
        
        return jsonify({
            "status": "success",
            "providers": providers,
            "current_provider": llm_client.provider
        })
    except Exception as e:
        logger.error(f"Error getting LLM providers: {e}")
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500

@bp.route('/llm/models', methods=['GET'])
def get_llm_models():
    """Get the available LLM models."""
    try:
        # Get provider from query params
        provider = request.args.get('provider')
        
        # Get LLM client
        llm_client = get_llm_client()
        
        # Get models
        if provider:
            # Get models for specific provider
            config = get_config()
            if provider in config.llm.providers:
                provider_config = config.llm.providers[provider]
                models = [
                    {
                        "id": model_id,
                        "provider": provider,
                        "provider_name": provider_config.name,
                        "default": model_id == provider_config.default_model
                    }
                    for model_id in provider_config.models
                ]
            else:
                models = []
        else:
            # Get models from all providers
            models = llm_client.get_available_models()
        
        return jsonify({
            "status": "success",
            "models": models,
            "current_model": llm_client.model,
            "current_provider": llm_client.provider
        })
    except Exception as e:
        logger.error(f"Error getting LLM models: {e}")
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500

@bp.route('/llm/config', methods=['GET'])
def get_llm_config():
    """Get the LLM configuration."""
    try:
        # Get LLM client
        llm_client = get_llm_client()
        
        return jsonify({
            "status": "success",
            "config": {
                "provider": llm_client.provider,
                "model": llm_client.model,
                "api_base": llm_client.api_base,
                "temperature": llm_client.llm_config.temperature,
                "max_tokens": llm_client.llm_config.max_tokens,
                "top_p": llm_client.llm_config.top_p,
                "frequency_penalty": llm_client.llm_config.frequency_penalty,
                "presence_penalty": llm_client.llm_config.presence_penalty,
                "timeout": llm_client.llm_config.timeout
            }
        })
    except Exception as e:
        logger.error(f"Error getting LLM config: {e}")
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500

@bp.route('/llm/config', methods=['POST'])
def update_llm_config():
    """Update the LLM configuration."""
    try:
        data = request.json or {}
        
        if not data:
            return jsonify({
                "status": "error",
                "error": "No data provided"
            }), 400
        
        # Get LLM client
        llm_client = get_llm_client()
        
        # Update config
        llm_client.update_config(data)
        
        return jsonify({
            "status": "success",
            "message": "LLM configuration updated successfully",
            "config": {
                "provider": llm_client.provider,
                "model": llm_client.model,
                "api_base": llm_client.api_base,
                "temperature": llm_client.llm_config.temperature,
                "max_tokens": llm_client.llm_config.max_tokens,
                "top_p": llm_client.llm_config.top_p,
                "frequency_penalty": llm_client.llm_config.frequency_penalty,
                "presence_penalty": llm_client.llm_config.presence_penalty,
                "timeout": llm_client.llm_config.timeout
            }
        })
    except Exception as e:
        logger.error(f"Error updating LLM config: {e}")
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500

@bp.route('/llm/test', methods=['POST'])
def test_llm():
    """Test the LLM configuration."""
    try:
        data = request.json or {}
        
        # Get LLM client
        llm_client = get_llm_client()
        
        # Update config if provided
        if "config" in data:
            llm_client.update_config(data["config"])
        
        # Create test message
        messages = data.get("messages", [
            {"role": "system", "content": "You are a helpful AI assistant."},
            {"role": "user", "content": "Say hello and introduce yourself briefly."}
        ])
        
        # Call LLM
        response = llm_client.completion(
            messages=messages,
            temperature=data.get("temperature", 0.7),
            max_tokens=data.get("max_tokens", 100),
        )
        
        # Extract response
        content = response["choices"][0]["message"]["content"]
        
        return jsonify({
            "status": "success",
            "content": content,
            "provider": llm_client.provider,
            "model": llm_client.model,
            "message": "LLM test successful"
        })
    except Exception as e:
        logger.error(f"Error testing LLM: {e}")
        
        return jsonify({
            "status": "error",
            "error": str(e),
            "provider": llm_client.provider if 'llm_client' in locals() else None,
            "model": llm_client.model if 'llm_client' in locals() else None,
            "message": "LLM test failed"
        }), 500

@bp.route('/runtime/status', methods=['GET'])
def runtime_status():
    """Get the runtime status."""
    try:
        agent = get_agent()
        
        if not agent.runtime:
            return jsonify({
                "status": "error",
                "error": "Runtime not available"
            }), 404
        
        status = agent.runtime.get_status()
        
        return jsonify({
            "status": "success",
            "runtime": status
        })
    except Exception as e:
        logger.error(f"Error getting runtime status: {e}")
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500

@bp.route('/runtime/logs', methods=['GET'])
def runtime_logs():
    """Get the runtime logs."""
    try:
        agent = get_agent()
        
        if not agent.runtime:
            return jsonify({
                "status": "error",
                "error": "Runtime not available"
            }), 404
        
        tail = request.args.get('tail', 100, type=int)
        logs = agent.runtime.get_logs(tail=tail)
        
        return jsonify({
            "status": "success",
            "logs": logs
        })
    except Exception as e:
        logger.error(f"Error getting runtime logs: {e}")
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500

@bp.route('/runtime/restart', methods=['POST'])
def restart_runtime():
    """Restart the runtime."""
    try:
        agent = get_agent()
        
        if not agent.runtime:
            return jsonify({
                "status": "error",
                "error": "Runtime not available"
            }), 404
        
        agent.runtime.restart()
        
        return jsonify({
            "status": "success",
            "message": "Runtime restarted"
        })
    except Exception as e:
        logger.error(f"Error restarting runtime: {e}")
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500