from flask import Blueprint, render_template, current_app, request, redirect, url_for, flash, session, jsonify, send_file
import os
import json
import uuid
from datetime import datetime
import zipfile
import io
import platform
import sys

bp = Blueprint('main', __name__)

# Initialize the OpenHands environment
def init_backdoor_env():
    """Initialize the Backdoor environment variables and settings."""
    os.environ['BACKDOOR_VERSION'] = '2.0.0'
    os.environ['BACKDOOR_ENV'] = 'production'
    os.environ['BACKDOOR_PLATFORM'] = platform.system()
    os.environ['BACKDOOR_PYTHON_VERSION'] = platform.python_version()
    os.environ['BACKDOOR_SYSTEM_VERSION'] = platform.version()
    os.environ['BACKDOOR_MACHINE'] = platform.machine()
    os.environ['BACKDOOR_NODE'] = platform.node()
    os.environ['BACKDOOR_RELEASE'] = platform.release()
    os.environ['BACKDOOR_PROCESSOR'] = platform.processor()
    
    # Create necessary directories
    os.makedirs('/tmp/backdoor', exist_ok=True)
    os.makedirs('/tmp/backdoor/tools', exist_ok=True)
    os.makedirs('/tmp/backdoor/cache', exist_ok=True)
    os.makedirs('/tmp/backdoor/logs', exist_ok=True)
    
    # Create a marker file to indicate Backdoor is initialized
    with open('/tmp/backdoor/initialized', 'w') as f:
        f.write(f"Backdoor initialized at {datetime.now().isoformat()}")
    
    return True

# Initialize OpenHands environment
init_backdoor_env()

@bp.route('/')
def index():
    from app.ai.model_service import model_service
    from app.ai.github_service import github_service
    
    # Get the session ID or create a new one
    session_id = session.get('session_id')
    if not session_id:
        session_id = str(uuid.uuid4())
        session['session_id'] = session_id
        
    # Create a session directory if it doesn't exist
    session_dir = os.path.join(current_app.config['CHAT_HISTORY_DIR'], session_id)
    os.makedirs(session_dir, exist_ok=True)
    
    # Load chat history if it exists
    chat_history = []
    history_file = os.path.join(session_dir, 'chat_history.json')
    if os.path.exists(history_file):
        try:
            with open(history_file, 'r') as f:
                chat_history = json.load(f)
        except json.JSONDecodeError:
            # If the file is corrupted, start with an empty history
            chat_history = []
    
    # Get API keys from session or config
    together_api_key = session.get('together_api_key') or current_app.config.get('TOGETHER_API_KEY', '')
    github_token = session.get('github_token') or current_app.config.get('GITHUB_TOKEN', '')
    
    # Set API keys in services
    if together_api_key:
        model_service.set_api_key(together_api_key)
    
    if github_token:
        github_service.set_token(github_token)
    
    # Get current repository if any
    current_repo = github_service.get_current_repo()
    
    # Get GitHub status
    github_status = github_service.get_status()
    
    # Get repository info if available
    repo_info = None
    if current_repo and github_status.get('connected'):
        repo_info = github_service.get_repo_info(current_repo)
        if isinstance(repo_info, dict) and "error" in repo_info:
            repo_info = None
    
    # Get model settings
    model_name = model_service.get_model()
    temperature = session.get('temperature', 0.7)
    max_tokens = session.get('max_tokens', 2048)
    streaming = session.get('streaming', True)
    
    # Get token usage
    token_usage = model_service.get_token_usage()
    
    # Check agent status
    agent_status = model_service.get_status()
    
    return render_template('index.html', 
                          chat_history=chat_history,
                          together_api_key=together_api_key,
                          github_token=github_token,
                          current_repo=current_repo,
                          repo_info=repo_info,
                          github_status=github_status,
                          model_name=model_name,
                          temperature=temperature,
                          max_tokens=max_tokens,
                          streaming=streaming,
                          token_usage=token_usage,
                          agent_status=agent_status)

@bp.route('/mentat-integration')
def mentat_integration():
    """Documentation page for Mentat integration features."""
    return render_template('mentat_integration.html')

