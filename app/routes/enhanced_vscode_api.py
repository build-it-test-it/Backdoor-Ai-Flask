"""
Enhanced VS Code API routes for Backdoor AI.

This module provides Flask routes for interacting with the enhanced VS Code
integration, including creating and managing workspaces, starting and
stopping sessions, and executing commands.
"""

from flask import Blueprint, request, jsonify, current_app, session, g
import json
import os
import logging
import asyncio
from datetime import datetime
from typing import Dict, Any, List, Optional
from pathlib import Path

from app.ai.enhanced_vscode_integration import enhanced_vscode_manager
from app.ai.enhanced_agent_handler import agent_handlers, EnhancedAgentHandler

bp = Blueprint('enhanced_vscode', __name__, url_prefix='/api/enhanced-vscode')

@bp.before_request
def set_agent_context():
    """Set agent context for the request."""
    g.agent_id = request.headers.get('X-Agent-ID') or request.args.get('agent_id')

@bp.route('/status', methods=['GET'])
def status():
    """Get the status of the enhanced VS Code integration."""
    return jsonify({
        'success': True,
        'initialized': enhanced_vscode_manager.initialized,
        'workspace_count': len(os.listdir(enhanced_vscode_manager.workspaces_path)) if enhanced_vscode_manager.initialized else 0,
        'session_count': len(enhanced_vscode_manager.active_sessions) if enhanced_vscode_manager.initialized else 0,
        'timestamp': datetime.now().isoformat()
    })

@bp.route('/workspaces', methods=['GET'])
def list_workspaces():
    """List all workspaces or filter by agent."""
    agent_id = request.args.get('agent_id') or g.agent_id
    
    result = enhanced_vscode_manager.list_workspaces(agent_id)
    
    if not result.get('success', False):
        return jsonify({
            'success': False,
            'error': result.get('error', 'Failed to list workspaces')
        }), 400
    
    return jsonify(result)

@bp.route('/workspaces', methods=['POST'])
def create_workspace():
    """Create a new workspace."""
    data = request.json
    
    if not data:
        return jsonify({
            'success': False,
            'error': 'No data provided'
        }), 400
    
    name = data.get('name')
    if not name:
        return jsonify({
            'success': False,
            'error': 'Workspace name is required'
        }), 400
    
    # Get agent ID
    agent_id = data.get('agent_id') or g.agent_id or 'unknown'
    
    # Get template if provided
    template = data.get('template')
    
    result = enhanced_vscode_manager.create_workspace(
        name=name,
        agent_id=agent_id,
        template=template
    )
    
    if not result.get('success', False):
        return jsonify({
            'success': False,
            'error': result.get('error', 'Failed to create workspace')
        }), 400
    
    return jsonify(result)

@bp.route('/workspaces/<workspace_id>', methods=['DELETE'])
def delete_workspace(workspace_id):
    """Delete a workspace."""
    result = enhanced_vscode_manager.delete_workspace(workspace_id)
    
    if not result.get('success', False):
        return jsonify({
            'success': False,
            'error': result.get('error', 'Failed to delete workspace')
        }), 400
    
    return jsonify(result)

@bp.route('/sessions', methods=['GET'])
def list_sessions():
    """List all sessions or filter by agent."""
    agent_id = request.args.get('agent_id') or g.agent_id
    
    result = enhanced_vscode_manager.list_sessions(agent_id)
    
    if not result.get('success', False):
        return jsonify({
            'success': False,
            'error': result.get('error', 'Failed to list sessions')
        }), 400
    
    return jsonify(result)

@bp.route('/sessions', methods=['POST'])
def start_session():
    """Start a new session for a workspace."""
    data = request.json
    
    if not data:
        return jsonify({
            'success': False,
            'error': 'No data provided'
        }), 400
    
    workspace_id = data.get('workspace_id')
    if not workspace_id:
        return jsonify({
            'success': False,
            'error': 'Workspace ID is required'
        }), 400
    
    # Get agent ID
    agent_id = data.get('agent_id') or g.agent_id or 'unknown'
    
    result = enhanced_vscode_manager.start_workspace(
        workspace_id=workspace_id,
        agent_id=agent_id
    )
    
    if not result.get('success', False):
        return jsonify({
            'success': False,
            'error': result.get('error', 'Failed to start session')
        }), 400
    
    # Initialize agent handler for this workspace if it doesn't exist
    if agent_id not in agent_handlers:
        workspace_path = os.path.join(enhanced_vscode_manager.workspaces_path, workspace_id)
        agent_handlers[agent_id] = EnhancedAgentHandler(agent_id, Path(workspace_path))
    
    return jsonify(result)

@bp.route('/sessions/<session_id>', methods=['DELETE'])
def stop_session(session_id):
    """Stop a session."""
    result = enhanced_vscode_manager.stop_workspace(session_id)
    
    if not result.get('success', False):
        return jsonify({
            'success': False,
            'error': result.get('error', 'Failed to stop session')
        }), 400
    
    return jsonify(result)

