from flask import Flask
from flask_cors import CORS
import os

def create_app():
    app = Flask(__name__)
    CORS(app)
    
    # Configure app
    app.config.from_mapping(
        SECRET_KEY=os.environ.get('SECRET_KEY', 'dev'),
        TOGETHER_API_KEY=os.environ.get('TOGETHER_API_KEY', ''),
        GITHUB_TOKEN=os.environ.get('GITHUB_TOKEN', ''),
        CHAT_HISTORY_DIR=os.path.join('/tmp', 'chat_history'),
    )
    
    # Ensure the chat history directory exists
    os.makedirs(app.config['CHAT_HISTORY_DIR'], exist_ok=True)
    
    # Register blueprints
    from app.routes import main, api
    app.register_blueprint(main.bp)
    app.register_blueprint(api.bp)
    
    return app