@bp.route('/settings', methods=['GET', 'POST'])
def settings():
    from app.ai.model_service import model_service
    from app.ai.github_service import github_service
    
    if request.method == 'POST':
        # Get LLM provider selection
        llm_provider = request.form.get('llm_provider', 'together')
        current_app.config['LLM_PROVIDER'] = llm_provider
        session['llm_provider'] = llm_provider
        
        # Get common settings
        together_api_key = request.form.get('together_api_key', '')
        github_token = request.form.get('github_token', '')
        
        # Get Ollama-specific settings
        ollama_api_base = request.form.get('ollama_api_base', 'http://localhost:11434')
        ollama_model = request.form.get('ollama_model')
        
        # Get model settings
        model_name = request.form.get('model_name')
        temperature = request.form.get('temperature')
        max_tokens = request.form.get('max_tokens')
        streaming = 'streaming' in request.form  # Checkbox value
        
        # Store general settings
        current_app.config['GITHUB_TOKEN'] = github_token
        session['github_token'] = github_token
        
        # Process temperature and model settings
        if temperature:
            try:
                temperature = float(temperature)
                session['temperature'] = temperature
            except (ValueError, TypeError):
                pass
        
        # Process max tokens
        if max_tokens:
            try:
                max_tokens = int(max_tokens)
                session['max_tokens'] = max_tokens
            except (ValueError, TypeError):
                pass
        
        session['streaming'] = streaming
        
        # Provider-specific settings
        # -------------------------
        # Together AI
        together_model = request.form.get('together_model')
        together_streaming = 'together_streaming' in request.form
        
        current_app.config['TOGETHER_API_KEY'] = together_api_key
        session['together_api_key'] = together_api_key
        session['together_model'] = together_model
        session['together_streaming'] = together_streaming
        
        # OpenAI
        openai_api_key = request.form.get('openai_api_key', '')
        openai_api_base = request.form.get('openai_api_base', '')
        openai_model = request.form.get('openai_model')
        
        current_app.config['OPENAI_API_KEY'] = openai_api_key
        current_app.config['OPENAI_API_BASE'] = openai_api_base
        current_app.config['OPENAI_MODEL'] = openai_model
        session['openai_api_key'] = openai_api_key
        session['openai_api_base'] = openai_api_base
        session['openai_model'] = openai_model
        
        # Anthropic
        anthropic_api_key = request.form.get('anthropic_api_key', '')
        anthropic_api_base = request.form.get('anthropic_api_base', '')
        anthropic_model = request.form.get('anthropic_model')
        
        current_app.config['ANTHROPIC_API_KEY'] = anthropic_api_key
        current_app.config['ANTHROPIC_API_BASE'] = anthropic_api_base
        current_app.config['ANTHROPIC_MODEL'] = anthropic_model
        session['anthropic_api_key'] = anthropic_api_key
        session['anthropic_api_base'] = anthropic_api_base
        session['anthropic_model'] = anthropic_model
        
        # Google
        google_api_key = request.form.get('google_api_key', '')
        google_api_base = request.form.get('google_api_base', '')
        google_model = request.form.get('google_model')
        
        current_app.config['GOOGLE_API_KEY'] = google_api_key
        current_app.config['GOOGLE_API_BASE'] = google_api_base
        current_app.config['GOOGLE_MODEL'] = google_model
        session['google_api_key'] = google_api_key
        session['google_api_base'] = google_api_base
        session['google_model'] = google_model
        
        # Mistral
        mistral_api_key = request.form.get('mistral_api_key', '')
        mistral_api_base = request.form.get('mistral_api_base', '')
        mistral_model = request.form.get('mistral_model')
        
        current_app.config['MISTRAL_API_KEY'] = mistral_api_key
        current_app.config['MISTRAL_API_BASE'] = mistral_api_base
        current_app.config['MISTRAL_MODEL'] = mistral_model
        session['mistral_api_key'] = mistral_api_key
        session['mistral_api_base'] = mistral_api_base
        session['mistral_model'] = mistral_model
        
        # Cohere
        cohere_api_key = request.form.get('cohere_api_key', '')
        cohere_api_base = request.form.get('cohere_api_base', '')
        cohere_model = request.form.get('cohere_model')
        
        current_app.config['COHERE_API_KEY'] = cohere_api_key
        current_app.config['COHERE_API_BASE'] = cohere_api_base
        current_app.config['COHERE_MODEL'] = cohere_model
        session['cohere_api_key'] = cohere_api_key
        session['cohere_api_base'] = cohere_api_base
        session['cohere_model'] = cohere_model
        
        # Ollama
        ollama_setup_type = request.form.get('ollama_setup_type', 'colab')
        
        # Handle custom Ollama model if selected
        if ollama_model == 'custom':
            custom_ollama_model = request.form.get('custom_ollama_model', '')
            if custom_ollama_model:
                ollama_model = custom_ollama_model
            session['custom_ollama_model'] = custom_ollama_model
            current_app.config['CUSTOM_OLLAMA_MODEL'] = custom_ollama_model
            
        current_app.config['OLLAMA_API_BASE'] = ollama_api_base
        current_app.config['OLLAMA_MODEL'] = ollama_model
        current_app.config['OLLAMA_SETUP_TYPE'] = ollama_setup_type
        session['ollama_api_base'] = ollama_api_base
        session['ollama_model'] = ollama_model
        session['ollama_setup_type'] = ollama_setup_type
        
        # Custom Provider
        custom_api_key = request.form.get('custom_api_key', '')
        custom_api_base = request.form.get('custom_api_base', '')
        custom_model = request.form.get('custom_model', '')
        custom_streaming = 'custom_streaming' in request.form
        
        current_app.config['CUSTOM_API_KEY'] = custom_api_key
        current_app.config['CUSTOM_API_BASE'] = custom_api_base
        current_app.config['CUSTOM_MODEL'] = custom_model
        session['custom_api_key'] = custom_api_key
        session['custom_api_base'] = custom_api_base
        session['custom_model'] = custom_model
        session['custom_streaming'] = custom_streaming
        
        # Set the model name used by the model service based on provider
        if llm_provider == 'together' and together_model:
            model_service.set_model(together_model)
            session['model_name'] = together_model
        elif llm_provider == 'openai' and openai_model:
            model_service.set_model(openai_model)
            session['model_name'] = openai_model
        elif llm_provider == 'anthropic' and anthropic_model:
            model_service.set_model(anthropic_model)
            session['model_name'] = anthropic_model
        elif llm_provider == 'google' and google_model:
            model_service.set_model(google_model)
            session['model_name'] = google_model
        elif llm_provider == 'mistral' and mistral_model:
            model_service.set_model(mistral_model)
            session['model_name'] = mistral_model
        elif llm_provider == 'cohere' and cohere_model:
            model_service.set_model(cohere_model)
            session['model_name'] = cohere_model
        elif llm_provider == 'ollama' and ollama_model:
            model_service.set_model(ollama_model)
            session['model_name'] = ollama_model
        elif llm_provider == 'custom' and custom_model:
            model_service.set_model(custom_model)
            session['model_name'] = custom_model
        
        # Set provider-specific API key
        if llm_provider == 'together' and together_api_key:
            model_service.set_api_key(together_api_key)
        elif llm_provider == 'openai' and openai_api_key:
            model_service.set_api_key(openai_api_key)
        elif llm_provider == 'anthropic' and anthropic_api_key:
            model_service.set_api_key(anthropic_api_key)
        elif llm_provider == 'google' and google_api_key:
            model_service.set_api_key(google_api_key)
        elif llm_provider == 'mistral' and mistral_api_key:
            model_service.set_api_key(mistral_api_key)
        elif llm_provider == 'cohere' and cohere_api_key:
            model_service.set_api_key(cohere_api_key)
        elif llm_provider == 'custom' and custom_api_key:
            model_service.set_api_key(custom_api_key)
        
        # Set GitHub token
        if github_token:
            github_service.set_token(github_token)
        
        flash('Settings updated successfully!', 'success')
        return redirect(url_for('main.index'))
    
    # For GET requests, display the settings form
    llm_provider = session.get('llm_provider', current_app.config.get('LLM_PROVIDER', 'together'))
    together_api_key = session.get('together_api_key') or current_app.config.get('TOGETHER_API_KEY', '')
    github_token = session.get('github_token') or current_app.config.get('GITHUB_TOKEN', '')
    
    # Get GitHub status and repository info
    github_status = github_service.get_status()
    current_repo = github_service.get_current_repo()
    
    if current_repo:
        repo_info = github_service.get_repo_info(current_repo)
    else:
        repo_info = None
