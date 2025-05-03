import json
import os
import platform
import uuid
from datetime import datetime
from flask import request, session, current_app

from app.ai.behavior_tracker import behavior_tracker

class AppContext:
    """Provides context about the application state, inspired by Backdoor-signer's AppContextManager"""
    
    @staticmethod
    def get_app_info():
        """Get basic app information"""
        return {
            "app_name": "Backdoor AI",
            "app_version": "1.0.0",
            "platform": platform.system(),
            "platform_version": platform.version(),
            "python_version": platform.python_version(),
            "user_agent": request.headers.get("User-Agent", "Unknown")
        }
    
    @staticmethod
    def get_current_screen():
        """Get information about the current screen"""
        path = request.path
        screen_name = "Unknown"
        
        if path == "/":
            screen_name = "Home"
        elif path == "/settings":
            screen_name = "Settings"
        elif path.startswith("/api/"):
            screen_name = "API"
        
        return {
            "screen_name": screen_name,
            "path": path,
            "query_params": dict(request.args),
            "timestamp": datetime.now().isoformat()
        }
    
    @staticmethod
    def get_user_info():
        """Get information about the current user"""
        return {
            "session_id": session.get("session_id", "Unknown"),
            "has_together_api_key": bool(session.get("together_api_key")),
            "has_github_token": bool(session.get("github_token")),
            "ip_address": request.remote_addr,
            "last_active": datetime.now().isoformat()
        }
    
    @staticmethod
    def get_command_context():
        """Get context for command processing, similar to Backdoor-signer's command processing"""
        return {
            "available_commands": [
                "navigate",
                "search",
                "download",
                "help",
                "settings"
            ],
            "current_screen": AppContext.get_current_screen()["screen_name"]
        }

class ContextProvider:
    """Provides rich context to the AI model, inspired by Backdoor-signer's CustomAIContextProvider"""
    
    @staticmethod
    def get_full_context():
        """Get the full context for the AI model"""
        app_info = AppContext.get_app_info()
        current_screen = AppContext.get_current_screen()
        user_info = AppContext.get_user_info()
        command_context = AppContext.get_command_context()
        recent_behaviors = [b.to_dict() for b in behavior_tracker.get_recent_behaviors(5)]
        recent_interactions = [i.to_dict() for i in behavior_tracker.get_recent_interactions(3)]
        
        return {
            "app_info": app_info,
            "current_screen": current_screen,
            "user_info": user_info,
            "command_context": command_context,
            "recent_behaviors": recent_behaviors,
            "recent_interactions": recent_interactions,
            "timestamp": datetime.now().isoformat()
        }
    
    @staticmethod
    def get_system_message():
        """Get the system message for the AI model, based on Backdoor-signer's welcome message"""
        return """You are Backdoor AI, an AI assistant integrated into the Backdoor application. 
Your primary role is to assist users with app signing, source management, and other app-related tasks.

You can:
1. Help users understand and navigate the Backdoor app
2. Assist with GitHub operations like creating pull requests
3. Provide guidance on app signing and source management
4. Answer questions about the app's features and functionality
5. Process commands in square brackets like [navigate to:settings]

Always be helpful, accurate, and security-conscious. When users ask you to perform actions, 
explain what you're doing and why. If a user requests something potentially harmful, 
explain the risks and suggest safer alternatives.

You have access to the user's current context within the application, including their recent actions,
current screen, and application state. Use this information to provide more relevant assistance.

When appropriate, you can use command syntax in your responses:
- [navigate to:screen_name] - Navigate to a specific screen
- [search:query] - Search for something
- [download:item_name] - Download an item
- [help:topic] - Provide help on a specific topic
"""
    
    @staticmethod
    def extract_commands(response):
        """Extract commands from AI response, similar to Backdoor-signer's implementation"""
        import re
        pattern = r'\[([^:]+):([^\]]+)\]'
        commands = []
        
        matches = re.finditer(pattern, response)
        for match in matches:
            if match.group(1) and match.group(2):
                commands.append((match.group(1), match.group(2)))
        
        return commands
    
    @staticmethod
    def process_commands(commands):
        """Process commands extracted from AI response"""
        results = []
        
        for command, parameter in commands:
            if command == "navigate":
                results.append(f"Navigation to {parameter} requested")
            elif command == "search":
                results.append(f"Search for {parameter} requested")
            elif command == "download":
                results.append(f"Download of {parameter} requested")
            elif command == "help":
                results.append(f"Help requested for {parameter}")
            elif command == "settings":
                results.append(f"Settings adjustment for {parameter} requested")
            else:
                results.append(f"Unknown command: {command}")
        
        return results

# Singleton instance
context_provider = ContextProvider()