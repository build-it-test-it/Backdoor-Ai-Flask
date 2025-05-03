from flask import Blueprint, request, jsonify, current_app, session
import requests
import json
import os
import subprocess
import sys
from datetime import datetime
import uuid

bp = Blueprint('api', __name__, url_prefix='/api')

@bp.route('/chat', methods=['POST'])
def chat():
    from app.ai.model_service import model_service
    from app.ai.context_provider import context_provider
    
    data = request.json
    
    # Get API key from session or request
    api_key = data.get('api_key') or session.get('together_api_key') or current_app.config.get('TOGETHER_API_KEY')
    if not api_key:
        return jsonify({
            'error': 'API key is required. Please set it in the settings.'
        }), 400
    
    # Set API key in model service
    model_service.set_api_key(api_key)
    
    # Get user message
    user_message = data.get('message', '')
    if not user_message:
        return jsonify({
            'error': 'Message is required'
        }), 400
    
    # Get chat history
    chat_history = data.get('history', [])
    
    # Get app context
    app_context = data.get('context', {})
    
    # Merge app context with our context
    context = context_provider.get_full_context()
    if app_context:
        # Add app-specific context
        context["app_context"] = app_context
    
    # Ensure session ID exists
    if 'session_id' not in session:
        session['session_id'] = str(uuid.uuid4())
    
    # Process the chat message
    try:
        result = model_service.process_chat(
            user_message=user_message,
            chat_history=chat_history,
            context=context
        )
        
        if not result.get("success", False):
            return jsonify({
                'error': result.get("error", "Unknown error"),
                'history': result.get("history", [])
            }), 400
        
        # Return the response
        return jsonify({
            'response': result.get("response", ""),
            'history': result.get("history", []),
            'interaction_id': result.get("interaction_id", ""),
            'commands': result.get("commands", []),
            'command_results': result.get("command_results", []),
            'tool_results': result.get("tool_results", [])
        })
    
    except Exception as e:
        return jsonify({
            'error': f"Error: {str(e)}"
        }), 500

@bp.route('/github', methods=['POST'])
def github():
    data = request.json
    
    # Get GitHub token from session or request
    github_token = data.get('github_token') or session.get('github_token') or current_app.config.get('GITHUB_TOKEN')
    if not github_token:
        return jsonify({
            'error': 'GitHub token is required. Please set it in the settings.'
        }), 400
    
    # Get the GitHub API endpoint
    endpoint = data.get('endpoint')
    if not endpoint:
        return jsonify({
            'error': 'GitHub API endpoint is required'
        }), 400
    
    # Get the HTTP method
    method = data.get('method', 'GET').upper()
    
    # Get the request body
    body = data.get('body')
    
    # Make the GitHub API request
    try:
        url = f"https://api.github.com/{endpoint.lstrip('/')}"
        
        headers = {
            "Authorization": f"token {github_token}",
            "Accept": "application/vnd.github.v3+json"
        }
        
        if method == 'GET':
            response = requests.get(url, headers=headers)
        elif method == 'POST':
            response = requests.post(url, headers=headers, json=body)
        elif method == 'PUT':
            response = requests.put(url, headers=headers, json=body)
        elif method == 'PATCH':
            response = requests.patch(url, headers=headers, json=body)
        elif method == 'DELETE':
            response = requests.delete(url, headers=headers)
        else:
            return jsonify({
                'error': f"Unsupported HTTP method: {method}"
            }), 400
        
        # Return the GitHub API response
        return jsonify(response.json()), response.status_code
    
    except Exception as e:
        return jsonify({
            'error': f"Error: {str(e)}"
        }), 500

