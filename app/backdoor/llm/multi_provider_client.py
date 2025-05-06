"""
Multi-provider LLM client for Backdoor.
"""
import copy
import json
import os
import time
import warnings
from functools import partial
from typing import Any, Callable, Dict, List, Optional, Union

import httpx
import tenacity
from flask import current_app, session

from app.backdoor.core.config import AppConfig, LLMConfig, LLMProviderConfig
from app.backdoor.core.exceptions import (
    LLMInvalidRequestError,
    LLMNoResponseError,
    LLMRateLimitError,
    LLMTimeoutError,
)
from app.backdoor.core.logger import get_logger

# Import litellm with warnings suppressed
with warnings.catch_warnings():
    warnings.simplefilter('ignore')
    import litellm

logger = get_logger("llm.multi_provider")

class MultiProviderLLMClient:
    """LLM client that supports multiple providers."""
    
    def __init__(self, config: AppConfig):
        """Initialize the LLM client.
        
        Args:
            config: The application configuration.
        """
        self.config = config
        self.llm_config = config.llm
        self.provider = self.llm_config.provider
        self.model = self.llm_config.model
        self.api_key = self.llm_config.api_key
        self.api_base = self.llm_config.api_base
        
        # Get provider config
        if self.provider in self.llm_config.providers:
            self.provider_config = self.llm_config.providers[self.provider]
        else:
            logger.warning(f"Provider {self.provider} not found in config. Using custom provider.")
            self.provider_config = self.llm_config.providers["custom"]
            self.provider_config.api_base = self.api_base
            self.provider_config.api_key = self.api_key
            if self.model:
                self.provider_config.models = [self.model]
                self.provider_config.default_model = self.model
        
        # Set up litellm
        litellm.api_key = self.api_key
        
        # Configure provider-specific settings
        if self.provider == "together":
            litellm.together_api_key = self.api_key
            if self.api_base:
                os.environ["TOGETHER_API_BASE"] = self.api_base
        elif self.provider == "openai":
            litellm.openai_api_key = self.api_key
            if self.api_base:
                os.environ["OPENAI_API_BASE"] = self.api_base
        elif self.provider == "anthropic":
            litellm.anthropic_api_key = self.api_key
            if self.api_base:
                os.environ["ANTHROPIC_API_BASE"] = self.api_base
        elif self.provider == "google":
            litellm.google_api_key = self.api_key
            if self.api_base:
                os.environ["GOOGLE_API_BASE"] = self.api_base
        elif self.provider == "mistral":
            litellm.mistral_api_key = self.api_key
            if self.api_base:
                os.environ["MISTRAL_API_BASE"] = self.api_base
        elif self.provider == "cohere":
            litellm.cohere_api_key = self.api_key
            if self.api_base:
                os.environ["COHERE_API_BASE"] = self.api_base
        elif self.provider == "ollama":
            # Ollama doesn't require an API key
            if self.api_base:
                os.environ["OLLAMA_API_BASE"] = self.api_base
        elif self.provider == "custom":
            # For custom provider, we'll use the OpenAI-compatible API
            os.environ["OPENAI_API_KEY"] = self.api_key
            os.environ["OPENAI_API_BASE"] = self.api_base
        
        logger.info(f"Initialized LLM client with provider: {self.provider}, model: {self.model}")
    
    def get_model_string(self) -> str:
        """Get the model string for litellm.
        
        Returns:
            The model string for litellm.
        """
        if self.provider == "together":
            return f"together/{self.model}"
        elif self.provider == "openai":
            return f"openai/{self.model}"
        elif self.provider == "anthropic":
            return f"anthropic/{self.model}"
        elif self.provider == "google":
            return f"google/{self.model}"
        elif self.provider == "mistral":
            return f"mistral/{self.model}"
        elif self.provider == "cohere":
            return f"cohere/{self.model}"
        elif self.provider == "ollama":
            return f"ollama/{self.model}"
        elif self.provider == "custom":
            # For custom provider, we'll use the OpenAI-compatible API
            return f"openai/{self.model}"
        else:
            return self.model
    
    def get_available_models(self) -> List[Dict[str, Any]]:
        """Get the available models.
        
        Returns:
            A list of available models.
        """
        models = []
        
        # Add models from all providers
        for provider_id, provider_config in self.llm_config.providers.items():
            if provider_id == "custom" and not provider_config.api_base:
                continue
                
            for model_id in provider_config.models:
                models.append({
                    "id": model_id,
                    "provider": provider_id,
                    "provider_name": provider_config.name,
                    "default": model_id == provider_config.default_model
                })
        
        return models
    
    def get_retry_decorator(self) -> Callable:
        """Get a retry decorator for LLM calls.
        
        Returns:
            A retry decorator.
        """
        return tenacity.retry(
            retry=tenacity.retry_if_exception_type(
                (httpx.TimeoutException, LLMTimeoutError, LLMRateLimitError)
            ),
            wait=tenacity.wait_exponential(
                multiplier=self.llm_config.retry_delay,
                exp_base=self.llm_config.retry_backoff,
                max=self.llm_config.retry_max_delay,
            ),
            stop=tenacity.stop_after_attempt(self.llm_config.max_retries),
            reraise=True,
            before_sleep=lambda retry_state: logger.warning(
                f"Retrying LLM call after {retry_state.outcome.exception()}, "
                f"attempt {retry_state.attempt_number}/{self.llm_config.max_retries}"
            ),
        )
    
    def completion(
        self,
        messages: List[Dict[str, str]],
        functions: Optional[List[Dict[str, Any]]] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        top_p: Optional[float] = None,
        frequency_penalty: Optional[float] = None,
        presence_penalty: Optional[float] = None,
        stop: Optional[List[str]] = None,
        timeout: Optional[int] = None,
        stream: bool = False,
        stream_callback: Optional[Callable] = None,
    ) -> Dict[str, Any]:
        """Generate a completion for the given messages.
        
        Args:
            messages: The messages to generate a completion for.
            functions: The functions to make available to the model.
            temperature: The temperature to use for sampling.
            max_tokens: The maximum number of tokens to generate.
            top_p: The top-p value to use for sampling.
            frequency_penalty: The frequency penalty to use.
            presence_penalty: The presence penalty to use.
            stop: The stop sequences to use.
            timeout: The timeout for the request.
            stream: Whether to stream the response.
            stream_callback: A callback to call for each chunk of a streaming response.
            
        Returns:
            The completion response.
        """
        # Set default values from config
        temperature = temperature if temperature is not None else self.llm_config.temperature
        max_tokens = max_tokens if max_tokens is not None else self.llm_config.max_tokens
        top_p = top_p if top_p is not None else self.llm_config.top_p
        frequency_penalty = frequency_penalty if frequency_penalty is not None else self.llm_config.frequency_penalty
        presence_penalty = presence_penalty if presence_penalty is not None else self.llm_config.presence_penalty
        stop = stop if stop is not None else self.llm_config.stop
        timeout = timeout if timeout is not None else self.llm_config.timeout
        
        # Get model string
        model = self.get_model_string()
        
        # Log request
        logger.debug_llm(f"LLM request: model={model}, messages={json.dumps(messages)}")
        if functions:
            logger.debug_llm(f"LLM functions: {json.dumps(functions)}")
        
        # Create completion kwargs
        completion_kwargs = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "top_p": top_p,
            "frequency_penalty": frequency_penalty,
            "presence_penalty": presence_penalty,
            "timeout": timeout,
            "stream": stream,
        }
        
        # Add functions if provided
        if functions:
            completion_kwargs["functions"] = functions
        
        # Add stop sequences if provided
        if stop:
            completion_kwargs["stop"] = stop
        
        # Create retry decorator
        retry_decorator = self.get_retry_decorator()
        
        # Define completion function
        @retry_decorator
        def _completion():
            try:
                start_time = time.time()
                
                if stream:
                    # Handle streaming
                    response_chunks = []
                    
                    for chunk in litellm.completion(**completion_kwargs):
                        if stream_callback:
                            stream_callback(chunk)
                        response_chunks.append(chunk)
                    
                    # Combine chunks
                    combined_response = litellm.stream_response_to_completion_response(response_chunks)
                    
                    # Log response time
                    elapsed_time = time.time() - start_time
                    logger.debug_llm(f"LLM streaming response time: {elapsed_time:.2f}s")
                    
                    return combined_response
                else:
                    # Handle non-streaming
                    response = litellm.completion(**completion_kwargs)
                    
                    # Log response time
                    elapsed_time = time.time() - start_time
                    logger.debug_llm(f"LLM response time: {elapsed_time:.2f}s")
                    
                    return response
            except Exception as e:
                # Handle exceptions
                if "rate limit" in str(e).lower():
                    raise LLMRateLimitError(f"Rate limit exceeded: {e}")
                elif "timeout" in str(e).lower():
                    raise LLMTimeoutError(f"Request timed out: {e}")
                elif "invalid request" in str(e).lower():
                    raise LLMInvalidRequestError(f"Invalid request: {e}")
                else:
                    raise
        
        # Execute completion
        try:
            response = _completion()
            
            # Check if response is valid
            if not response or not response.get("choices"):
                raise LLMNoResponseError("No response from LLM")
            
            # Log response
            logger.debug_llm(f"LLM response: {json.dumps(response)}")
            
            return response
        except Exception as e:
            logger.error(f"Error in LLM completion: {e}")
            raise
    
    def update_config(self, config: Dict[str, Any]) -> None:
        """Update the LLM configuration.
        
        Args:
            config: The new configuration.
        """
        # Update provider
        if "provider" in config:
            self.provider = config["provider"]
            
            # Reset model to default if provider changed
            if self.provider in self.llm_config.providers:
                self.model = self.llm_config.providers[self.provider].default_model
        
        # Update model
        if "model" in config:
            self.model = config["model"]
        
        # Update API key
        if "api_key" in config:
            self.api_key = config["api_key"]
            
            # Update litellm API key
            litellm.api_key = self.api_key
            
            # Update provider-specific API key
            if self.provider == "together":
                litellm.together_api_key = self.api_key
            elif self.provider == "openai":
                litellm.openai_api_key = self.api_key
            elif self.provider == "anthropic":
                litellm.anthropic_api_key = self.api_key
            elif self.provider == "google":
                litellm.google_api_key = self.api_key
            elif self.provider == "mistral":
                litellm.mistral_api_key = self.api_key
            elif self.provider == "cohere":
                litellm.cohere_api_key = self.api_key
            elif self.provider == "custom":
                os.environ["OPENAI_API_KEY"] = self.api_key
            # For Ollama, we don't need to set an API key as it doesn't require one
        
        # Update API base
        if "api_base" in config:
            self.api_base = config["api_base"]
            
            # Update provider-specific API base
            if self.provider == "together":
                os.environ["TOGETHER_API_BASE"] = self.api_base
            elif self.provider == "openai":
                os.environ["OPENAI_API_BASE"] = self.api_base
            elif self.provider == "anthropic":
                os.environ["ANTHROPIC_API_BASE"] = self.api_base
            elif self.provider == "google":
                os.environ["GOOGLE_API_BASE"] = self.api_base
            elif self.provider == "mistral":
                os.environ["MISTRAL_API_BASE"] = self.api_base
            elif self.provider == "cohere":
                os.environ["COHERE_API_BASE"] = self.api_base
            elif self.provider == "ollama":
                os.environ["OLLAMA_API_BASE"] = self.api_base
            elif self.provider == "custom":
                os.environ["OPENAI_API_BASE"] = self.api_base
        
        # Update other parameters
        if "temperature" in config:
            self.llm_config.temperature = config["temperature"]
        if "max_tokens" in config:
            self.llm_config.max_tokens = config["max_tokens"]
        if "top_p" in config:
            self.llm_config.top_p = config["top_p"]
        if "frequency_penalty" in config:
            self.llm_config.frequency_penalty = config["frequency_penalty"]
        if "presence_penalty" in config:
            self.llm_config.presence_penalty = config["presence_penalty"]
        if "stop" in config:
            self.llm_config.stop = config["stop"]
        if "timeout" in config:
            self.llm_config.timeout = config["timeout"]
        
        logger.info(f"Updated LLM config: provider={self.provider}, model={self.model}")