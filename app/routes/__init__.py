# Import all route modules here
from app.routes import main, api, agents_api, enhanced_agents_api, health, vscode_api, code_agent_api, performance

# Register blueprints that aren't registered elsewhere
def register_blueprints(app):
    app.register_blueprint(performance.performance_bp)