@bp.route('/feedback', methods=['POST'])
def feedback():
    from app.ai.model_service import model_service
    
    data = request.json
    
    # Get interaction ID
    interaction_id = data.get('interaction_id')
    if not interaction_id:
        return jsonify({
            'error': 'Interaction ID is required'
        }), 400
    
    # Get rating
    rating = data.get('rating')
    if rating is None:
        return jsonify({
            'error': 'Rating is required'
        }), 400
    
    # Try to convert rating to int
    try:
        rating = int(rating)
    except ValueError:
        return jsonify({
            'error': 'Rating must be a number'
        }), 400
    
    # Validate rating range (1-5)
    if rating < 1 or rating > 5:
        return jsonify({
            'error': 'Rating must be between 1 and 5'
        }), 400
    
    # Get comment (optional)
    comment = data.get('comment')
    
    # Record feedback
    success = model_service.record_feedback(interaction_id, rating, comment)
    
    if not success:
        return jsonify({
            'error': 'Failed to record feedback. Interaction ID may be invalid.'
        }), 400
    
    return jsonify({
        'success': True,
        'message': 'Feedback recorded successfully'
    })

@bp.route('/track', methods=['POST'])
def track_behavior():
    from app.ai.behavior_tracker import behavior_tracker
    
    data = request.json
    
    # Get action
    action = data.get('action')
    if not action:
        return jsonify({
            'error': 'Action is required'
        }), 400
    
    # Get screen
    screen = data.get('screen')
    if not screen:
        return jsonify({
            'error': 'Screen is required'
        }), 400
    
    # Get duration (optional)
    duration = data.get('duration', 0)
    
    # Get details (optional)
    details = data.get('details', {})
    
    # Record behavior
    behavior = behavior_tracker.record_behavior(action, screen, duration, details)
    
    return jsonify({
        'success': True,
        'message': 'Behavior tracked successfully',
        'behavior_id': behavior.id
    })

@bp.route('/settings', methods=['POST'])
def update_settings():
    data = request.json
    
    # Update API keys
    together_api_key = data.get('together_api_key')
    github_token = data.get('github_token')
    
    if together_api_key is not None:
        current_app.config['TOGETHER_API_KEY'] = together_api_key
        session['together_api_key'] = together_api_key
    
    if github_token is not None:
        current_app.config['GITHUB_TOKEN'] = github_token
        session['github_token'] = github_token
    
    return jsonify({
        'success': True,
        'message': 'Settings updated successfully'
    })

@bp.route('/execute_bash', methods=['POST'])
def execute_bash():
    """Execute a bash command and return the result."""
    from app.ai.tools import tool_registry
    
    data = request.json
    
    # Get command
    command = data.get('command')
    if not command:
        return jsonify({
            'error': 'Command is required'
        }), 400
    
    # Get is_input flag
    is_input = data.get('is_input', 'false')
    
    # Execute the command
    result = tool_registry.execute_tool('execute_bash', command=command, is_input=is_input)
    
    return jsonify(result)

@bp.route('/file', methods=['GET', 'POST', 'PUT'])
def file_operations():
    """Handle file operations."""
    from app.ai.tools import tool_registry
    
    if request.method == 'GET':
        # View a file or directory
        path = request.args.get('path')
        if not path:
            return jsonify({
                'error': 'Path is required'
            }), 400
        
        view_range = request.args.get('view_range')
        if view_range:
            try:
                view_range = json.loads(view_range)
            except json.JSONDecodeError:
                view_range = None
        
        result = tool_registry.execute_tool('str_replace_editor', command='view', path=path, view_range=view_range)
        return jsonify(result)
    
    elif request.method == 'POST':
        # Create a file
        data = request.json
        
        path = data.get('path')
        if not path:
            return jsonify({
                'error': 'Path is required'
            }), 400
        
        file_text = data.get('file_text')
        if file_text is None:
            return jsonify({
                'error': 'File text is required'
            }), 400
        
        result = tool_registry.execute_tool('str_replace_editor', command='create', path=path, file_text=file_text)
        return jsonify(result)
    
    elif request.method == 'PUT':
        # Edit a file
        data = request.json
        
        path = data.get('path')
        if not path:
            return jsonify({
                'error': 'Path is required'
            }), 400
        
        command = data.get('command')
        if command not in ['str_replace', 'insert', 'undo_edit']:
            return jsonify({
                'error': 'Invalid command'
            }), 400
        
        if command == 'str_replace':
            old_str = data.get('old_str')
            if not old_str:
                return jsonify({
                    'error': 'old_str is required for str_replace command'
                }), 400
            
            new_str = data.get('new_str', '')
            
            result = tool_registry.execute_tool('str_replace_editor', command=command, path=path, old_str=old_str, new_str=new_str)
        
        elif command == 'insert':
            insert_line = data.get('insert_line')
            if insert_line is None:
                return jsonify({
                    'error': 'insert_line is required for insert command'
                }), 400
            
            new_str = data.get('new_str')
            if not new_str:
                return jsonify({
                    'error': 'new_str is required for insert command'
                }), 400
            
            result = tool_registry.execute_tool('str_replace_editor', command=command, path=path, insert_line=insert_line, new_str=new_str)
        
        elif command == 'undo_edit':
            result = tool_registry.execute_tool('str_replace_editor', command=command, path=path)
        
        return jsonify(result)
    
    return jsonify({
        'error': 'Invalid method'
    }), 405

