import json
import os
import requests
import uuid
from datetime import datetime
from flask import current_app, session
from typing import Any, Dict, List, Optional, Union

from app.ai.context_provider import context_provider
from app.ai.behavior_tracker import behavior_tracker
from app.ai.tools import tool_registry

class TogetherAIService:
    """Service for interacting with Together AI's API, inspired by OpenHands LLM implementation"""
    
    MODEL_ID = "meta-llama/Llama-3.3-70B-Instruct-Turbo-Free"
    API_URL = "https://api.together.xyz/v1/chat/completions"
    
    def __init__(self, api_key=None):
        self.api_key = api_key
        self.active_tools = {}  # Track active tool executions
        self.token_usage = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0
        }
    
    def set_api_key(self, api_key):
        """Set the API key"""
        self.api_key = api_key
    
    def get_api_key(self):
        """Get the API key from session if not set"""
        if not self.api_key:
            self.api_key = session.get('together_api_key')
        return self.api_key
        
    def get_token_usage(self):
        """Get the current token usage"""
        # Get from session if available
        session_tokens = session.get('token_usage')
        if session_tokens:
            return session_tokens
        return self.token_usage
        
    def update_token_usage(self, usage_data):
        """Update token usage with new data"""
        current_usage = self.get_token_usage()
        
        # Update counts
        current_usage["prompt_tokens"] += usage_data.get("prompt_tokens", 0)
        current_usage["completion_tokens"] += usage_data.get("completion_tokens", 0)
        current_usage["total_tokens"] = current_usage["prompt_tokens"] + current_usage["completion_tokens"]
        
        # Store in session and instance
        session['token_usage'] = current_usage
        self.token_usage = current_usage
        
        return current_usage
    
    def chat_completion(self, messages, temperature=0.7, max_tokens=1024, tools=None, tool_choice=None):
        """Get a chat completion from Together AI with optional function calling"""
        api_key = self.get_api_key()
        if not api_key:
            return {
                "error": "API key not set. Please configure your Together AI API key in settings."
            }
        
        # Add system message with context if not already present
        if not messages or messages[0].get('role') != 'system':
            system_message = {
                'role': 'system',
                'content': context_provider.get_system_message()
            }
            messages.insert(0, system_message)
        
        # Add context to user messages
        for i, message in enumerate(messages):
            if message.get('role') == 'user':
                # Add context as metadata
                if 'metadata' not in message:
                    message['metadata'] = {}
                message['metadata']['context'] = context_provider.get_full_context()
        
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": self.MODEL_ID,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        
        # Add tools if provided
        if tools:
            payload["tools"] = tools
        
        # Add tool_choice if provided
        if tool_choice:
            payload["tool_choice"] = tool_choice
        
        try:
            response = requests.post(
                self.API_URL,
                headers=headers,
                json=payload
            )
            
            if response.status_code == 200:
                response_data = response.json()
                
                # Track token usage if available in the response
                if "usage" in response_data:
                    self.update_token_usage(response_data["usage"])
                
                return response_data
            else:
                return {
                    "error": f"API request failed with status code {response.status_code}",
                    "details": response.text
                }
        except Exception as e:
            return {
                "error": f"Exception occurred: {str(e)}"
            }
    
    def process_chat(self, user_message, chat_history=None, context=None):
        """Process a chat message and handle all the context and tracking, similar to OpenHands implementation"""
        if chat_history is None:
            chat_history = self.load_chat_history()
        
        if context is None:
            context = context_provider.get_full_context()
        
        # Format messages for the API
        messages = []
        
        # Add system message
        system_message = {
            'role': 'system',
            'content': context_provider.get_system_message()
        }
        messages.append(system_message)
        
        # Add chat history
        for msg in chat_history:
            if msg.get('role') in ['user', 'assistant']:
                message_to_add = {
                    'role': msg.get('role'),
                    'content': msg.get('content')
                }
                
                # Include tool calls and results if present
                if msg.get('tool_calls'):
                    message_to_add['tool_calls'] = msg.get('tool_calls')
                
                if msg.get('tool_call_id'):
                    message_to_add['tool_call_id'] = msg.get('tool_call_id')
                    message_to_add['name'] = msg.get('name')
                
                messages.append(message_to_add)
        
        # Add the current user message
        messages.append({
            'role': 'user',
            'content': user_message
        })
        
        # Record user behavior
        behavior_tracker.record_behavior(
            action="chat",
            screen=context.get("current_screen", {}).get("screen_name", "Unknown"),
            details={"message": user_message}
        )
        
        # Get tool schemas
        tools = tool_registry.get_tool_schemas()
        
        # Call the API with tools
        response_data = self.chat_completion(messages, tools=tools)
        
        if "error" in response_data:
            error_message = response_data.get("error")
            
            # Save error to history
            error_msg = {
                'role': 'system',
                'content': f"Error: {error_message}",
                'timestamp': datetime.now().isoformat()
            }
            chat_history.append(error_msg)
            self.save_chat_history(chat_history)
            
            return {
                "success": False,
                "error": error_message,
                "history": chat_history
            }
        
        # Extract the assistant's response
        assistant_response = response_data.get('choices', [{}])[0].get('message', {})
        assistant_message = assistant_response.get('content', '')
        tool_calls = assistant_response.get('tool_calls', [])
        
        # Add user message to history
        user_msg = {
            'role': 'user',
            'content': user_message,
            'timestamp': datetime.now().isoformat()
        }
        chat_history.append(user_msg)
        
        # Add assistant response to history
        assistant_msg = {
            'role': 'assistant',
            'content': assistant_message,
            'timestamp': datetime.now().isoformat(),
        }
        
        # Add tool calls if present
        if tool_calls:
            assistant_msg['tool_calls'] = tool_calls
        
        chat_history.append(assistant_msg)
        
        # Save updated history
        self.save_chat_history(chat_history)
        
        # Record the interaction for learning
        interaction = behavior_tracker.record_interaction(
            user_message=user_message,
            ai_response=assistant_message,
            context=context
        )
        
        # Process tool calls if present
        tool_results = []
        if tool_calls:
            for tool_call in tool_calls:
                tool_call_id = tool_call.get('id')
                function = tool_call.get('function', {})
                tool_name = function.get('name')
                tool_args = json.loads(function.get('arguments', '{}'))
                
                # Execute the tool
                tool_result = tool_registry.execute_tool(tool_name, **tool_args)
                
                # Add tool result to history
                tool_result_msg = {
                    'role': 'tool',
                    'tool_call_id': tool_call_id,
                    'name': tool_name,
                    'content': json.dumps(tool_result),
                    'timestamp': datetime.now().isoformat()
                }
                chat_history.append(tool_result_msg)
                tool_results.append(tool_result)
            
            # Save updated history with tool results
            self.save_chat_history(chat_history)
            
            # If there are tool calls, make a follow-up API call to get the final response
            if tool_results:
                # Call the API again with the tool results
                follow_up_response = self.chat_completion(chat_history)
                
                if "error" not in follow_up_response:
                    # Extract the follow-up response
                    follow_up_message = follow_up_response.get('choices', [{}])[0].get('message', {}).get('content', '')
                    
                    # Add follow-up response to history
                    follow_up_msg = {
                        'role': 'assistant',
                        'content': follow_up_message,
                        'timestamp': datetime.now().isoformat()
                    }
                    chat_history.append(follow_up_msg)
                    
                    # Update the assistant message for the return value
                    assistant_message = follow_up_message
                    
                    # Save updated history
                    self.save_chat_history(chat_history)
        
        # Extract and process any commands in the response (legacy support)
        commands = context_provider.extract_commands(assistant_message)
        command_results = []
        
        if commands:
            command_results = context_provider.process_commands(commands)
            
            # Add command results to history if any
            if command_results:
                command_msg = {
                    'role': 'system',
                    'content': "\n".join(command_results),
                    'timestamp': datetime.now().isoformat()
                }
                chat_history.append(command_msg)
                self.save_chat_history(chat_history)
        
        return {
            "success": True,
            "response": assistant_message,
            "history": chat_history,
            "interaction_id": interaction.id,
            "commands": commands,
            "command_results": command_results,
            "tool_results": tool_results
        }
    
    def record_feedback(self, interaction_id, rating, comment=None):
        """Record feedback for an interaction"""
        success = behavior_tracker.record_feedback(interaction_id, rating, comment)
        return success
    
    def save_chat_history(self, messages):
        """Save chat history to disk"""
        session_id = session.get('session_id')
        if not session_id:
            return False
        
        session_dir = os.path.join(current_app.config['CHAT_HISTORY_DIR'], session_id)
        os.makedirs(session_dir, exist_ok=True)
        
        history_file = os.path.join(session_dir, 'chat_history.json')
        
        # Add timestamp to each message if not present
        for message in messages:
            if 'timestamp' not in message:
                message['timestamp'] = datetime.now().isoformat()
        
        with open(history_file, 'w') as f:
            json.dump(messages, f, indent=2)
        
        return True
    
    def load_chat_history(self):
        """Load chat history from disk"""
        session_id = session.get('session_id')
        if not session_id:
            return []
        
        session_dir = os.path.join(current_app.config['CHAT_HISTORY_DIR'], session_id)
        history_file = os.path.join(session_dir, 'chat_history.json')
        
        if os.path.exists(history_file):
            try:
                with open(history_file, 'r') as f:
                    return json.load(f)
            except json.JSONDecodeError:
                return []
        
        return []

# Singleton instance
model_service = TogetherAIService()