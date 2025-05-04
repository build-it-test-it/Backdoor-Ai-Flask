"""
Code Agent API for Backdoor AI

This module provides API routes for the Code Agent functionality in Backdoor AI.
"""

import logging
import asyncio
from flask import Blueprint, request, jsonify, current_app, session
import uuid

from app.ai.agent import Agent, AgentManager, AgentController
from app.ai.agent.code_agent import CodeAgent
from app.ai.agent.agent_config import AgentConfig
from app.ai.mcp_models import AgentRole

# Set up logging
logger = logging.getLogger("code_agent_api")

# Create blueprint
bp = Blueprint('code_agent_api', __name__, url_prefix='/api/code-agent')

# Get agent manager
from app.ai.agent.agent import agent_manager


@bp.route('/create', methods=['POST'])
def create_agent():
    """Create a new code agent."""
    data = request.json or {}
    
    # Get agent name
    name = data.get('name', 'Code Assistant')
    
    # Get session ID
    session_id = session.get('session_id')
    if not session_id:
        session_id = str(uuid.uuid4())
        session['session_id'] = session_id
    
    # Create agent config
    config = AgentConfig(
        enable_browsing=data.get('enable_browsing', True),
        enable_editor=data.get('enable_editor', True),
        enable_cmd=data.get('enable_cmd', True),
        enable_jupyter=data.get('enable_jupyter', False),
        enable_llm_editor=data.get('enable_llm_editor', False)
    )
    
    # Create the agent
    try:
        agent = agent_manager.create_agent(
            name=name,
            role=AgentRole.ASSISTANT,
            agent_class="CodeAgent",
            config=config,
            session_id=session_id
        )
        
        return jsonify({
            "success": True,
            "agent_id": agent.id,
            "name": agent.name,
            "session_id": session_id
        })
    except Exception as e:
        logger.error(f"Error creating agent: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@bp.route('/<agent_id>/chat', methods=['POST'])
def chat_with_agent(agent_id):
    """Chat with a code agent."""
    data = request.json or {}
    
    # Get the message
    message = data.get('message')
    if not message:
        return jsonify({
            "success": False,
            "error": "Message is required"
        }), 400
    
    # Get the agent
    agent = agent_manager.get_agent(agent_id)
    if not agent:
        return jsonify({
            "success": False,
            "error": f"Agent not found: {agent_id}"
        }), 404
    
    # Create controller if needed
    controller = AgentController(
        agent=agent,
        max_iterations=data.get('max_iterations', 10),
        session_id=agent.session_id
    )
    
    # Add user message to state
    controller.state['history'].append({
        "type": "message",
        "source": "user",
        "content": message,
        "timestamp": controller.state['last_action_time']
    })
    
    # Run a single step
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        continue_execution, result = loop.run_until_complete(controller.step())
        
        loop.close()
        
        return jsonify({
            "success": True,
            "result": result,
            "continue": continue_execution,
            "agent_id": agent_id
        })
    except Exception as e:
        logger.error(f"Error in agent step: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@bp.route('/<agent_id>/run', methods=['POST'])
def run_agent(agent_id):
    """Run a code agent for multiple steps."""
    data = request.json or {}
    
    # Get the agent
    agent = agent_manager.get_agent(agent_id)
    if not agent:
        return jsonify({
            "success": False,
            "error": f"Agent not found: {agent_id}"
        }), 404
    
    # Get max steps
    max_steps = data.get('max_steps', 5)
    
    # Create controller
    controller = AgentController(
        agent=agent,
        max_iterations=max_steps,
        session_id=agent.session_id
    )
    
    # Add initial message if provided
    initial_message = data.get('message')
    if initial_message:
        controller.state['history'].append({
            "type": "message",
            "source": "user",
            "content": initial_message,
            "timestamp": controller.state['last_action_time']
        })
    
    # Run the agent
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        result = loop.run_until_complete(controller.run(max_steps=max_steps))
        
        loop.close()
        
        return jsonify({
            "success": True,
            "result": result,
            "agent_id": agent_id
        })
    except Exception as e:
        logger.error(f"Error running agent: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@bp.route('/<agent_id>/state', methods=['GET'])
def get_agent_state(agent_id):
    """Get the state of a code agent."""
    # Get the agent
    agent = agent_manager.get_agent(agent_id)
    if not agent:
        return jsonify({
            "success": False,
            "error": f"Agent not found: {agent_id}"
        }), 404
    
    # Create controller to get state
    controller = AgentController(
        agent=agent,
        session_id=agent.session_id
    )
    
    return jsonify({
        "success": True,
        "state": controller.state,
        "agent_id": agent_id,
        "name": agent.name,
        "complete": agent.complete
    })


@bp.route('/<agent_id>', methods=['DELETE'])
def delete_agent(agent_id):
    """Delete a code agent."""
    # Delete the agent
    success = agent_manager.delete_agent(agent_id)
    
    if success:
        return jsonify({
            "success": True,
            "message": f"Agent deleted: {agent_id}"
        })
    else:
        return jsonify({
            "success": False,
            "error": f"Failed to delete agent: {agent_id}"
        }), 500


@bp.route('/list', methods=['GET'])
def list_agents():
    """List all code agents for the current session."""
    # Get session ID
    session_id = session.get('session_id')
    
    # List agents
    agents = agent_manager.list_agents(session_id=session_id)
    
    return jsonify({
        "success": True,
        "agents": agents
    })

