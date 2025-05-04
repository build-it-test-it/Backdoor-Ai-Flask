"""
API routes for enhanced agents in Backdoor AI.

This module provides Flask routes for creating, accessing, and managing
enhanced agents with state management and human-in-the-loop capabilities.
"""

from flask import Blueprint, jsonify, request, current_app, g, session
import logging
import traceback
from typing import Dict, Any

from app.ai.enhanced_agents import enhanced_agent_manager, AgentRole, ConfirmationType
from app.database import db

bp = Blueprint('enhanced_agents', __name__, url_prefix='/api/enhanced-agents')

@bp.before_request
def set_agent_context():
    """Set agent context for the request."""
    g.agent_id = request.headers.get('X-Agent-ID') or request.args.get('agent_id')

@bp.route('', methods=['GET'])
def list_agents():
    """List all agents, optionally filtered by session."""
    # Get session ID from query or current session
    session_id = request.args.get('session_id') or session.get('session_id')
    
    # List agents
    agents = enhanced_agent_manager.list_agents(session_id)
    
    return jsonify({
        'success': True,
        'agents': agents,
        'count': len(agents)
    })

@bp.route('', methods=['POST'])
def create_agent():
    """Create a new agent."""
    data = request.json
    
    if not data:
        return jsonify({
            'success': False,
            'error': 'No data provided'
        }), 400
    
    # Get required fields
    name = data.get('name')
    if not name:
        return jsonify({
            'success': False,
            'error': 'Agent name is required'
        }), 400
    
    # Get optional fields
    role_str = data.get('role', 'DEFAULT')
    try:
        role = AgentRole(role_str)
    except ValueError:
        return jsonify({
            'success': False,
            'error': f'Invalid role: {role_str}'
        }), 400
    
    session_id = data.get('session_id') or session.get('session_id')
    agent_id = data.get('id')
    
    # Create the agent
    try:
        agent = enhanced_agent_manager.create_agent(
            name=name,
            role=role,
            session_id=session_id,
            agent_id=agent_id
        )
        
        return jsonify({
            'success': True,
            'agent': {
                'id': agent.id,
                'name': agent.name,
                'role': agent.role,
                'session_id': agent.session_id,
                'status': agent.fsm.get_current_state()
            }
        }), 201
    except Exception as e:
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@bp.route('/<agent_id>', methods=['GET'])
def get_agent(agent_id):
    """Get details of a specific agent."""
    agent = enhanced_agent_manager.get_agent(agent_id)
    
    if not agent:
        return jsonify({
            'success': False,
            'error': 'Agent not found'
        }), 404
    
    return jsonify({
        'success': True,
        'agent': {
            'id': agent.id,
            'name': agent.name,
            'role': agent.role,
            'session_id': agent.session_id,
            'status': agent.fsm.get_current_state(),
            'pending_confirmations': agent.get_pending_confirmations()
        }
    })

@bp.route('/<agent_id>', methods=['DELETE'])
def delete_agent(agent_id):
    """Delete an agent."""
    result = enhanced_agent_manager.delete_agent(agent_id)
    
    if result:
        return jsonify({
            'success': True,
            'message': 'Agent deleted successfully'
        })
    else:
        return jsonify({
            'success': False,
            'error': 'Failed to delete agent'
        }), 404

@bp.route('/<agent_id>/tools', methods=['POST'])
async def execute_tool(agent_id):
    """Execute a tool with an agent."""
    data = request.json
    
    if not data:
        return jsonify({
            'success': False,
            'error': 'No data provided'
        }), 400
    
    # Get required fields
    tool_name = data.get('tool')
    if not tool_name:
        return jsonify({
            'success': False,
            'error': 'Tool name is required'
        }), 400
    
    # Get optional fields
    parameters = data.get('parameters', {})
    require_confirmation = data.get('require_confirmation', False)
    
    # Get the agent
    agent = enhanced_agent_manager.get_agent(agent_id)
    if not agent:
        return jsonify({
            'success': False,
            'error': 'Agent not found'
        }), 404
    
    # Execute the tool
    try:
        result = await agent.execute_tool(
            tool_name=tool_name,
            parameters=parameters,
            require_confirmation=require_confirmation
        )
        
        return jsonify(result)
    except Exception as e:
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@bp.route('/<agent_id>/confirmations', methods=['GET'])
def get_confirmations(agent_id):
    """Get pending confirmations for an agent."""
    agent = enhanced_agent_manager.get_agent(agent_id)
    
    if not agent:
        return jsonify({
            'success': False,
            'error': 'Agent not found'
        }), 404
    
    confirmations = agent.get_pending_confirmations()
    
    return jsonify({
        'success': True,
        'confirmations': confirmations,
        'count': len(confirmations)
    })

@bp.route('/<agent_id>/confirmations/<confirmation_id>', methods=['POST'])
async def execute_confirmation(agent_id, confirmation_id):
    """Execute a confirmation."""
    agent = enhanced_agent_manager.get_agent(agent_id)
    
    if not agent:
        return jsonify({
            'success': False,
            'error': 'Agent not found'
        }), 404
    
    try:
        result = await agent.execute_confirmation(confirmation_id)
        
        return jsonify(result)
    except Exception as e:
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
