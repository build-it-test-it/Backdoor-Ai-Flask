from flask import Flask, session
from flask_cors import CORS
import os
import platform
import sys
import uuid
from datetime import datetime

def create_app():
    app = Flask(__name__)
    CORS(app, supports_credentials=True, origins="*")
    
    # Configure app
    app.config.from_mapping(
        SECRET_KEY=os.environ.get('SECRET_KEY', 'dev'),
        TOGETHER_API_KEY=os.environ.get('TOGETHER_API_KEY', ''),
        GITHUB_TOKEN=os.environ.get('GITHUB_TOKEN', ''),
        CHAT_HISTORY_DIR=os.path.join('/tmp', 'chat_history'),
        OPENHANDS_VERSION='2.0.0',
        OPENHANDS_ENV=os.environ.get('OPENHANDS_ENV', 'production'),
        OPENHANDS_PLATFORM=platform.system(),
        OPENHANDS_PYTHON_VERSION=platform.python_version(),
        OPENHANDS_SYSTEM_VERSION=platform.version(),
        OPENHANDS_MACHINE=platform.machine(),
        OPENHANDS_NODE=platform.node(),
        OPENHANDS_RELEASE=platform.release(),
        OPENHANDS_PROCESSOR=platform.processor(),
        OPENHANDS_TOOLS_DIR=os.path.join('/tmp', 'openhands', 'tools'),
        OPENHANDS_CACHE_DIR=os.path.join('/tmp', 'openhands', 'cache'),
        OPENHANDS_LOGS_DIR=os.path.join('/tmp', 'openhands', 'logs'),
        OPENHANDS_TEMP_DIR=os.path.join('/tmp', 'openhands', 'temp'),
        OPENHANDS_DATA_DIR=os.path.join('/tmp', 'openhands', 'data'),
        OPENHANDS_CONFIG_DIR=os.path.join('/tmp', 'openhands', 'config'),
        OPENHANDS_MODELS_DIR=os.path.join('/tmp', 'openhands', 'models'),
        OPENHANDS_PLUGINS_DIR=os.path.join('/tmp', 'openhands', 'plugins'),
        OPENHANDS_EXTENSIONS_DIR=os.path.join('/tmp', 'openhands', 'extensions'),
        OPENHANDS_TEMPLATES_DIR=os.path.join('/tmp', 'openhands', 'templates'),
        OPENHANDS_STATIC_DIR=os.path.join('/tmp', 'openhands', 'static'),
        OPENHANDS_UPLOADS_DIR=os.path.join('/tmp', 'openhands', 'uploads'),
        OPENHANDS_DOWNLOADS_DIR=os.path.join('/tmp', 'openhands', 'downloads'),
        OPENHANDS_BACKUPS_DIR=os.path.join('/tmp', 'openhands', 'backups'),
        OPENHANDS_SESSIONS_DIR=os.path.join('/tmp', 'openhands', 'sessions'),
    )
    
    # Ensure all directories exist
    for key, path in app.config.items():
        if key.startswith('OPENHANDS_') and key.endswith('_DIR'):
            os.makedirs(path, exist_ok=True)
    
    # Ensure the chat history directory exists
    os.makedirs(app.config['CHAT_HISTORY_DIR'], exist_ok=True)
    
    # Create a marker file to indicate OpenHands is initialized
    with open(os.path.join(app.config['OPENHANDS_CONFIG_DIR'], 'initialized'), 'w') as f:
        f.write(f"OpenHands initialized at {datetime.now().isoformat()}")
    
    # Register blueprints
    from app.routes import main, api
    app.register_blueprint(main.bp)
    app.register_blueprint(api.bp)
    
    # Initialize session ID middleware
    @app.before_request
    def ensure_session_id():
        if 'session_id' not in session:
            session['session_id'] = str(uuid.uuid4())
    
    return app