def download_chat():
    session_id = session.get('session_id')
    if not session_id:
        flash('No chat history found.', 'error')
        return redirect(url_for('main.index'))
    
    # Create a zip file in memory
    memory_file = io.BytesIO()
    with zipfile.ZipFile(memory_file, 'w') as zf:
        session_dir = os.path.join(current_app.config['CHAT_HISTORY_DIR'], session_id)
        history_file = os.path.join(session_dir, 'chat_history.json')
        
        if os.path.exists(history_file):
            # Add the chat history JSON file
            zf.write(history_file, 'chat_history.json')
            
            # Also create a formatted text version for easier reading
            try:
                with open(history_file, 'r') as f:
                    chat_history = json.load(f)
                
                text_content = "Backdoor AI Chat History\n"
                text_content += "=" * 30 + "\n\n"
                text_content += f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                
                for msg in chat_history:
                    role = msg.get('role', 'unknown')
                    content = msg.get('content', '')
                    timestamp = msg.get('timestamp', '')
                    
                    text_content += f"[{timestamp}] {role.upper()}:\n"
                    text_content += f"{content}\n\n"
                
                zf.writestr('chat_history.txt', text_content)
            except Exception as e:
                zf.writestr('error.txt', f"Error creating text version: {str(e)}")
        else:
            zf.writestr('empty.txt', 'No chat history found.')
    
    # Seek to the beginning of the file
    memory_file.seek(0)
    
    # Return the zip file
    return send_file(
        memory_file,
        mimetype='application/zip',
        as_attachment=True,
        download_name='backdoor_ai_chat_history.zip'
    )