@bp.route('/execute_python', methods=['POST'])
def execute_python():
    """Execute Python code and return the result."""
    from app.ai.tools import tool_registry
    
    data = request.json
    
    # Get code
    code = data.get('code')
    if not code:
        return jsonify({
            'error': 'Code is required'
        }), 400
    
    # Execute the code
    result = tool_registry.execute_tool('execute_ipython_cell', code=code)
    
    return jsonify(result)

@bp.route('/web_read', methods=['GET'])
def web_read():
    """Read content from a webpage."""
    from app.ai.tools import tool_registry
    
    # Get URL
    url = request.args.get('url')
    if not url:
        return jsonify({
            'error': 'URL is required'
        }), 400
    
    # Read the webpage
    result = tool_registry.execute_tool('web_read', url=url)
    
    return jsonify(result)

@bp.route('/browser', methods=['POST'])
def browser():
    """Interact with a browser."""
    from app.ai.tools import tool_registry
    
    data = request.json
    
    # Get code
    code = data.get('code')
    if not code:
        return jsonify({
            'error': 'Code is required'
        }), 400
    
    # Execute the browser code
    result = tool_registry.execute_tool('browser', code=code)
    
    return jsonify(result)

@bp.route('/think', methods=['POST'])
def think():
    """Log a thought."""
    from app.ai.tools import tool_registry
    
    data = request.json
    
    # Get thought
    thought = data.get('thought')
    if not thought:
        return jsonify({
            'error': 'Thought is required'
        }), 400
    
    # Log the thought
    result = tool_registry.execute_tool('think', thought=thought)
    
    return jsonify(result)

@bp.route('/finish', methods=['POST'])
def finish():
    """Signal task completion."""
    from app.ai.tools import tool_registry
    
    data = request.json
    
    # Get message
    message = data.get('message')
    if not message:
        return jsonify({
            'error': 'Message is required'
        }), 400
    
    # Get task_completed
    task_completed = data.get('task_completed', 'false')
    
    # Signal task completion
    result = tool_registry.execute_tool('finish', message=message, task_completed=task_completed)
    
    return jsonify(result)

@bp.route('/token-usage', methods=['GET'])
def token_usage():
    """Get the current token usage."""
    from app.ai.model_service import model_service
    
    # Get token usage from model service
    usage = model_service.get_token_usage()
    
    return jsonify({
        'success': True,
        'token_usage': usage
    })

@bp.route('/agent-status', methods=['GET'])
def agent_status():
    """Check if the agent is ready."""
    from app.ai.model_service import model_service
    
    # Check if API key is set
    api_key = model_service.get_api_key()
    
    # Check if OpenHands is initialized
    initialized_file = os.path.join(current_app.config['OPENHANDS_CONFIG_DIR'], 'initialized')
    is_initialized = os.path.exists(initialized_file)
    
    # Get token usage
    usage = model_service.get_token_usage()
    
    return jsonify({
        'success': True,
        'status': {
            'ready': bool(api_key) and is_initialized,
            'api_key_set': bool(api_key),
            'initialized': is_initialized,
            'token_usage': usage
        }
    })