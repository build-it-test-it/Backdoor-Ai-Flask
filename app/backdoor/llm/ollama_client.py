"""
Ollama client for Backdoor.
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

logger = get_logger("llm.ollama_client")

class OllamaClient:
    """Client for interacting with Ollama API."""
    
    DEFAULT_MODEL = "llama4:latest"
    DEFAULT_API_BASE = "http://localhost:11434"
    
    def __init__(self, model: Optional[str] = None, api_base: Optional[str] = None):
        """Initialize the Ollama client.
        
        Args:
            model: The model to use.
            api_base: The base URL for the Ollama API.
        """
        self.model = model or self.DEFAULT_MODEL
        self.api_base = api_base or self.DEFAULT_API_BASE
        
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
    
    def set_api_base(self, api_base: str) -> str:
        """Set the API base URL.
        
        Args:
            api_base: The base URL for the Ollama API.
            
        Returns:
            The API base URL.
        """
        # Clean up the API base URL if needed
        if api_base:
            # Remove trailing slashes
            api_base = api_base.rstrip('/')
            
            # Ensure the URL has a scheme
            if not api_base.startswith(('http://', 'https://')):
                api_base = 'https://' + api_base
        
        self.api_base = api_base or self.DEFAULT_API_BASE
        session['ollama_api_base'] = self.api_base
        return self.api_base
    
    def get_api_base(self) -> str:
        """Get the API base URL.
        
        Returns:
            The API base URL.
        """
        if not hasattr(self, 'api_base') or not self.api_base:
            self.api_base = session.get('ollama_api_base') or self.DEFAULT_API_BASE
        return self.api_base
    
    def _get_api_url(self, endpoint: str) -> str:
        """Get the full API URL for a given endpoint.
        
        Args:
            endpoint: The API endpoint.
            
        Returns:
            The full API URL.
        """
        base_url = self.get_api_base()
        return f"{base_url}/{endpoint}"
    
    def check_connection(self) -> bool:
        """Check if Ollama is available.
        
        Returns:
            True if Ollama is available, False otherwise.
        """
        try:
            url = self._get_api_url("api/tags")
            response = httpx.get(url, timeout=5)
            if response.status_code == 200:
                return True
            else:
                logger.error(f"Ollama not available. Status code: {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"Error checking Ollama connection: {e}")
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
    
    def _estimate_token_usage(self, prompt: str, response: str) -> Dict[str, int]:
        """Estimate token usage based on text length.
        
        This is a very rough estimation as Ollama doesn't return token counts.
        
        Args:
            prompt: The prompt text.
            response: The response text.
            
        Returns:
            Estimated token usage.
        """
        # Very rough estimation: ~1 token per 4 characters
        prompt_chars = len(prompt)
        response_chars = len(response)
        
        prompt_tokens = prompt_chars // 4
        completion_tokens = response_chars // 4
        
        return {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens
        }
    
    def get_status(self) -> Dict[str, Any]:
        """Get the current status of the Ollama service.
        
        Returns:
            The status.
        """
        # Check if Ollama is available
        ollama_available = self.check_connection()
        
        # Get token usage
        token_usage = self.get_token_usage()
        
        return {
            "ready": ollama_available,
            "initialized": ollama_available,
            "model": self.get_model(),
            "api_base": self.get_api_base(),
            "token_usage": token_usage,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        }
    
    def get_available_models(self) -> List[Dict[str, Any]]:
        """Get a list of available models.
        
        Returns:
            A list of models.
        """
        try:
            url = self._get_api_url("api/tags")
            response = httpx.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                models = []
                
                for model in data.get("models", []):
                    models.append({
                        "id": model.get("name"),
                        "name": model.get("name"),
                        "size": model.get("size"),
                        "modified_at": model.get("modified_at"),
                        "installed": True,
                        "provider": "ollama"
                    })
                
                # Add recommended models if not already in the list
                recommended_models = [
                    "llama4:latest", 
                    "llama4-8b:latest", 
                    "llama4-code:latest",
                    "llama4-tiny:latest",
                    "mistral:latest",
                    "gemma:latest"
                ]
                
                model_ids = [model["id"] for model in models]
                
                for rec_model in recommended_models:
                    if rec_model not in model_ids:
                        models.append({
                            "id": rec_model,
                            "name": rec_model,
                            "size": None,
                            "modified_at": None,
                            "installed": False,
                            "provider": "ollama",
                            "recommended": True
                        })
                
                return models
            else:
                logger.error(f"Failed to get models from Ollama. Status code: {response.status_code}")
                return []
        except Exception as e:
            logger.error(f"Error getting models from Ollama: {e}")
            return []
    
    def generate(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        top_p: Optional[float] = None,
        frequency_penalty: Optional[float] = None,
        presence_penalty: Optional[float] = None,
        stop: Optional[List[str]] = None,
        stream: bool = False,
    ) -> Dict[str, Any]:
        """Generate a response from Ollama.
        
        Args:
            messages: List of message objects with role and content.
            model: The model to use.
            temperature: The temperature to use for sampling.
            max_tokens: The maximum number of tokens to generate.
            top_p: The top-p value to use for sampling.
            frequency_penalty: The frequency penalty to use.
            presence_penalty: The presence penalty to use.
            stop: The stop sequences to use.
            stream: Whether to stream the response.
            
        Returns:
            The generation response.
        """
        model = model or self.get_model()
        url = self._get_api_url("api/chat")
        
        # Convert messages to Ollama format
        prompt = self._convert_messages_to_prompt(messages)
        
        # Build the request payload
        payload = {
            "model": model,
            "messages": messages,
            "options": {
                "temperature": temperature,
            }
        }
        
        # Add optional parameters
        if max_tokens:
            payload["options"]["num_predict"] = max_tokens
        
        if stop:
            payload["options"]["stop"] = stop
        
        if top_p:
            payload["options"]["top_p"] = top_p
            
        if frequency_penalty:
            payload["options"]["frequency_penalty"] = frequency_penalty
        
        if presence_penalty:
            payload["options"]["presence_penalty"] = presence_penalty
        
        # Set stream parameter
        payload["stream"] = stream
        
        try:
            if stream:
                # For streaming, return the response object directly
                response = httpx.post(url, json=payload, timeout=60, stream=True)
                return response
            else:
                # For non-streaming, process the response
                response = httpx.post(url, json=payload, timeout=60)
                
                if response.status_code == 200:
                    result = response.json()
                    
                    # Convert to OpenAI-like format for compatibility
                    openai_format = self._convert_to_openai_format(result, messages, model)
                    
                    # Estimate token usage
                    prompt_text = prompt if isinstance(prompt, str) else ""
                    response_text = result.get("message", {}).get("content", "")
                    usage = self._estimate_token_usage(prompt_text, response_text)
                    self.update_token_usage(usage)
                    
                    # Add usage to the response
                    openai_format["usage"] = usage
                    
                    return openai_format
                else:
                    error_msg = f"API request failed with status code {response.status_code}: {response.text}"
                    logger.error(error_msg)
                    raise LLMInvalidRequestError(error_msg)
                
        except httpx.TimeoutException as e:
            raise LLMTimeoutError(f"Request to Ollama timed out: {e}")
        except Exception as e:
            logger.error(f"Error generating response from Ollama: {e}")
            raise LLMInvalidRequestError(f"Error generating response: {e}")
    
    def _convert_messages_to_prompt(self, messages: List[Dict[str, str]]) -> str:
        """Convert a list of messages to a prompt string.
        
        Args:
            messages: List of message objects with role and content.
            
        Returns:
            The prompt string.
        """
        prompt = ""
        
        for message in messages:
            role = message.get("role", "").lower()
            content = message.get("content", "")
            
            if role == "system":
                prompt += f"<s>[INST] <<SYS>>\n{content}\n<</SYS>>\n\n"
            elif role == "user":
                if prompt:
                    prompt += f"{content} [/INST]"
                else:
                    prompt += f"<s>[INST] {content} [/INST]"
            elif role == "assistant":
                prompt += f" {content} </s>"
                
                # Start a new exchange
                if messages.index(message) < len(messages) - 1:
                    prompt += "\n<s>[INST] "
        
        return prompt
    
    def _convert_to_openai_format(
        self, 
        ollama_response: Dict[str, Any],
        messages: List[Dict[str, str]],
        model: str
    ) -> Dict[str, Any]:
        """Convert Ollama response to OpenAI format for compatibility.
        
        Args:
            ollama_response: The response from Ollama.
            messages: The messages sent to Ollama.
            model: The model used.
            
        Returns:
            The response in OpenAI format.
        """
        content = ollama_response.get("message", {}).get("content", "")
        
        return {
            "id": f"ollama-{int(time.time())}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": content
                    },
                    "finish_reason": "stop"
                }
            ]
        }
    
    def stream_chat(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        top_p: Optional[float] = None,
        frequency_penalty: Optional[float] = None,
        presence_penalty: Optional[float] = None,
        stop: Optional[List[str]] = None,
    ):
        """Stream a chat response from Ollama.
        
        Args:
            messages: List of message objects with role and content.
            model: The model to use.
            temperature: The temperature to use for sampling.
            max_tokens: The maximum number of tokens to generate.
            top_p: The top-p value to use for sampling.
            frequency_penalty: The frequency penalty to use.
            presence_penalty: The presence penalty to use.
            stop: The stop sequences to use.
            
        Yields:
            The streaming response chunks.
        """
        response = self.generate(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p,
            frequency_penalty=frequency_penalty,
            presence_penalty=presence_penalty,
            stop=stop,
            stream=True
        )
        
        # Process the streaming response
        try:
            full_content = ""
            
            for line in response.iter_lines():
                if not line:
                    continue
                
                try:
                    chunk = json.loads(line)
                    
                    # Get the content delta
                    if "message" in chunk and "content" in chunk["message"]:
                        content_delta = chunk["message"]["content"]
                        full_content += content_delta
                        
                        # Create a streaming response chunk in OpenAI format
                        yield {
                            "id": f"ollama-{int(time.time())}",
                            "object": "chat.completion.chunk",
                            "created": int(time.time()),
                            "model": model or self.get_model(),
                            "choices": [
                                {
                                    "index": 0,
                                    "delta": {
                                        "content": content_delta
                                    },
                                    "finish_reason": None
                                }
                            ]
                        }
                    
                    # If this is the final message
                    if chunk.get("done", False):
                        # Final chunk
                        yield {
                            "id": f"ollama-{int(time.time())}",
                            "object": "chat.completion.chunk",
                            "created": int(time.time()),
                            "model": model or self.get_model(),
                            "choices": [
                                {
                                    "index": 0,
                                    "delta": {},
                                    "finish_reason": "stop"
                                }
                            ]
                        }
                        
                        # Estimate token usage
                        prompt_text = self._convert_messages_to_prompt(messages)
                        usage = self._estimate_token_usage(prompt_text, full_content)
                        self.update_token_usage(usage)
                        
                except json.JSONDecodeError:
                    logger.error(f"Failed to parse JSON: {line}")
                    continue
        
        except Exception as e:
            logger.error(f"Error streaming response: {e}")
            raise LLMInvalidRequestError(f"Error streaming response: {e}")
        
        finally:
            response.close()
