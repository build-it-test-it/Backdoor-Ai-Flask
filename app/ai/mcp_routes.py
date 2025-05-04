"""
API routes for the Model Context Protocol (MCP) server.

This module provides Flask routes for interacting with the MCP server,
enabling context management, retrieval, and utilization by external services.
"""

from flask import Blueprint, request, jsonify, current_app, session
import json
from datetime import datetime
from typing import Dict, Any, List, Optional

from app.ai.mcp_server import mcp_server

bp = Blueprint('mcp', __name__, url_prefix='/api/mcp')

# Import agent and tool handler after blueprint creation to avoid circular imports
from app.ai.mcp_agents import agent_manager, AgentRole
from app.ai.mcp_tool_handler import mcp_tool_handler

@bp.route('/status', methods=['GET'])
def status():
    """Get the status of the MCP server."""
    return jsonify({
        'success': True,
        'status': 'ready',
        'initialized': mcp_server.initialized,
        'timestamp': datetime.now().isoformat()
    })

@bp.route('/context', methods=['GET'])
def get_context():
    """Get context for the current session."""
    session_id = request.args.get('session_id') or session.get('session_id')
    token_limit = request.args.get('token_limit', 4000, type=int)
    
    context = mcp_server.get_full_context(session_id, token_limit)
    
    return jsonify({
        'success': True,
        'context': context
    })

@bp.route('/context/add', methods=['POST'])
def add_context():
    """Add a new context item."""
    data = request.json
    
    if not data:
        return jsonify({
            'success': False,
            'error': 'No data provided'
        }), 400
    
    item_type = data.get('type')
    if not item_type:
        return jsonify({
            'success': False,
            'error': 'Context type is required'
        }), 400
    
    content = data.get('content')
    if not content:
        return jsonify({
            'success': False,
            'error': 'Context content is required'
        }), 400
    
    ttl = data.get('ttl', 3600)
    session_id = data.get('session_id')
    
    item_id = mcp_server.add_context_item(
        item_type=item_type,
        data=content,
        ttl=ttl,
        session_id=session_id
    )
    
    return jsonify({
        'success': True,
        'item_id': item_id,
        'message': f'Context item of type {item_type} added successfully'
    })

@bp.route('/context/<item_id>', methods=['GET'])
def get_context_item(item_id):
    """Get a specific context item by ID."""
    session_id = request.args.get('session_id')
    
    item_data = mcp_server.get_context_item(item_id, session_id)
    
    if item_data is None:
        return jsonify({
            'success': False,
            'error': 'Context item not found or expired'
        }), 404
    
    return jsonify({
        'success': True,
        'item': item_data
    })

@bp.route('/context/<item_id>', methods=['PUT'])
def update_context_item(item_id):
    """Update a specific context item."""
    data = request.json
    
    if not data or 'content' not in data:
        return jsonify({
            'success': False,
            'error': 'No content provided for update'
        }), 400
    
    session_id = data.get('session_id')
    content = data.get('content')
    
    success = mcp_server.update_context_item(item_id, content, session_id)
    
    if not success:
        return jsonify({
            'success': False,
            'error': 'Context item not found'
        }), 404
    
    return jsonify({
        'success': True,
        'message': 'Context item updated successfully'
    })

@bp.route('/context/type/<item_type>', methods=['GET'])
def get_context_by_type(item_type):
    """Get context items by type."""
    session_id = request.args.get('session_id')
    max_items = request.args.get('max_items', 10, type=int)
    
    items = mcp_server.get_context_by_type(item_type, session_id, max_items)
    
    return jsonify({
        'success': True,
        'items': items,
        'count': len(items)
    })

@bp.route('/behavior', methods=['POST'])
def record_behavior():
    """Record user behavior as context."""
    data = request.json
    
    if not data:
        return jsonify({
            'success': False,
            'error': 'No data provided'
        }), 400
    
    action = data.get('action')
    if not action:
        return jsonify({
            'success': False,
            'error': 'Action is required'
        }), 400
    
    screen = data.get('screen')
    if not screen:
        return jsonify({
            'success': False,
            'error': 'Screen is required'
        }), 400
    
    duration = data.get('duration', 0)
    details = data.get('details', {})
    
    item_id = mcp_server.record_user_behavior(action, screen, duration, details)
    
    return jsonify({
        'success': True,
        'item_id': item_id,
        'message': 'Behavior recorded successfully'
    })

@bp.route('/interaction', methods=['POST'])
def record_interaction():
    """Record an AI interaction as context."""
    data = request.json
    
    if not data:
        return jsonify({
            'success': False,
            'error': 'No data provided'
        }), 400
    
    user_message = data.get('user_message')
    if not user_message:
        return jsonify({
            'success': False,
            'error': 'User message is required'
        }), 400
    
    ai_response = data.get('ai_response')
    if not ai_response:
        return jsonify({
            'success': False,
            'error': 'AI response is required'
        }), 400
    
    context = data.get('context', {})
    
    item_id = mcp_server.record_interaction(user_message, ai_response, context)
    
    return jsonify({
        'success': True,
        'item_id': item_id,
        'message': 'Interaction recorded successfully'
    })

