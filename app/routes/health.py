"""
Health check routes for the Backdoor AI application.

This module provides API endpoints for checking the health of the application,
including database connectivity, model service, and VS Code integration.
"""

from flask import Blueprint, jsonify, current_app
import os
import time
import logging
from datetime import datetime

from app.database import db_health_check
from app.ai.model_service import model_service
from app.ai.vscode_integration import vscode_manager

# Configure logging
logger = logging.getLogger("health")

bp = Blueprint('health', __name__, url_prefix='/api/health')

@bp.route('', methods=['GET'])
def health_check():
    """
    Basic health check endpoint for the application.
    
    This endpoint provides a comprehensive health check of all system components,
    including database connectivity, model service, and VS Code integration.
    
    Returns:
        JSON response with health status of all components
    """
    # Check database connectivity
    db_status = check_database()
    
    # Check model service
    model_status = check_model_service()
    
    # Check VS Code integration
    vscode_status = check_vscode()
    
    # Check if Backdoor is initialized
    backdoor_initialized = os.path.exists('/tmp/backdoor/initialized')
    
    # Determine overall system status
    all_systems_ok = (
        db_status.get('connected', False) and 
        model_status.get('available', False) and 
        backdoor_initialized
    )
    
    # Prepare response
    response = {
        'status': 'ok' if all_systems_ok else 'degraded',
        'timestamp': datetime.now().isoformat(),
        'database': db_status,
        'model_service': model_status,
        'vscode': vscode_status,
        'backdoor_initialized': backdoor_initialized,
        'environment': current_app.config.get('BACKDOOR_ENV', 'unknown'),
        'version': current_app.config.get('BACKDOOR_VERSION', 'unknown')
    }
    
    # Log health check results if degraded
    if not all_systems_ok:
        logger.warning(f"Health check degraded: {response}")
    
    return jsonify(response)

@bp.route('/db', methods=['GET'])
def database_health_check():
    """
    Database-specific health check endpoint.
    
    This endpoint provides detailed information about the database connection,
    including connection latency and pool statistics.
    
    Returns:
        JSON response with detailed database health information
    """
    # Get detailed database health information
    db_status = check_database(detailed=True)
    
    return jsonify({
        'status': 'ok' if db_status.get('connected', False) else 'error',
        'timestamp': datetime.now().isoformat(),
        'database': db_status
    })

def check_database(detailed=False):
    """
    Check database connectivity.
    
    Args:
        detailed: Whether to include detailed connection information
        
    Returns:
        Dictionary with database health status
    """
    # Use our enhanced database health check function
    health_result = db_health_check()
    
    # Convert to our expected format
    db_status = {
        'connected': health_result['status'] == 'healthy',
        'type': 'unknown'
    }
    
    # Add error message if present
    if health_result['status'] != 'healthy':
        db_status['error'] = health_result['message']
    else:
        db_status['response_time_ms'] = health_result.get('latency_ms', 0)
    
    # Determine database type
    db_url = current_app.config.get('SQLALCHEMY_DATABASE_URI', '')
    
    if not db_url:
        db_status['connected'] = False
        db_status['error'] = 'No database URL configured'
        return db_status
    
    # Determine database type from URL
    if db_url.startswith('sqlite:///'):
        db_status['type'] = 'sqlite'
        db_path = db_url.replace('sqlite:///', '')
        db_status['path'] = db_path
        
        # Check if file exists
        if not os.path.exists(db_path) and db_path != ':memory:':
            db_status['connected'] = False
            db_status['error'] = f'SQLite database file not found: {db_path}'
    
    elif db_url.startswith('postgresql://'):
        db_status['type'] = 'postgresql'
        
        # Add additional PostgreSQL info if detailed check requested
        if detailed and db_status['connected']:
            try:
                # Get postgres version
                from sqlalchemy import text
                from app.database import db
                
                version_result = db.session.execute(text("SELECT version()")).scalar()
                db_status['version'] = version_result
                
                # Get connection pool stats if available
                engine = db.engine
                if hasattr(engine, 'pool') and hasattr(engine.pool, 'size'):
                    db_status['pool'] = {
                        'size': engine.pool.size(),
                        'checkedin': engine.pool.checkedin(),
                        'overflow': engine.pool.overflow(),
                        'checkedout': engine.pool.checkedout()
                    }
            except Exception as e:
                logger.warning(f"Error getting detailed database info: {e}")
    
    else:
        db_status['type'] = db_url.split('://')[0]
        
    return db_status

def check_model_service():
    """
    Check model service connectivity.
    
    Returns:
        Dictionary with model service health status
    """
    try:
        # Use the unified model service
        api_key = model_service.get_api_key()
        
        if not api_key:
            return {
                'available': False,
                'error': 'No API key configured'
            }
        
        # Get provider and model information
        provider = model_service.get_provider()
        model = model_service.get_model()
        
        # Check if the model service is initialized
        return {
            'available': model_service.ready,
            'provider': provider,
            'model': model,
            'initialized': model_service.initialized
        }
    
    except Exception as e:
        logger.error(f"Error checking model service: {e}")
        return {
            'available': False,
            'error': str(e)
        }

def check_vscode():
    """
    Check VS Code integration.
    
    Returns:
        Dictionary with VS Code integration health status
    """
    try:
        if not vscode_manager.initialized:
            return {
                'available': False,
                'error': 'VS Code integration not initialized'
            }
        
        # Get workspace and session counts
        workspaces_count = 0
        if hasattr(vscode_manager, 'workspaces_path') and os.path.exists(vscode_manager.workspaces_path):
            workspaces_count = len(os.listdir(vscode_manager.workspaces_path))
        
        sessions_count = 0
        if hasattr(vscode_manager, 'active_sessions'):
            sessions_count = len(vscode_manager.active_sessions)
        
        return {
            'available': True,
            'workspaces_count': workspaces_count,
            'sessions_count': sessions_count
        }
    
    except Exception as e:
        logger.error(f"Error checking VS Code integration: {e}")
        return {
            'available': False,
            'error': str(e)
        }
