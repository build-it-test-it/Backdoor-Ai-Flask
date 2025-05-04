"""
Code Context API routes for Backdoor AI.

This module provides Flask routes for interacting with the code context manager,
including scanning repositories, finding files, and managing code features.
"""

from flask import Blueprint, request, jsonify, current_app, session, g
import json
import os
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from pathlib import Path

from app.ai.code_context_manager import context_managers, CodeContextManager, CodeInterval

bp = Blueprint('code_context', __name__, url_prefix='/api/code-context')

@bp.before_request
def set_agent_context():
    """Set agent context for the request."""
    g.agent_id = request.headers.get('X-Agent-ID') or request.args.get('agent_id')

def get_context_manager(agent_id: str, base_path: Optional[str] = None) -> CodeContextManager:
    """Get or create a context manager for an agent."""
    if agent_id not in context_managers:
        if not base_path:
            # Default to the current working directory
            base_path = os.getcwd()
        
        context_managers[agent_id] = CodeContextManager(Path(base_path))
    
    return context_managers[agent_id]

@bp.route('/status', methods=['GET'])
def status():
    """Get the status of the code context manager."""
    agent_id = request.args.get('agent_id') or g.agent_id
    
    if not agent_id:
        return jsonify({
            'success': False,
            'error': 'Agent ID is required'
        }), 400
    
    # Get or create context manager
    context_manager = get_context_manager(agent_id)
    
    # Get feature counts
    features = context_manager.get_all_features()
    file_count = sum(1 for f in features if not f.is_directory)
    dir_count = sum(1 for f in features if f.is_directory)
    
    return jsonify({
        'success': True,
        'agent_id': agent_id,
        'base_path': str(context_manager.base_path),
        'file_count': file_count,
        'directory_count': dir_count,
        'timestamp': datetime.now().isoformat()
    })

@bp.route('/scan', methods=['POST'])
def scan_repository():
    """Scan a repository for files."""
    data = request.json or {}
    
    agent_id = data.get('agent_id') or g.agent_id
    if not agent_id:
        return jsonify({
            'success': False,
            'error': 'Agent ID is required'
        }), 400
    
    base_path = data.get('base_path')
    max_depth = data.get('max_depth', 5)
    
    # Get or create context manager
    context_manager = get_context_manager(agent_id, base_path)
    
    try:
        # Scan repository
        features = context_manager.scan_repository(max_depth=max_depth)
        
        return jsonify({
            'success': True,
            'agent_id': agent_id,
            'base_path': str(context_manager.base_path),
            'feature_count': len(features),
            'file_count': sum(1 for f in features if not f.is_directory),
            'directory_count': sum(1 for f in features if f.is_directory)
        })
    
    except Exception as e:
        logging.error(f"Error scanning repository: {e}")
        return jsonify({
            'success': False,
            'error': f"Failed to scan repository: {str(e)}"
        }), 500

@bp.route('/features', methods=['GET'])
def list_features():
    """List all features in the context."""
    agent_id = request.args.get('agent_id') or g.agent_id
    if not agent_id:
        return jsonify({
            'success': False,
            'error': 'Agent ID is required'
        }), 400
    
    # Get context manager
    if agent_id not in context_managers:
        return jsonify({
            'success': False,
            'error': 'Context manager not found for agent'
        }), 404
    
    context_manager = context_managers[agent_id]
    
    # Get features
    features = context_manager.get_all_features()
    
    # Convert to dictionaries
    feature_dicts = [feature.to_dict() for feature in features]
    
    return jsonify({
        'success': True,
        'agent_id': agent_id,
        'features': feature_dicts
    })

@bp.route('/features', methods=['POST'])
def add_feature():
    """Add a feature to the context."""
    data = request.json or {}
    
    agent_id = data.get('agent_id') or g.agent_id
    if not agent_id:
        return jsonify({
            'success': False,
            'error': 'Agent ID is required'
        }), 400
    
    path = data.get('path')
    if not path:
        return jsonify({
            'success': False,
            'error': 'Path is required'
        }), 400
    
    # Get intervals if provided
    intervals_data = data.get('intervals', [])
    intervals = []
    
    for interval_data in intervals_data:
        start = interval_data.get('start')
        end = interval_data.get('end')
        
        if start is not None and end is not None:
            try:
                intervals.append(CodeInterval(start, end))
            except ValueError as e:
                return jsonify({
                    'success': False,
                    'error': f"Invalid interval: {str(e)}"
                }), 400
    
    # Get context manager
    if agent_id not in context_managers:
        return jsonify({
            'success': False,
            'error': 'Context manager not found for agent'
        }), 404
    
    context_manager = context_managers[agent_id]
    
    # Add feature
    feature = context_manager.add_feature(Path(path), intervals)
    
    if not feature:
        return jsonify({
            'success': False,
            'error': 'Failed to add feature'
        }), 500
    
    return jsonify({
        'success': True,
        'agent_id': agent_id,
        'feature': feature.to_dict()
    })

