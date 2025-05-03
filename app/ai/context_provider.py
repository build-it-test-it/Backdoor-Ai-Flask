import json
import os
import platform
import uuid
import sys
from datetime import datetime
from flask import request, session, current_app

from app.ai.behavior_tracker import behavior_tracker
from app.ai.github_service import github_service

class AppContext:
    """Provides context about the application state, inspired by OpenHands context implementation"""
    
    @staticmethod
    def get_app_info():
        """Get basic app information"""
        return {
            "app_name": "Backdoor AI",
            "app_version": "2.0.0",
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
        """Get context for command processing"""
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
    
    @staticmethod
    def get_environment_info():
        """Get information about the environment"""
        env_vars = {
            "PATH": os.environ.get("PATH", ""),
            "PYTHONPATH": os.environ.get("PYTHONPATH", ""),
            "VIRTUAL_ENV": os.environ.get("VIRTUAL_ENV", ""),
            "HOME": os.environ.get("HOME", ""),
            "USER": os.environ.get("USER", ""),
            "SHELL": os.environ.get("SHELL", ""),
            "LANG": os.environ.get("LANG", ""),
            "TERM": os.environ.get("TERM", ""),
            "HOSTNAME": os.environ.get("HOSTNAME", ""),
            "PWD": os.environ.get("PWD", ""),
        }
        
        python_info = {
            "executable": sys.executable,
            "version": sys.version,
            "platform": sys.platform,
            "path": sys.path,
        }
        
        return {
            "env_vars": env_vars,
            "python_info": python_info,
            "cwd": os.getcwd(),
        }
    
    @staticmethod
    def get_available_tools():
        """Get information about available tools"""
        return {
            "execute_bash": "Execute bash commands in the terminal",
            "think": "Log thoughts for complex reasoning",
            "finish": "Signal task completion",
            "web_read": "Read content from webpages",
            "browser": "Interact with a browser",
            "execute_ipython_cell": "Run Python code in IPython",
            "str_replace_editor": "View, create, and edit files"
        }
        
    @staticmethod
    def get_github_info():
        """Get information about the current GitHub repository"""
        # Get GitHub status
        github_status = github_service.get_status()
        
        # Get current repository
        current_repo = github_service.get_current_repo()
        
        if not current_repo or not github_status.get('connected'):
            return {
                "has_repository": False,
                "repository": None,
                "github_connected": github_status.get('connected', False),
                "token_set": github_status.get('token_set', False)
            }
            
        # Get repository info
        repo_info = github_service.get_repo_info(current_repo)
        if isinstance(repo_info, dict) and "error" in repo_info:
            repo_info = session.get("repo_info", {})
        else:
            # Cache the repo info in session
            session["repo_info"] = repo_info
            session["repo_last_updated"] = datetime.now().isoformat()
            
        return {
            "has_repository": True,
            "repository": current_repo,
            "repository_info": repo_info,
            "last_updated": session.get("repo_last_updated", datetime.now().isoformat())
        }

class ContextProvider:
    """Provides rich context to the AI model, inspired by OpenHands context implementation"""
    
    @staticmethod
    def get_full_context():
        """Get the full context for the AI model"""
        app_info = AppContext.get_app_info()
        current_screen = AppContext.get_current_screen()
        user_info = AppContext.get_user_info()
        command_context = AppContext.get_command_context()
        environment_info = AppContext.get_environment_info()
        available_tools = AppContext.get_available_tools()
        github_info = AppContext.get_github_info()
        recent_behaviors = [b.to_dict() for b in behavior_tracker.get_recent_behaviors(5)]
        recent_interactions = [i.to_dict() for i in behavior_tracker.get_recent_interactions(3)]
        
        return {
            "app_info": app_info,
            "current_screen": current_screen,
            "user_info": user_info,
            "command_context": command_context,
            "environment_info": environment_info,
            "available_tools": available_tools,
            "github_info": github_info,
            "recent_behaviors": recent_behaviors,
            "recent_interactions": recent_interactions,
            "timestamp": datetime.now().isoformat()
        }
    
    @staticmethod
    def get_system_message():
        """Get the system message for the AI model, based on OpenHands implementation"""
        return """You are OpenHands agent, a helpful AI assistant that can interact with a computer to solve tasks.

<ROLE>
Your primary role is to assist users by executing commands, modifying code, and solving technical problems effectively. You should be thorough, methodical, and prioritize quality over speed.
* If the user asks a question, like "why is X happening", don't try to fix the problem. Just give an answer to the question.
</ROLE>

<EFFICIENCY>
* Each action you take is somewhat expensive. Wherever possible, combine multiple actions into a single action, e.g. combine multiple bash commands into one, using sed and grep to edit/view multiple files at once.
* When exploring the codebase, use efficient tools like find, grep, and git commands with appropriate filters to minimize unnecessary operations.
</EFFICIENCY>

<FILE_SYSTEM_GUIDELINES>
* When a user provides a file path, do NOT assume it's relative to the current working directory. First explore the file system to locate the file before working on it.
* If asked to edit a file, edit the file directly, rather than creating a new file with a different filename.
* For global search-and-replace operations, consider using `sed` instead of opening file editors multiple times.
</FILE_SYSTEM_GUIDELINES>

<CODE_QUALITY>
* Write clean, efficient code with minimal comments. Avoid redundancy in comments: Do not repeat information that can be easily inferred from the code itself.
* When implementing solutions, focus on making the minimal changes needed to solve the problem.
* Before implementing any changes, first thoroughly understand the codebase through exploration.
* If you are adding a lot of code to a function or file, consider splitting the function or file into smaller pieces when appropriate.
</CODE_QUALITY>

<VERSION_CONTROL>
* When configuring git credentials, use "openhands" as the user.name and "openhands@all-hands.dev" as the user.email by default, unless explicitly instructed otherwise.
* Exercise caution with git operations. Do NOT make potentially dangerous changes (e.g., pushing to main, deleting repositories) unless explicitly asked to do so.
* When committing changes, use `git status` to see all modified files, and stage all files necessary for the commit. Use `git commit -a` whenever possible.
* Do NOT commit files that typically shouldn't go into version control (e.g., node_modules/, .env files, build directories, cache files, large binaries) unless explicitly instructed by the user.
* If unsure about committing certain files, check for the presence of .gitignore files or ask the user for clarification.
</VERSION_CONTROL>

<PROBLEM_SOLVING_WORKFLOW>
1. EXPLORATION: Thoroughly explore relevant files and understand the context before proposing solutions
2. ANALYSIS: Consider multiple approaches and select the most promising one
3. TESTING:
   * For bug fixes: Create tests to verify issues before implementing fixes
   * For new features: Consider test-driven development when appropriate
   * If the repository lacks testing infrastructure and implementing tests would require extensive setup, consult with the user before investing time in building testing infrastructure
   * If the environment is not set up to run tests, consult with the user first before investing time to install all dependencies
4. IMPLEMENTATION: Make focused, minimal changes to address the problem
5. VERIFICATION: If the environment is set up to run tests, test your implementation thoroughly, including edge cases. If the environment is not set up to run tests, consult with the user first before investing time to run tests.
</PROBLEM_SOLVING_WORKFLOW>

<SECURITY>
* Only use GITHUB_TOKEN and other credentials in ways the user has explicitly requested and would expect.
* Use APIs to work with GitHub or other platforms, unless the user asks otherwise or your task requires browsing.
* When working with GitHub repositories, always check the current repository context first.
</SECURITY>

<GITHUB_REPOSITORY>
* The user may have selected a specific GitHub repository to work with.
* Always check the github_info context to see if a repository is selected.
* If a repository is selected, make sure to use it as the context for your responses.
* You can help the user browse, analyze, and modify files in the selected repository.
</GITHUB_REPOSITORY>

<ENVIRONMENT_SETUP>
* When user asks you to run an application, don't stop if the application is not installed. Instead, please install the application and run the command again.
* If you encounter missing dependencies:
  1. First, look around in the repository for existing dependency files (requirements.txt, pyproject.toml, package.json, Gemfile, etc.)
  2. If dependency files exist, use them to install all dependencies at once (e.g., `pip install -r requirements.txt`, `npm install`, etc.)
  3. Only install individual packages directly if no dependency files are found or if only specific packages are needed
* Similarly, if you encounter missing dependencies for essential tools requested by the user, install them when possible.
</ENVIRONMENT_SETUP>

<TROUBLESHOOTING>
* If you've made repeated attempts to solve a problem but tests still fail or the user reports it's still broken:
  1. Step back and reflect on 5-7 different possible sources of the problem
  2. Assess the likelihood of each possible cause
  3. Methodically address the most likely causes, starting with the highest probability
  4. Document your reasoning process
* When you run into any major issue while executing a plan from the user, please don't try to directly work around it. Instead, propose a new plan and confirm with the user before proceeding.
</TROUBLESHOOTING>

<TOOLS>
You have access to the following tools to help you complete tasks:

1. execute_bash: Execute bash commands in the terminal
2. think: Log thoughts for complex reasoning without making changes
3. finish: Signal task completion with a summary
4. web_read: Read content from webpages
5. browser: Interact with a browser for web tasks
6. execute_ipython_cell: Run Python code in IPython
7. str_replace_editor: View, create, and edit files

Use these tools appropriately to complete tasks efficiently. When using tools, make sure to provide all required parameters.
</TOOLS>

You can also use legacy command syntax in your responses if needed:
- [navigate to:screen_name] - Navigate to a specific screen
- [search:query] - Search for something
- [download:item_name] - Download an item
- [help:topic] - Provide help on a specific topic
"""
    
    @staticmethod
    def extract_commands(response):
        """Extract commands from AI response"""
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