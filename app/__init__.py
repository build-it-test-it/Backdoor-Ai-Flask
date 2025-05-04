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
        
        # LLM API keys
        TOGETHER_API_KEY=os.environ.get('TOGETHER_API_KEY', ''),
        TOGETHER_MODEL=os.environ.get('TOGETHER_MODEL', 'meta-llama/Llama-3.3-70B-Instruct-Turbo-Free'),
        TOGETHER_API_BASE=os.environ.get('TOGETHER_API_BASE', 'https://api.together.xyz/v1'),
        
        OPENAI_API_KEY=os.environ.get('OPENAI_API_KEY', ''),
        OPENAI_MODEL=os.environ.get('OPENAI_MODEL', 'gpt-3.5-turbo'),
        OPENAI_API_BASE=os.environ.get('OPENAI_API_BASE', 'https://api.openai.com/v1'),
        
        ANTHROPIC_API_KEY=os.environ.get('ANTHROPIC_API_KEY', ''),
        ANTHROPIC_MODEL=os.environ.get('ANTHROPIC_MODEL', 'claude-3-haiku-20240307'),
        ANTHROPIC_API_BASE=os.environ.get('ANTHROPIC_API_BASE', 'https://api.anthropic.com/v1'),
        
        GOOGLE_API_KEY=os.environ.get('GOOGLE_API_KEY', ''),
        GOOGLE_MODEL=os.environ.get('GOOGLE_MODEL', 'gemini-pro'),
        GOOGLE_API_BASE=os.environ.get('GOOGLE_API_BASE', 'https://generativelanguage.googleapis.com/v1beta'),
        
        MISTRAL_API_KEY=os.environ.get('MISTRAL_API_KEY', ''),
        MISTRAL_MODEL=os.environ.get('MISTRAL_MODEL', 'mistral-small'),
        MISTRAL_API_BASE=os.environ.get('MISTRAL_API_BASE', 'https://api.mistral.ai/v1'),
        
        COHERE_API_KEY=os.environ.get('COHERE_API_KEY', ''),
        COHERE_MODEL=os.environ.get('COHERE_MODEL', 'command'),
        COHERE_API_BASE=os.environ.get('COHERE_API_BASE', 'https://api.cohere.ai/v1'),
        
        CUSTOM_API_KEY=os.environ.get('CUSTOM_API_KEY', ''),
        CUSTOM_MODEL=os.environ.get('CUSTOM_MODEL', ''),
        CUSTOM_API_BASE=os.environ.get('CUSTOM_API_BASE', ''),
        
        # Default LLM provider
        LLM_PROVIDER=os.environ.get('LLM_PROVIDER', 'together'),
        
        # GitHub token
        GITHUB_TOKEN=os.environ.get('GITHUB_TOKEN', ''),
        
        # App configuration
        CHAT_HISTORY_DIR=os.path.join('/tmp', 'chat_history'),
        MCP_ENABLED=os.environ.get('MCP_ENABLED', 'true').lower() == 'true',
        MCP_LOG_LEVEL=os.environ.get('MCP_LOG_LEVEL', 'INFO'),
        SQLALCHEMY_DATABASE_URI=os.environ.get('DATABASE_URL', 'sqlite:///app.db'),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        BACKDOOR_VERSION='2.0.0',
        BACKDOOR_ENV=os.environ.get('BACKDOOR_ENV', 'production'),
        
        # System information
        BACKDOOR_PLATFORM=platform.system(),
        BACKDOOR_PYTHON_VERSION=platform.python_version(),
        BACKDOOR_SYSTEM_VERSION=platform.version(),
        BACKDOOR_MACHINE=platform.machine(),
        BACKDOOR_NODE=platform.node(),
        BACKDOOR_RELEASE=platform.release(),
        BACKDOOR_PROCESSOR=platform.processor(),
        
        # Docker configuration
        BACKDOOR_DOCKER_ENABLED=os.environ.get('BACKDOOR_DOCKER_ENABLED', 'true').lower() == 'true',
        BACKDOOR_DOCKER_IMAGE=os.environ.get('BACKDOOR_DOCKER_IMAGE', 'backdoor/runtime:latest'),
        BACKDOOR_DOCKER_NETWORK=os.environ.get('BACKDOOR_DOCKER_NETWORK', 'backdoor-network'),
        
        # Directory paths
        BACKDOOR_TOOLS_DIR=os.path.join('/tmp', 'backdoor', 'tools'),
        BACKDOOR_CACHE_DIR=os.path.join('/tmp', 'backdoor', 'cache'),
        BACKDOOR_LOGS_DIR=os.path.join('/tmp', 'backdoor', 'logs'),
        BACKDOOR_TEMP_DIR=os.path.join('/tmp', 'backdoor', 'temp'),
        BACKDOOR_DATA_DIR=os.path.join('/tmp', 'backdoor', 'data'),
        BACKDOOR_CONFIG_DIR=os.path.join('/tmp', 'backdoor', 'config'),
        BACKDOOR_MODELS_DIR=os.path.join('/tmp', 'backdoor', 'models'),
        BACKDOOR_PLUGINS_DIR=os.path.join('/tmp', 'backdoor', 'plugins'),
        BACKDOOR_EXTENSIONS_DIR=os.path.join('/tmp', 'backdoor', 'extensions'),
        BACKDOOR_TEMPLATES_DIR=os.path.join('/tmp', 'backdoor', 'templates'),
        BACKDOOR_STATIC_DIR=os.path.join('/tmp', 'backdoor', 'static'),
        BACKDOOR_UPLOADS_DIR=os.path.join('/tmp', 'backdoor', 'uploads'),
        BACKDOOR_DOWNLOADS_DIR=os.path.join('/tmp', 'backdoor', 'downloads'),
        BACKDOOR_BACKUPS_DIR=os.path.join('/tmp', 'backdoor', 'backups'),
        BACKDOOR_SESSIONS_DIR=os.path.join('/tmp', 'backdoor', 'sessions'),
        BACKDOOR_MICROAGENTS_DIR=os.path.join('/tmp', 'backdoor', 'microagents'),
    )
    
    # Handle Render.com's DATABASE_URL format (postgres:// to postgresql://)
    if app.config['SQLALCHEMY_DATABASE_URI'] and app.config['SQLALCHEMY_DATABASE_URI'].startswith('postgres://'):
        app.config['SQLALCHEMY_DATABASE_URI'] = app.config['SQLALCHEMY_DATABASE_URI'].replace('postgres://', 'postgresql://', 1)
    
    # Ensure all directories exist
    for key, path in app.config.items():
        if key.startswith('BACKDOOR_') and key.endswith('_DIR'):
            os.makedirs(path, exist_ok=True)
    
    # Ensure the chat history directory exists
    os.makedirs(app.config['CHAT_HISTORY_DIR'], exist_ok=True)
    
    # Create a marker file to indicate Backdoor is initialized
    with open(os.path.join(app.config['BACKDOOR_CONFIG_DIR'], 'initialized'), 'w') as f:
        f.write(f"Backdoor initialized at {datetime.now().isoformat()}")
    
    # Initialize database
    from app.database import init_app as init_db, db
    from flask_migrate import Migrate
    init_db(app)
    migrate = Migrate(app, db)
    
    # Register blueprints
    from app.routes import main, api, agents_api, vscode_api, health, enhanced_agents_api, code_agent_api, backdoor_api, ollama_api
    from app.ai import mcp_routes, mcp_routes_enhanced
    app.register_blueprint(main.bp)
    app.register_blueprint(api.bp)
    app.register_blueprint(mcp_routes.bp)
    app.register_blueprint(mcp_routes_enhanced.bp)
    app.register_blueprint(agents_api.bp)
    app.register_blueprint(vscode_api.bp)
    app.register_blueprint(health.bp)
    app.register_blueprint(enhanced_agents_api.bp)
    app.register_blueprint(code_agent_api.bp)
    app.register_blueprint(backdoor_api.bp)
    app.register_blueprint(ollama_api.bp)
    
    # Initialize session ID middleware
    @app.before_request
    def ensure_session_id():
        if 'session_id' not in session:
            session['session_id'] = str(uuid.uuid4())
    
    # Import all models to ensure they're registered with SQLAlchemy
    with app.app_context():
        from app.ai.mcp_models import ContextItem, Agent, ToolUsage, ToolResult, Task
        if app.config['SQLALCHEMY_DATABASE_URI'].startswith('sqlite:'):
            db.create_all()
            print(f"Created SQLite database tables at {app.config['SQLALCHEMY_DATABASE_URI']}")
    
    return app