@bp.route('/features/<path:feature_path>', methods=['DELETE'])
def remove_feature(feature_path):
    """Remove a feature from the context."""
    agent_id = request.args.get('agent_id') or g.agent_id
    if not agent_id:
        return jsonify({
            'success': False,
            'error': 'Agent ID is required'
        }), 400
    
    # Get context manager
    if agent_id not in context_managers:
        return jsonify({
            'success': False,
            'error': 'Context manager not found for agent'
        }), 404
    
    context_manager = context_managers[agent_id]
    
    # Remove feature
    success = context_manager.remove_feature(Path(feature_path))
    
    if not success:
        return jsonify({
            'success': False,
            'error': 'Feature not found'
        }), 404
    
    return jsonify({
        'success': True,
        'agent_id': agent_id,
        'path': feature_path
    })

@bp.route('/features/<path:feature_path>', methods=['GET'])
def get_feature(feature_path):
    """Get a feature from the context."""
    agent_id = request.args.get('agent_id') or g.agent_id
    if not agent_id:
        return jsonify({
            'success': False,
            'error': 'Agent ID is required'
        }), 400
    
    # Get context manager
    if agent_id not in context_managers:
        return jsonify({
            'success': False,
            'error': 'Context manager not found for agent'
        }), 404
    
    context_manager = context_managers[agent_id]
    
    # Get feature
    feature = context_manager.get_feature(Path(feature_path))
    
    if not feature:
        return jsonify({
            'success': False,
            'error': 'Feature not found'
        }), 404
    
    # Get content if requested
    include_content = request.args.get('include_content', 'false').lower() == 'true'
    
    feature_dict = feature.to_dict()
    if include_content and not feature.is_directory:
        feature_dict['content'] = feature.content
    
    return jsonify({
        'success': True,
        'agent_id': agent_id,
        'feature': feature_dict
    })

@bp.route('/find', methods=['GET'])
def find_files():
    """Find files matching a pattern."""
    agent_id = request.args.get('agent_id') or g.agent_id
    if not agent_id:
        return jsonify({
            'success': False,
            'error': 'Agent ID is required'
        }), 400
    
    pattern = request.args.get('pattern')
    content_pattern = request.args.get('content')
    
    if not pattern and not content_pattern:
        return jsonify({
            'success': False,
            'error': 'Pattern or content pattern is required'
        }), 400
    
    # Get context manager
    if agent_id not in context_managers:
        return jsonify({
            'success': False,
            'error': 'Context manager not found for agent'
        }), 404
    
    context_manager = context_managers[agent_id]
    
    # Find files
    if pattern:
        features = context_manager.find_files_by_pattern(pattern)
    else:
        features = context_manager.find_files_by_content(content_pattern)
    
    # Convert to dictionaries
    feature_dicts = [feature.to_dict() for feature in features]
    
    return jsonify({
        'success': True,
        'agent_id': agent_id,
        'features': feature_dicts
    })

@bp.route('/changes', methods=['GET'])
def get_changes():
    """Get changed files in the repository."""
    agent_id = request.args.get('agent_id') or g.agent_id
    if not agent_id:
        return jsonify({
            'success': False,
            'error': 'Agent ID is required'
        }), 400
    
    staged = request.args.get('staged', 'false').lower() == 'true'
    
    # Get context manager
    if agent_id not in context_managers:
        return jsonify({
            'success': False,
            'error': 'Context manager not found for agent'
        }), 404
    
    context_manager = context_managers[agent_id]
    
    # Get changed features
    features = context_manager.get_changed_features(staged)
    
    # Convert to dictionaries
    feature_dicts = [feature.to_dict() for feature in features]
    
    return jsonify({
        'success': True,
        'agent_id': agent_id,
        'features': feature_dicts
    })