"""
Health check routes for the Backdoor AI application.

This module provides API endpoints for checking the health of the application,
including database connectivity, model service, and VS Code integration.
"""

from flask import Blueprint, jsonify, current_app
import os
import psycopg2
import time
from datetime import datetime

from app.ai.model_service import model_service
from app.ai.vscode_integration import vscode_manager

bp = Blueprint('health', __name__, url_prefix='/api/health')

@bp.route('', methods=['GET'])
def health_check():
    """Basic health check endpoint for the application."""
    
    # Check database connectivity
    db_status = check_database()
    
    # Check model service
    model_status = check_model_service()
    
    # Check VS Code integration
    vscode_status = check_vscode()
    
    # Check if Backdoor is initialized
    backdoor_initialized = os.path.exists('/tmp/backdoor/initialized')
    
    # Prepare response
    response = {
        'status': 'ok' if all([db_status['connected'], model_status['available'], backdoor_initialized]) else 'degraded',
        'timestamp': datetime.now().isoformat(),
        'database': db_status,
        'model_service': model_status,
        'vscode': vscode_status,
        'backdoor_initialized': backdoor_initialized,
        'environment': current_app.config.get('BACKDOOR_ENV', 'unknown')
    }
    
    return jsonify(response)

def check_database():
    """Check database connectivity."""
    try:
        db_url = current_app.config.get('SQLALCHEMY_DATABASE_URI')
        
        if not db_url:
            return {
                'connected': False,
                'error': 'No database URL configured'
            }
        
        # For SQLite, just check if the file exists
        if db_url.startswith('sqlite:///'):
            db_path = db_url.replace('sqlite:///', '')
            return {
                'connected': os.path.exists(db_path),
                'type': 'sqlite',
                'path': db_path
            }
        
        # For PostgreSQL, try to connect
        elif db_url.startswith('postgresql://'):
            start_time = time.time()
            conn = psycopg2.connect(db_url)
            conn.close()
            response_time = time.time() - start_time
            
            return {
                'connected': True,
                'type': 'postgresql',
                'response_time_ms': round(response_time * 1000, 2)
            }
        
        # Unsupported database type
        else:
            return {
                'connected': False,
                'error': f'Unsupported database type: {db_url.split("://")[0]}'
            }
    
    except Exception as e:
        return {
            'connected': False,
            'error': str(e)
        }

def check_model_service():
    """Check model service connectivity."""
    try:
        api_key = model_service.get_api_key()
        
        if not api_key:
            return {
                'available': False,
                'error': 'No API key configured'
            }
        
        # Check if the model service is initialized
        return {
            'available': True,
            'provider': 'Together AI',
            'model': model_service.default_model
        }
    
    except Exception as e:
        return {
            'available': False,
            'error': str(e)
        }

def check_vscode():
    """Check VS Code integration."""
    try:
        if not vscode_manager.initialized:
            return {
                'available': False,
                'error': 'VS Code integration not initialized'
            }
        
        return {
            'available': True,
            'workspaces_count': len(os.listdir(vscode_manager.workspaces_path)) if os.path.exists(vscode_manager.workspaces_path) else 0,
            'sessions_count': len(vscode_manager.active_sessions)
        }
    
    except Exception as e:
        return {
            'available': False,
            'error': str(e)
        }
