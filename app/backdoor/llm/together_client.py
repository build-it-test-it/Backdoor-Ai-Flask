"""
Together AI client for Backdoor.
"""
import json
import os
import time
from typing import Any, Dict, List, Optional, Union

import httpx
from flask import current_app, session

from app.backdoor.core.config import LLMConfig
from app.backdoor.core.exceptions import (
    LLMInvalidRequestError,
    LLMNoResponseError,
    LLMRateLimitError,
    LLMTimeoutError,
)
from app.backdoor.core.logger import get_logger

logger = get_logger("llm.together_client")

class TogetherClient:
    """Client for Together AI API."""
    
    DEFAULT_MODEL = "meta-llama/Llama-3.3-70B-Instruct-Turbo-Free"
    API_URL = "https://api.together.xyz/v1/chat/completions"
    
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        """Initialize the Together AI client.
        
        Args:
            api_key: The API key for Together AI.
            model: The model to use.
        """
        self.api_key = api_key
        self.model = model or self.DEFAULT_MODEL
        
        # Initialize token usage
        self.token_usage = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0
        }
        
        # Load token usage from session if available
        session_tokens = session.get('token_usage')
        if session_tokens:
            self.token_usage = session_tokens
    
    def set_api_key(self, api_key: str):
        """Set the API key.
        
        Args:
            api_key: The API key for Together AI.
        """
        self.api_key = api_key
        
        # Check if the API key is valid
        if api_key:
            self.check_api_key()
    
    def get_api_key(self) -> Optional[str]:
        """Get the API key.
        
        Returns:
            The API key.
        """
        if not self.api_key:
            self.api_key = current_app.config.get('TOGETHER_API_KEY') or session.get('together_api_key')
        return self.api_key
    
    def set_model(self, model: str) -> str:
        """Set the model.
        
        Args:
            model: The model to use.
            
        Returns:
            The model.
        """
        self.model = model or self.DEFAULT_MODEL
        session['model_id'] = self.model
        return self.model
    
    def get_model(self) -> str:
        """Get the model.
        
        Returns:
            The model.
        """
        if not hasattr(self, 'model') or not self.model:
            self.model = session.get('model_id') or self.DEFAULT_MODEL
        return self.model
    
    def check_api_key(self) -> bool:
        """Check if the API key is valid.
        
        Returns:
            True if the API key is valid, False otherwise.
        """
        api_key = self.get_api_key()
        if not api_key:
            return False
        
        # Make a simple request to check if the API key is valid
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        try:
            # Use a minimal request to check the API key
            data = {
                "model": self.get_model(),
                "messages": [{"role": "user", "content": "Hello"}],
                "max_tokens": 1
            }
            
            response = httpx.post(
                self.API_URL,
                headers=headers,
                json=data,
                timeout=10
            )
            
            if response.status_code == 200:
                return True
            elif response.status_code == 401:
                logger.error("Invalid API key")
                return False
            else:
                logger.error(f"API key check failed: {response.status_code} {response.text}")
                return False
            
        except Exception as e:
            logger.error(f"API key check failed: {e}")
            return False
    
    def get_token_usage(self) -> Dict[str, int]:
        """Get token usage.
        
        Returns:
            The token usage.
        """
        return self.token_usage
    
    def update_token_usage(self, usage: Dict[str, int]):
        """Update token usage.
        
        Args:
            usage: The token usage to add.
        """
        self.token_usage["prompt_tokens"] += usage.get("prompt_tokens", 0)
        self.token_usage["completion_tokens"] += usage.get("completion_tokens", 0)
        self.token_usage["total_tokens"] += usage.get("total_tokens", 0)
        
        # Update session
        session['token_usage'] = self.token_usage
    
    def get_status(self) -> Dict[str, Any]:
        """Get the current status of the model service.
        
        Returns:
            The status.
        """
        api_key = self.get_api_key()
        
        # Check if Backdoor is initialized
        backdoor_initialized = os.path.exists('/tmp/backdoor/initialized')
        
        # Get token usage
        token_usage = self.get_token_usage()
        
        return {
            "ready": bool(api_key) and backdoor_initialized,
            "initialized": backdoor_initialized,
            "api_key_set": bool(api_key),
            "model": self.get_model(),
            "token_usage": token_usage,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        }
    
    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        top_p: float = 0.95,
        frequency_penalty: float = 0.0,
        presence_penalty: float = 0.0,
        stop: Optional[List[str]] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[Union[str, Dict[str, Any]]] = None,
        stream: bool = False,
    ) -> Dict[str, Any]:
        """Generate a chat completion.
        
        Args:
            messages: The messages to generate a completion for.
            model: The model to use.
            temperature: The temperature to use.
            max_tokens: The maximum number of tokens to generate.
            top_p: The top_p to use.
            frequency_penalty: The frequency penalty to use.
            presence_penalty: The presence penalty to use.
            stop: The stop sequences to use.
            tools: The tools to use.
            tool_choice: The tool choice to use.
            stream: Whether to stream the response.
            
        Returns:
            The chat completion.
        """
        api_key = self.get_api_key()
        if not api_key:
            raise LLMInvalidRequestError("API key not set")
        
        model = model or self.get_model()
        
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "top_p": top_p,
            "frequency_penalty": frequency_penalty,
            "presence_penalty": presence_penalty,
            "stream": stream,
        }
        
        if stop:
            data["stop"] = stop
        
        if tools:
            data["tools"] = tools
        
        if tool_choice:
            data["tool_choice"] = tool_choice
        
        try:
            response = httpx.post(
                self.API_URL,
                headers=headers,
                json=data,
                timeout=60,
                stream=stream
            )
            
            if response.status_code != 200:
                if response.status_code == 401:
                    raise LLMInvalidRequestError("Invalid API key")
                elif response.status_code == 429:
                    raise LLMRateLimitError("Rate limit exceeded")
                else:
                    raise LLMInvalidRequestError(
                        f"API request failed: {response.status_code} {response.text}"
                    )
            
            if stream:
                return response
            
            result = response.json()
            
            # Update token usage
            if "usage" in result:
                self.update_token_usage(result["usage"])
            
            return result
            
        except httpx.TimeoutException:
            raise LLMTimeoutError("API request timed out")
        except Exception as e:
            raise LLMInvalidRequestError(f"API request failed: {e}")
    
    def stream_chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        top_p: float = 0.95,
        frequency_penalty: float = 0.0,
        presence_penalty: float = 0.0,
        stop: Optional[List[str]] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[Union[str, Dict[str, Any]]] = None,
    ):
        """Stream a chat completion.
        
        Args:
            messages: The messages to generate a completion for.
            model: The model to use.
            temperature: The temperature to use.
            max_tokens: The maximum number of tokens to generate.
            top_p: The top_p to use.
            frequency_penalty: The frequency penalty to use.
            presence_penalty: The presence penalty to use.
            stop: The stop sequences to use.
            tools: The tools to use.
            tool_choice: The tool choice to use.
            
        Yields:
            The chat completion chunks.
        """
        response = self.chat_completion(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p,
            frequency_penalty=frequency_penalty,
            presence_penalty=presence_penalty,
            stop=stop,
            tools=tools,
            tool_choice=tool_choice,
            stream=True,
        )
        
        # Process the streaming response
        try:
            for line in response.iter_lines():
                if not line:
                    continue
                
                if line.startswith(b"data: "):
                    line = line[6:]  # Remove "data: " prefix
                    
                    if line.strip() == b"[DONE]":
                        break
                    
                    try:
                        chunk = json.loads(line)
                        yield chunk
                    except json.JSONDecodeError:
                        logger.error(f"Failed to parse JSON: {line}")
                        continue
        
        except Exception as e:
            logger.error(f"Error streaming response: {e}")
            raise LLMInvalidRequestError(f"Error streaming response: {e}")
        
        finally:
            response.close()