@bp.route('/sessions/<session_id>/command', methods=['POST'])
def execute_command(session_id):
    """Execute a command in a session."""
    data = request.json
    
    if not data:
        return jsonify({
            'success': False,
            'error': 'No data provided'
        }), 400
    
    command = data.get('command')
    if not command:
        return jsonify({
            'success': False,
            'error': 'Command is required'
        }), 400
    
    result = enhanced_vscode_manager.execute_command(
        session_id=session_id,
        command=command
    )
    
    if not result.get('success', False):
        return jsonify({
            'success': False,
            'error': result.get('error', 'Failed to execute command')
        }), 400
    
    return jsonify(result)

@bp.route('/sessions/<session_id>/messages', methods=['GET'])
def get_messages(session_id):
    """Get pending messages for a session."""
    messages = enhanced_vscode_manager.get_messages(session_id)
    
    return jsonify({
        'success': True,
        'messages': messages
    })

@bp.route('/sessions/<session_id>/messages', methods=['POST'])
def send_message(session_id):
    """Send a message to the server."""
    data = request.json
    
    if not data:
        return jsonify({
            'success': False,
            'error': 'No data provided'
        }), 400
    
    result = enhanced_vscode_manager.handle_message(data, session_id)
    
    return jsonify(result)

@bp.route('/agent/<agent_id>/enable', methods=['POST'])
def enable_agent(agent_id):
    """Enable agent mode for an agent."""
    if agent_id not in agent_handlers:
        return jsonify({
            'success': False,
            'error': 'Agent not found'
        }), 404
    
    result = agent_handlers[agent_id].enable_agent_mode()
    
    return jsonify(result)

@bp.route('/agent/<agent_id>/disable', methods=['POST'])
def disable_agent(agent_id):
    """Disable agent mode for an agent."""
    if agent_id not in agent_handlers:
        return jsonify({
            'success': False,
            'error': 'Agent not found'
        }), 404
    
    result = agent_handlers[agent_id].disable_agent_mode()
    
    return jsonify(result)

@bp.route('/agent/<agent_id>/commands', methods=['GET'])
def get_commands(agent_id):
    """Get commands for an agent."""
    if agent_id not in agent_handlers:
        return jsonify({
            'success': False,
            'error': 'Agent not found'
        }), 404
    
    result = agent_handlers[agent_id].determine_commands()
    
    return jsonify(result)

@bp.route('/agent/<agent_id>/execute', methods=['POST'])
async def execute_agent_command(agent_id):
    """Execute a command for an agent."""
    if agent_id not in agent_handlers:
        return jsonify({
            'success': False,
            'error': 'Agent not found'
        }), 404
    
    data = request.json
    
    if not data:
        return jsonify({
            'success': False,
            'error': 'No data provided'
        }), 400
    
    command = data.get('command')
    if not command:
        return jsonify({
            'success': False,
            'error': 'Command is required'
        }), 400
    
    # Execute the command asynchronously
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    result = await agent_handlers[agent_id].execute_command(command)
    
    return jsonify(result)

@bp.route('/agent/<agent_id>/context', methods=['GET'])
def get_context(agent_id):
    """Get context for an agent."""
    if agent_id not in agent_handlers:
        return jsonify({
            'success': False,
            'error': 'Agent not found'
        }), 404
    
    result = agent_handlers[agent_id].get_context_summary()
    
    return jsonify(result)

@bp.route('/agent/<agent_id>/file', methods=['GET'])
def get_file(agent_id):
    """Get a file from the agent's context."""
    if agent_id not in agent_handlers:
        return jsonify({
            'success': False,
            'error': 'Agent not found'
        }), 404
    
    path = request.args.get('path')
    if not path:
        return jsonify({
            'success': False,
            'error': 'Path is required'
        }), 400
    
    result = agent_handlers[agent_id].get_file_content(path)
    
    return jsonify(result)

@bp.route('/agent/<agent_id>/file', methods=['POST'])
def add_file(agent_id):
    """Add a file to the agent's context."""
    if agent_id not in agent_handlers:
        return jsonify({
            'success': False,
            'error': 'Agent not found'
        }), 404
    
    data = request.json
    
    if not data:
        return jsonify({
            'success': False,
            'error': 'No data provided'
        }), 400
    
    path = data.get('path')
    if not path:
        return jsonify({
            'success': False,
            'error': 'Path is required'
        }), 400
    
    result = agent_handlers[agent_id].add_file_to_context(path)
    
    return jsonify(result)

@bp.route('/agent/<agent_id>/file', methods=['DELETE'])
def remove_file(agent_id):
    """Remove a file from the agent's context."""
    if agent_id not in agent_handlers:
        return jsonify({
            'success': False,
            'error': 'Agent not found'
        }), 404
    
    path = request.args.get('path')
    if not path:
        return jsonify({
            'success': False,
            'error': 'Path is required'
        }), 400
    
    result = agent_handlers[agent_id].remove_file_from_context(path)
    
    return jsonify(result)