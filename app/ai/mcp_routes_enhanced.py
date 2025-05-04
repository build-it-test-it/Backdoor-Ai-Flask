"""
Enhanced API routes for the Model Context Protocol (MCP) server.

This module provides additional routes for the MCP server, including
endpoints for context chains, agent context integration, and maintenance.
"""

import json
import logging
import asyncio
from typing import Dict, List, Any, Optional
from datetime import datetime

from flask import Blueprint, request, jsonify, current_app, g, session
from app.ai.mcp_server import mcp_server
from app.ai.mcp_enhancements import (
    ContextPrioritizer, 
    ContextChain, 
    AgentContextIntegration, 
    maintenance_scheduler
)

# Set up logging
logger = logging.getLogger("mcp_routes_enhanced")

bp = Blueprint('mcp_enhanced', __name__, url_prefix='/api/mcp/enhanced')

@bp.before_request
def set_agent_context():
    """Set agent context for the request."""
    g.agent_id = request.headers.get('X-Agent-ID') or request.args.get('agent_id')

@bp.route('/priority/update', methods=['POST'])
def update_priorities():
    """Update priorities for all context items."""
    try:
        ContextPrioritizer.update_context_priorities()
        
        return jsonify({
            'success': True,
            'message': 'Context priorities updated successfully'
        })
    except Exception as e:
        logger.error(f"Error updating priorities: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@bp.route('/chains', methods=['POST'])
def create_chain():
    """Create a new context chain."""
    data = request.json
    
    if not data:
        return jsonify({
            'success': False,
            'error': 'No data provided'
        }), 400
    
    # Get required fields
    root_item_id = data.get('root_item_id')
    chain_name = data.get('name')
    
    if not root_item_id or not chain_name:
        return jsonify({
            'success': False,
            'error': 'Root item ID and chain name are required'
        }), 400
    
    # Get optional fields
    description = data.get('description', f"Chain created at {datetime.utcnow().isoformat()}")
    session_id = data.get('session_id') or session.get('session_id')
    
    # Create chain
    result = ContextChain.create_chain(
        root_item_id=root_item_id,
        chain_name=chain_name,
        description=description,
        session_id=session_id
    )
    
    if result.get('success', False):
        return jsonify(result)
    else:
        return jsonify(result), 400

@bp.route('/chains/<chain_id>', methods=['GET'])
def get_chain(chain_id):
    """Get a context chain with all its items."""
    session_id = request.args.get('session_id') or session.get('session_id')
    
    result = ContextChain.get_chain(
        chain_id=chain_id,
        session_id=session_id
    )
    
    if result.get('success', False):
        return jsonify(result)
    else:
        return jsonify(result), 404

@bp.route('/chains/<chain_id>/items', methods=['POST'])
def add_to_chain(chain_id):
    """Add a context item to an existing chain."""
    data = request.json
    
    if not data:
        return jsonify({
            'success': False,
            'error': 'No data provided'
        }), 400
    
    # Get required fields
    item_id = data.get('item_id')
    
    if not item_id:
        return jsonify({
            'success': False,
            'error': 'Item ID is required'
        }), 400
    
    # Get optional fields
    session_id = data.get('session_id') or session.get('session_id')
    
    # Add to chain
    result = ContextChain.add_to_chain(
        chain_id=chain_id,
        item_id=item_id,
        session_id=session_id
    )
    
    if result.get('success', False):
        return jsonify(result)
    else:
        return jsonify(result), 400

@bp.route('/agent-context/<agent_id>', methods=['GET'])
async def get_agent_context(agent_id):
    """Get context relevant to a specific agent."""
    # Get optional parameters
    context_types = request.args.get('context_types')
    if context_types:
        context_types = context_types.split(',')
    
    token_limit = request.args.get('token_limit', 2000, type=int)
    
    # Get agent context
    result = await AgentContextIntegration.get_agent_context(
        agent_id=agent_id,
        context_types=context_types,
        token_limit=token_limit
    )
    
    if result.get('success', False):
        return jsonify(result)
    else:
        return jsonify(result), 404

@bp.route('/agent-context/<agent_id>', methods=['POST'])
async def add_agent_context(agent_id):
    """Add context data for an agent."""
    data = request.json
    
    if not data:
        return jsonify({
            'success': False,
            'error': 'No data provided'
        }), 400
    
    # Get required fields
    item_type = data.get('item_type')
    context_data = data.get('data')
    
    if not item_type or not context_data:
        return jsonify({
            'success': False,
            'error': 'Item type and data are required'
        }), 400
    
    # Get optional fields
    ttl = data.get('ttl', 3600)
    
    # Add context
    result = await AgentContextIntegration.add_agent_context(
        agent_id=agent_id,
        item_type=item_type,
        data=context_data,
        ttl=ttl
    )
    
    if result.get('success', False):
        return jsonify(result)
    else:
        return jsonify(result), 400

@bp.route('/maintenance/start', methods=['POST'])
async def start_maintenance():
    """Start the maintenance scheduler."""
    await maintenance_scheduler.start_maintenance_loop()
    
    return jsonify({
        'success': True,
        'message': 'Maintenance scheduler started'
    })

@bp.route('/maintenance/stop', methods=['POST'])
async def stop_maintenance():
    """Stop the maintenance scheduler."""
    await maintenance_scheduler.stop_maintenance_loop()
    
    return jsonify({
        'success': True,
        'message': 'Maintenance scheduler stopped'
    })

@bp.route('/maintenance/status', methods=['GET'])
def get_maintenance_status():
    """Get the status of the maintenance scheduler."""
    return jsonify({
        'success': True,
        'running': maintenance_scheduler.running
    })

@bp.route('/maintenance/run', methods=['POST'])
async def run_maintenance():
    """Run maintenance tasks immediately."""
    try:
        await maintenance_scheduler._run_maintenance()
        
        return jsonify({
            'success': True,
            'message': 'Maintenance tasks executed successfully'
        })
    except Exception as e:
        logger.error(f"Error running maintenance: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
