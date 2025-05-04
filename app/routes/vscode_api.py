"""
API routes for VS Code integration in Backdoor AI.

This module provides Flask routes for interacting with the VS Code
integration, including creating and managing workspaces, starting and
stopping sessions, and executing commands.
"""

from flask import Blueprint, request, jsonify, current_app, session, g
import json
import os
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional

from app.ai.vscode_integration import vscode_manager

bp = Blueprint('vscode', __name__, url_prefix='/api/vscode')

@bp.before_request
def set_agent_context():
    """Set agent context for the request."""
    g.agent_id = request.headers.get('X-Agent-ID') or request.args.get('agent_id')

@bp.route('/status', methods=['GET'])
def status():
    """Get the status of the VS Code integration."""
    return jsonify({
        'success': True,
        'initialized': vscode_manager.initialized,
        'workspace_count': len(os.listdir(vscode_manager.workspaces_path)) if vscode_manager.initialized else 0,
        'session_count': len(vscode_manager.active_sessions) if vscode_manager.initialized else 0,
        'timestamp': datetime.now().isoformat()
    })

@bp.route('/workspaces', methods=['GET'])
def list_workspaces():
    """List all workspaces or filter by agent."""
    agent_id = request.args.get('agent_id') or g.agent_id
    
    result = vscode_manager.list_workspaces(agent_id)
    
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
    
    result = vscode_manager.create_workspace(
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
    result = vscode_manager.delete_workspace(workspace_id)
    
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
    
    result = vscode_manager.list_sessions(agent_id)
    
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
    
    result = vscode_manager.start_workspace(
        workspace_id=workspace_id,
        agent_id=agent_id
    )
    
    if not result.get('success', False):
        return jsonify({
            'success': False,
            'error': result.get('error', 'Failed to start session')
        }), 400
    
    return jsonify(result)

@bp.route('/sessions/<session_id>', methods=['DELETE'])
def stop_session(session_id):
    """Stop a session."""
    result = vscode_manager.stop_workspace(session_id)
    
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
    
    result = vscode_manager.execute_command(
        session_id=session_id,
        command=command
    )
    
    if not result.get('success', False):
        return jsonify({
            'success': False,
            'error': result.get('error', 'Failed to execute command')
        }), 400
    
    return jsonify(result)
