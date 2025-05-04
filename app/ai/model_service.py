import json
import os
import uuid
import time
import logging
from datetime import datetime
from flask import current_app, session
from typing import Any, Dict, List, Optional, Union

from app.ai.context_provider import context_provider
from app.ai.behavior_tracker import behavior_tracker
from app.ai.tools import tool_registry
from app.ai.mcp_server import mcp_server
from app.ai.mcp_tool_handler import mcp_tool_handler
from app.ai.mcp_agents import agent_manager, AgentRole
from app.backdoor.core.config import get_config
from app.backdoor.llm.multi_provider_client import MultiProviderLLMClient

# Set up logging
logger = logging.getLogger("model_service")

class UnifiedModelService:
    """
    Unified Model Service for Backdoor AI.
    This service integrates TogetherAI and MultiProviderLLMClient functionality
    to provide a consistent interface for LLM interactions throughout the application.
    """
    
    DEFAULT_MODEL = "meta-llama/Llama-3.3-70B-Instruct-Turbo-Free"
    
    def __init__(self, api_key=None):
        """Initialize the unified model service."""
        self.initialized = False
        self.ready = False
        
        # Initialize token usage
        self.token_usage = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0
        }
        
        # Initialize the Multi-Provider LLM Client
        try:
            config = get_config()
            self.llm_client = MultiProviderLLMClient(config)
            
            # Set API key if provided
            if api_key:
                if config.llm.provider == "together":
                    self.llm_client.update_config({"api_key": api_key})
            
            # Load token usage from session if available
            try:
                session_tokens = session.get('token_usage')
                if session_tokens:
                    self.token_usage = session_tokens
            except RuntimeError:
                # Working outside of request context
                pass
                
            self.initialized = True
            logger.info("Unified Model Service initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing Unified Model Service: {e}")
    
    def set_api_key(self, api_key, provider=None):
        """Set the API key for the specified provider."""
        if not provider:
            provider = self.llm_client.provider
            
        # Update the LLM client configuration
        self.llm_client.update_config({
            "provider": provider,
            "api_key": api_key
        })
        
        # Check if the API key is valid
        if self.check_api_key():
            session[f'{provider}_api_key'] = api_key
            return True
        return False
    
    def get_api_key(self, provider=None):
        """Get the API key for the specified provider."""
        if not provider:
            provider = self.llm_client.provider
            
        # Try to get from session if not in client
        if provider == self.llm_client.provider:
            return self.llm_client.api_key
            
        # Try to get from session
        return session.get(f'{provider}_api_key')
    
    def set_model(self, model_id, provider=None):
        """Set the model ID for the specified provider."""
        config_update = {"model": model_id}
        if provider:
            config_update["provider"] = provider
            
        self.llm_client.update_config(config_update)
        session['model_id'] = model_id
        session['provider'] = provider or self.llm_client.provider
        
        return model_id
    
    def get_model(self):
        """Get the current model ID."""
        return self.llm_client.model
    
    def get_provider(self):
        """Get the current provider."""
        return self.llm_client.provider
    
    def get_status(self):
        """Get the current status of the model service."""
        backdoor_initialized = os.path.exists('/tmp/backdoor/initialized')
        
        # Get token usage
        token_usage = self.get_token_usage()
        
        return {
            "ready": self.ready and backdoor_initialized and bool(self.llm_client.api_key),
            "initialized": self.initialized and backdoor_initialized,
            "api_key_set": bool(self.llm_client.api_key),
            "model": self.get_model(),
            "provider": self.get_provider(),
            "token_usage": token_usage,
            "backdoor_initialized": backdoor_initialized,
            "timestamp": datetime.now().isoformat()
        }
    
    def check_api_key(self):
        """Check if the API key is valid by making a test request."""
        try:
            # Simple test message
            messages = [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Hello"}
            ]
            
            # Use a small max_tokens to minimize token usage
            response = self.llm_client.completion(
                messages=messages,
                max_tokens=1
            )
            
            # Check if response is valid
            if response and "choices" in response:
                self.ready = True
                return True
            else:
                self.ready = False
                return False
        except Exception as e:
            logger.error(f"Error checking API key: {e}")
            self.ready = False
            return False
    
    def get_token_usage(self):
        """Get the current token usage."""
        # Get from session if available
        session_tokens = session.get('token_usage')
        if session_tokens:
            return session_tokens
        return self.token_usage
    
    def update_token_usage(self, usage_data):
        """Update token usage with new data."""
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
        """Get a chat completion from the configured LLM provider with optional function calling."""
        if not self.llm_client.api_key:
            return {
                "error": f"API key not set for provider {self.llm_client.provider}. Please configure your API key in settings."
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
        
        try:
            # Create completion arguments
            completion_args = {
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
            
            # Add tools if provided
            if tools:
                completion_args["functions"] = tools
            
            # Add tool_choice if provided
            if tool_choice:
                completion_args["function_call"] = tool_choice
            
            # Call the LLM client
            response = self.llm_client.completion(**completion_args)
            
            # Track token usage if available
            if "usage" in response:
                self.update_token_usage(response["usage"])
            
            return response
        except Exception as e:
            logger.error(f"Error in chat completion: {e}")
            return {
                "error": f"Exception occurred: {str(e)}"
            }
    
    def process_chat(self, user_message, chat_history=None, context=None):
        """Process a chat message and handle all the context and tracking."""
        if chat_history is None:
            chat_history = self.load_chat_history()
        
        # Use the MCP server for enhanced context management if available
        if context is None:
            try:
                # First try to get context from MCP server
                mcp_context = mcp_server.get_full_context()
                # Merge with traditional context
                standard_context = context_provider.get_full_context()
                
                # Use MCP context but fall back to standard values if needed
                context = standard_context
                if mcp_context and 'context' in mcp_context:
                    for context_type, items in mcp_context['context'].items():
                        if items:  # Only use non-empty context lists
                            # Map MCP context types to standard context structure
                            if context_type == 'user_info' and items:
                                context['user_info'] = items[0]  # Use most recent
                            elif context_type == 'behavior' and items:
                                context['recent_behaviors'] = items
                            elif context_type == 'interaction' and items:
                                context['recent_interactions'] = items
                            elif context_type == 'github' and items:
                                context['github_info'] = items[0]  # Use most recent
                            elif context_type == 'environment' and items:
                                context['environment_info'] = items[0]  # Use most recent
                
            except Exception as e:
                logger.error(f"Error getting MCP context: {str(e)}")
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
                    'content': msg.get('content', '')  # Ensure content is never None
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
        
        # Record user behavior in both systems for backwards compatibility
        # The MCP server provides enhanced context tracking
        try:
            # Track in the behavior tracker (legacy)
            behavior_tracker.record_behavior(
                action="chat",
                screen=context.get("current_screen", {}).get("screen_name", "Unknown"),
                details={"message": user_message}
            )
            
            # Also track in the MCP server (new system)
            mcp_server.record_user_behavior(
                action="chat",
                screen=context.get("current_screen", {}).get("screen_name", "Unknown"),
                details={"message": user_message}
            )
        except Exception as e:
            # Log but continue if behavior tracking fails
            logger.error(f"Error tracking behavior: {str(e)}")
        
        # Get tool schemas from MCP tool handler
        try:
            # Use MCP tool handler to get tool schemas
            tools = mcp_tool_handler.get_tools_schema()
            
            # If empty, fall back to the direct tool registry as a backup
            if not tools:
                tools = tool_registry.get_tool_schemas()
        except Exception as e:
            # Default to no tools if there's an error
            logger.error(f"Error getting tool schemas: {str(e)}")
            tools = None
        
        # Call the API with tools - with rate limit handling
        max_retries = 2
        retry_count = 0
        retry_delay = 1  # Start with 1 second delay
        
        while retry_count <= max_retries:
            try:
                # Call the API with tools
                response_data = self.chat_completion(messages, tools=tools)
                
                # Break the loop if successful
                if "error" not in response_data:
                    break
                
                # If rate limited, retry
                error_message = response_data.get("error", "")
                if "429" in error_message and retry_count < max_retries:
                    retry_count += 1
                    # Exponential backoff
                    time.sleep(retry_delay)
                    retry_delay *= 2
                    continue
                else:
                    # Other error or final retry failed
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
            except Exception as e:
                error_message = str(e)
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
            
            # Increment retry count if we get here
            retry_count += 1
        
        # Extract the assistant's response with proper error handling
        try:
            assistant_response = response_data.get('choices', [{}])[0].get('message', {})
            # Ensure we never have None for content
            assistant_message = assistant_response.get('content', '')
            if assistant_message is None:
                assistant_message = "I apologize, but I couldn't generate a response. Please try again."
            
            tool_calls = assistant_response.get('tool_calls', [])
        except Exception as e:
            # If there's an error extracting the response, provide a fallback
            assistant_message = "I apologize, but there was an error processing your request. Please try again."
            tool_calls = []
            logger.error(f"Error extracting assistant response: {str(e)}")
            logger.debug(f"Response data: {response_data}")
        
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
        
        # Save updated history with error handling
        try:
            self.save_chat_history(chat_history)
        except Exception as e:
            logger.error(f"Error saving chat history: {str(e)}")
            # Continue anyway - it's better to return a response with unsaved history
            # than to fail the entire request
        
        # Record the interaction for learning in both systems
        # Legacy behavior tracker
        interaction = behavior_tracker.record_interaction(
            user_message=user_message,
            ai_response=assistant_message,
            context=context
        )
        
        # Also record in the MCP server for enhanced context
        try:
            mcp_server.record_interaction(
                user_message=user_message,
                ai_response=assistant_message,
                context=context
            )
        except Exception as e:
            logger.error(f"Error recording interaction in MCP server: {str(e)}")
        
        # Process tool calls if present
        tool_results = []
        if tool_calls:
            for tool_call in tool_calls:
                tool_call_id = tool_call.get('id')
                function = tool_call.get('function', {})
                tool_name = function.get('name')
                tool_args = json.loads(function.get('arguments', '{}'))
                
                # Execute the tool through MCP tool handler
                session_id = session.get('session_id')
                
                # Try to get or create an agent for this session
                agent = agent_manager.get_default_agent(session_id)
                if not agent:
                    # Create a new agent for this session
                    agent = agent_manager.create_agent(
                        name="Tool Assistant",
                        role=AgentRole.ASSISTANT,
                        session_id=session_id
                    )
                
                # Execute tool through MCP with this agent
                tool_result = mcp_tool_handler.execute_tool(
                    tool_type=tool_name,
                    agent_id=agent.id,
                    **tool_args
                )
                
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
        """Record feedback for an interaction."""
        success = behavior_tracker.record_feedback(interaction_id, rating, comment)
        return success
    
    def save_chat_history(self, messages):
        """Save chat history to disk."""
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
        """Load chat history from disk."""
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
    
    def get_available_models(self):
        """Get a list of all available models from the LLM client."""
        return self.llm_client.get_available_models()
    
    def get_providers(self):
        """Get a list of all available providers."""
        config = get_config()
        providers = []
        for provider_id, provider_config in config.llm.providers.items():
            # Skip custom provider if no API base is set
            if provider_id == "custom" and not provider_config.api_base:
                continue
                
            providers.append({
                "id": provider_id,
                "name": provider_config.name,
                "api_base": provider_config.api_base,
                "default_model": provider_config.default_model,
                "models_count": len(provider_config.models),
            })
        
        return providers

# Singleton instance that uses LLMClient for all model interactions
model_service = UnifiedModelService()

# For backward compatibility
class TogetherAIService(UnifiedModelService):
    """Legacy class for backward compatibility."""
    pass