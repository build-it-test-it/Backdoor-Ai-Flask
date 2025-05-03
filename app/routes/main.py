from flask import Blueprint, render_template, current_app, request, redirect, url_for, flash, session, jsonify, send_file
import os
import json
import uuid
from datetime import datetime
import zipfile
import io

bp = Blueprint('main', __name__)

@bp.route('/')
def index():
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
    
    return render_template('index.html', 
                          chat_history=chat_history,
                          together_api_key=current_app.config.get('TOGETHER_API_KEY', ''),
                          github_token=current_app.config.get('GITHUB_TOKEN', ''))

@bp.route('/settings', methods=['GET', 'POST'])
def settings():
    if request.method == 'POST':
        # Update API keys
        together_api_key = request.form.get('together_api_key', '')
        github_token = request.form.get('github_token', '')
        
        # Store in app config
        current_app.config['TOGETHER_API_KEY'] = together_api_key
        current_app.config['GITHUB_TOKEN'] = github_token
        
        # Store in session for persistence
        session['together_api_key'] = together_api_key
        session['github_token'] = github_token
        
        flash('Settings updated successfully!', 'success')
        return redirect(url_for('main.index'))
    
    # For GET requests, display the settings form
    return render_template('settings.html',
                          together_api_key=current_app.config.get('TOGETHER_API_KEY', ''),
                          github_token=current_app.config.get('GITHUB_TOKEN', ''))

@bp.route('/download-chat')
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