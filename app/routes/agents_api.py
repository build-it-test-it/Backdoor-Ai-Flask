"""
API routes for the Agent system in the MCP architecture.

This module provides Flask routes for creating and managing agents
through a RESTful API interface.
"""

from flask import Blueprint, request, jsonify, current_app, session
import json
from datetime import datetime
from typing import Dict, Any, List, Optional

from app.ai.mcp_agents import agent_manager, AgentRole
from app.ai.mcp_tool_handler import mcp_tool_handler

bp = Blueprint('agents', __name__, url_prefix='/api/agents')

@bp.route('/status', methods=['GET'])
def status():
    """Get the status of the agent system."""
    session_id = request.args.get('session_id') or session.get('session_id')
    
    # Get all agents for this session
    agents = []
    if session_id:
        agents = agent_manager.get_agents_for_session(session_id)
    
    return jsonify({
        'success': True,
        'status': 'ready',
        'agent_count': len(agents),
        'timestamp': datetime.now().isoformat()
    })

@bp.route('/', methods=['GET'])
def get_agents():
    """Get all agents for the current session."""
    session_id = request.args.get('session_id') or session.get('session_id')
    
    if not session_id:
        return jsonify({
            'success': False,
            'error': 'Session ID is required'
        }), 400
    
    agents = agent_manager.get_agents_for_session(session_id)
    
    return jsonify({
        'success': True,
        'agents': [agent.get_context() for agent in agents],
        'count': len(agents)
    })

@bp.route('/', methods=['POST'])
def create_agent():
    """Create a new agent."""
    data = request.json
    
    if not data:
        return jsonify({
            'success': False,
            'error': 'No data provided'
        }), 400
    
    name = data.get('name')
    role = data.get('role', AgentRole.ASSISTANT)
    session_id = data.get('session_id') or session.get('session_id')
    tool_permissions = data.get('tool_permissions')
    
    if not session_id:
        return jsonify({
            'success': False,
            'error': 'Session ID is required'
        }), 400
    
    agent = agent_manager.create_agent(
        name=name,
        role=role,
        session_id=session_id,
        tool_permissions=tool_permissions
    )
    
    return jsonify({
        'success': True,
        'agent': agent.get_context(),
        'message': f'Agent {agent.name} created successfully'
    })

@bp.route('/<agent_id>', methods=['GET'])
def get_agent(agent_id):
    """Get an agent by ID."""
    agent = agent_manager.get_agent(agent_id)
    
    if not agent:
        return jsonify({
            'success': False,
            'error': f'Agent with ID {agent_id} not found'
        }), 404
    
    return jsonify({
        'success': True,
        'agent': agent.get_context()
    })

@bp.route('/<agent_id>/status', methods=['GET'])
def get_agent_status(agent_id):
    """Get the status of an agent."""
    status = agent_manager.get_agent_status(agent_id)
    
    if not status.get('success', False):
        return jsonify(status), 404
    
    return jsonify(status)

@bp.route('/<agent_id>/terminate', methods=['POST'])
def terminate_agent(agent_id):
    """Terminate an agent."""
    success = agent_manager.terminate_agent(agent_id)
    
    if not success:
        return jsonify({
            'success': False,
            'error': f'Agent with ID {agent_id} not found or could not be terminated'
        }), 404
    
    return jsonify({
        'success': True,
        'message': f'Agent with ID {agent_id} terminated successfully'
    })

@bp.route('/default', methods=['GET'])
def get_default_agent():
    """Get the default agent for the current session."""
    session_id = request.args.get('session_id') or session.get('session_id')
    
    if not session_id:
        return jsonify({
            'success': False,
            'error': 'Session ID is required'
        }), 400
    
    agent = agent_manager.get_default_agent(session_id)
    
    if not agent:
        return jsonify({
            'success': False,
            'error': f'No default agent found for session {session_id}'
        }), 404
    
    return jsonify({
        'success': True,
        'agent': agent.get_context()
    })

@bp.route('/default', methods=['POST'])
def set_default_agent():
    """Set the default agent for the current session."""
    data = request.json
    
    if not data:
        return jsonify({
            'success': False,
            'error': 'No data provided'
        }), 400
    
    agent_id = data.get('agent_id')
    if not agent_id:
        return jsonify({
            'success': False,
            'error': 'Agent ID is required'
        }), 400
    
    session_id = data.get('session_id') or session.get('session_id')
    if not session_id:
        return jsonify({
            'success': False,
            'error': 'Session ID is required'
        }), 400
    
    success = agent_manager.set_default_agent(session_id, agent_id)
    
    if not success:
        return jsonify({
            'success': False,
            'error': f'Agent with ID {agent_id} not found or not associated with session {session_id}'
        }), 404
    
    return jsonify({
        'success': True,
        'message': f'Default agent set to {agent_id} for session {session_id}'
    })

@bp.route('/<agent_id>/execute', methods=['POST'])
def execute_tool_with_agent(agent_id):
    """Execute a tool with a specific agent."""
    data = request.json
    
    if not data:
        return jsonify({
            'success': False,
            'error': 'No data provided'
        }), 400
    
    tool_type = data.get('tool_type')
    if not tool_type:
        return jsonify({
            'success': False,
            'error': 'Tool type is required'
        }), 400
    
    # Get tool parameters
    params = data.get('params', {})
    
    # Execute the tool with the agent
    result = agent_manager.execute_tool_with_agent(
        agent_id=agent_id,
        tool_type=tool_type,
        **params
    )
    
    return jsonify({
        'success': True,
        'result': result
    })

@bp.route('/<agent_id>/task', methods=['POST'])
def execute_task_with_agent(agent_id):
    """Execute a task with a specific agent."""
    data = request.json
    
    if not data:
        return jsonify({
            'success': False,
            'error': 'No data provided'
        }), 400
    
    task_description = data.get('task_description')
    if not task_description:
        return jsonify({
            'success': False,
            'error': 'Task description is required'
        }), 400
    
    # Get task data
    task_data = data.get('task_data', {})
    
    # Execute the task with the agent
    result = agent_manager.execute_task_with_agent(
        agent_id=agent_id,
        task_description=task_description,
        task_data=task_data
    )
    
    return jsonify({
        'success': True,
        'result': result
    })