@bp.route('/github', methods=['POST'])
def store_github_info():
    """Store GitHub repository information."""
    data = request.json
    
    if not data:
        return jsonify({
            'success': False,
            'error': 'No data provided'
        }), 400
    
    repo_name = data.get('repo_name')
    if not repo_name:
        return jsonify({
            'success': False,
            'error': 'Repository name is required'
        }), 400
    
    repo_info = data.get('repo_info', {})
    
    item_id = mcp_server.store_github_info(repo_name, repo_info)
    
    return jsonify({
        'success': True,
        'item_id': item_id,
        'message': 'GitHub information stored successfully'
    })

@bp.route('/cleanup', methods=['POST'])
def cleanup():
    """Clean up expired context items."""
    count = mcp_server.cleanup_expired_items()
    
    return jsonify({
        'success': True,
        'removed_count': count,
        'message': f'Removed {count} expired context items'
    })

@bp.route('/activities', methods=['GET'])
def recent_activities():
    """Get recent user activities."""
    limit = request.args.get('limit', 10, type=int)
    
    activities = mcp_server.get_recent_activities(limit)
    
    return jsonify({
        'success': True,
        'activities': activities,
        'count': len(activities)
    })

# Agent-related routes

@bp.route('/agents', methods=['GET'])
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

@bp.route('/agents/create', methods=['POST'])
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

@bp.route('/agents/<agent_id>', methods=['GET'])
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

@bp.route('/agents/<agent_id>/status', methods=['GET'])
def get_agent_status(agent_id):
    """Get the status of an agent."""
    status = agent_manager.get_agent_status(agent_id)
    
    if not status.get('success', False):
        return jsonify(status), 404
    
    return jsonify(status)

@bp.route('/agents/<agent_id>/terminate', methods=['POST'])
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

@bp.route('/agents/default', methods=['GET'])
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

@bp.route('/agents/default', methods=['POST'])
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

# Tool-related routes

@bp.route('/tools', methods=['GET'])
def get_tools():
    """Get all available tools."""
    return jsonify({
        'success': True,
        'tools': mcp_tool_handler.get_tool_types(),
        'enabled_tools': list(mcp_tool_handler.enabled_tools),
        'count': len(mcp_tool_handler.enabled_tools)
    })

@bp.route('/tools/schema', methods=['GET'])
def get_tools_schema():
    """Get the schema for all enabled tools."""
    return jsonify({
        'success': True,
        'schemas': mcp_tool_handler.get_tools_schema()
    })

@bp.route('/tools/execute', methods=['POST'])
def execute_tool():
    """Execute a tool."""
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
    
    # Get agent and session information
    agent_id = data.get('agent_id')
    session_id = data.get('session_id') or session.get('session_id')
    
    # Get tool parameters
    params = data.get('params', {})
    
    # Execute the tool
    result = mcp_tool_handler.execute_tool(
        tool_type=tool_type,
        agent_id=agent_id,
        session_id=session_id,
        **params
    )
    
    return jsonify({
        'success': True,
        'result': result
    })

@bp.route('/tools/enable/<tool_type>', methods=['POST'])
def enable_tool(tool_type):
    """Enable a tool."""
    success = mcp_tool_handler.enable_tool(tool_type)
    
    if not success:
        return jsonify({
            'success': False,
            'error': f'Tool {tool_type} not found or already enabled'
        }), 404
    
    return jsonify({
        'success': True,
        'message': f'Tool {tool_type} enabled successfully'
    })

@bp.route('/tools/disable/<tool_type>', methods=['POST'])
def disable_tool(tool_type):
    """Disable a tool."""
    success = mcp_tool_handler.disable_tool(tool_type)
    
    if not success:
        return jsonify({
            'success': False,
            'error': f'Tool {tool_type} not found or already disabled'
        }), 404
    
    return jsonify({
        'success': True,
        'message': f'Tool {tool_type} disabled successfully'
    })

@bp.route('/tools/permission', methods=['POST'])
def set_tool_permission():
    """Set permission for a role to use a tool."""
    data = request.json
    
    if not data:
        return jsonify({
            'success': False,
            'error': 'No data provided'
        }), 400
    
    role = data.get('role')
    if not role:
        return jsonify({
            'success': False,
            'error': 'Role is required'
        }), 400
    
    tool_type = data.get('tool_type')
    if not tool_type:
        return jsonify({
            'success': False,
            'error': 'Tool type is required'
        }), 400
    
    allowed = data.get('allowed', False)
    
    success = mcp_tool_handler.set_role_permission(role, tool_type, allowed)
    
    if not success:
        return jsonify({
            'success': False,
            'error': f'Failed to set permission: role={role}, tool={tool_type}, allowed={allowed}'
        }), 400
    
    return jsonify({
        'success': True,
        'message': f'Permission set: role={role}, tool={tool_type}, allowed={allowed}'
    })

@bp.route('/tools/history', methods=['GET'])
def get_tool_history():
    """Get tool usage history."""
    limit = request.args.get('limit', 100, type=int)
    
    history = mcp_tool_handler.get_tool_usage_history(limit)
    
    return jsonify({
        'success': True,
        'history': history,
        'count': len(history)
    })
