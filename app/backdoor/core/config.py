"""
Configuration module for Backdoor.
Adapted from OpenHands with modifications for Backdoor Flask app.
"""
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union

@dataclass
class LLMProviderConfig:
    """Configuration for an LLM provider."""
    name: str
    api_base: str
    api_key: Optional[str] = None
    models: List[str] = field(default_factory=list)
    default_model: Optional[str] = None
    headers: Dict[str, str] = field(default_factory=dict)
    timeout: int = 120
    max_retries: int = 3
    retry_delay: int = 1
    retry_backoff: float = 2.0
    retry_jitter: float = 0.1
    retry_max_delay: int = 60
    retry_on_timeout: bool = True
    retry_on_status_codes: List[int] = field(default_factory=lambda: [429, 500, 502, 503, 504])
    retry_on_exceptions: List[str] = field(default_factory=lambda: ["Timeout", "RateLimitError", "InternalServerError"])

@dataclass
class LLMConfig:
    """Configuration for LLM."""
    provider: str = "together"
    model: str = "meta-llama/Llama-3.3-70B-Instruct-Turbo-Free"
    api_key: Optional[str] = None
    api_base: Optional[str] = None
    max_tokens: int = 4096
    temperature: float = 0.7
    top_p: float = 0.95
    frequency_penalty: float = 0.0
    presence_penalty: float = 0.0
    stop: List[str] = field(default_factory=list)
    timeout: int = 120
    max_retries: int = 3
    retry_delay: int = 1
    retry_backoff: float = 2.0
    retry_jitter: float = 0.1
    retry_max_delay: int = 60
    retry_on_timeout: bool = True
    retry_on_status_codes: List[int] = field(default_factory=lambda: [429, 500, 502, 503, 504])
    retry_on_exceptions: List[str] = field(default_factory=lambda: ["Timeout", "RateLimitError", "InternalServerError"])
    providers: Dict[str, LLMProviderConfig] = field(default_factory=lambda: {
        "together": LLMProviderConfig(
            name="Together AI",
            api_base="https://api.together.xyz/v1",
            models=[
                "meta-llama/Llama-3.3-70B-Instruct-Turbo-Free",
                "meta-llama/Llama-3.1-70B-Instruct",
                "meta-llama/Llama-3.1-8B-Instruct",
                "mistralai/Mixtral-8x7B-Instruct-v0.1",
                "mistralai/Mistral-7B-Instruct-v0.2",
                "google/gemma-7b-it",
                "google/gemma-2-9b-it",
                "google/gemma-2-27b-it",
                "anthropic/claude-3-opus-20240229",
                "anthropic/claude-3-sonnet-20240229",
                "anthropic/claude-3-haiku-20240307",
                "anthropic/claude-2.1",
                "anthropic/claude-2.0",
                "anthropic/claude-instant-1.2",
                "meta-llama/Llama-2-70b-chat-hf",
                "meta-llama/Llama-2-13b-chat-hf",
                "meta-llama/Llama-2-7b-chat-hf",
                "codellama/CodeLlama-34b-Instruct-hf",
                "codellama/CodeLlama-13b-Instruct-hf",
                "codellama/CodeLlama-7b-Instruct-hf",
                "togethercomputer/StripedHyena-Nous-7B",
                "togethercomputer/RedPajama-INCITE-7B-Chat",
            ],
            default_model="meta-llama/Llama-3.3-70B-Instruct-Turbo-Free"
        ),
        "openai": LLMProviderConfig(
            name="OpenAI",
            api_base="https://api.openai.com/v1",
            models=[
                "gpt-4o",
                "gpt-4o-mini",
                "gpt-4-turbo",
                "gpt-4",
                "gpt-3.5-turbo",
            ],
            default_model="gpt-3.5-turbo"
        ),
        "anthropic": LLMProviderConfig(
            name="Anthropic",
            api_base="https://api.anthropic.com/v1",
            models=[
                "claude-3-opus-20240229",
                "claude-3-sonnet-20240229",
                "claude-3-haiku-20240307",
                "claude-2.1",
                "claude-2.0",
                "claude-instant-1.2",
            ],
            default_model="claude-3-haiku-20240307"
        ),
        "google": LLMProviderConfig(
            name="Google",
            api_base="https://generativelanguage.googleapis.com/v1beta",
            models=[
                "gemini-pro",
                "gemini-ultra",
            ],
            default_model="gemini-pro"
        ),
        "mistral": LLMProviderConfig(
            name="Mistral AI",
            api_base="https://api.mistral.ai/v1",
            models=[
                "mistral-tiny",
                "mistral-small",
                "mistral-medium",
                "mistral-large",
            ],
            default_model="mistral-small"
        ),
        "cohere": LLMProviderConfig(
            name="Cohere",
            api_base="https://api.cohere.ai/v1",
            models=[
                "command",
                "command-light",
                "command-nightly",
                "command-light-nightly",
            ],
            default_model="command"
        ),
        "custom": LLMProviderConfig(
            name="Custom",
            api_base="",
            models=[],
            default_model=None
        ),
        "ollama": LLMProviderConfig(
            name="Ollama",
            api_base="http://localhost:11434",
            models=[
                "llama4:latest",
                "llama4-8b:latest",
                "llama4-code:latest",
                "llama4-tiny:latest",
                "mistral:latest",
                "gemma:latest",
            ],
            default_model="llama4:latest"
        )
    })

@dataclass
class DockerConfig:
    """Configuration for Docker runtime."""
    enabled: bool = True
    image: str = "backdoor/runtime:latest"
    container_prefix: str = "backdoor-runtime-"
    network: str = "backdoor-network"
    volume_prefix: str = "backdoor-volume-"
    timeout: int = 60
    max_containers: int = 5
    port_range_start: int = 30000
    port_range_end: int = 39999
    vscode_port_range_start: int = 40000
    vscode_port_range_end: int = 49999
    app_port_range_start: int = 50000
    app_port_range_end: int = 59999

@dataclass
class GitHubConfig:
    """Configuration for GitHub integration."""
    token: Optional[str] = None
    username: str = "backdoor"
    email: str = "backdoor@example.com"
    api_base: str = "https://api.github.com"
    timeout: int = 30
    max_retries: int = 3

@dataclass
class AgentConfig:
    """Configuration for Agent."""
    name: str = "BackdoorAgent"
    description: str = "Backdoor AI Agent"
    version: str = "1.0.0"
    tools: List[str] = field(default_factory=lambda: ["execute_bash", "str_replace_editor", "browser", "execute_ipython_cell", "think", "web_read", "finish"])
    microagents_dir: str = "/tmp/backdoor/microagents"
    max_iterations: int = 10
    max_tool_calls: int = 100
    max_tokens: int = 4096
    temperature: float = 0.7
    timeout: int = 300

@dataclass
class AppConfig:
    """Configuration for Backdoor app."""
    debug: bool = False
    testing: bool = False
    env: str = "production"
    secret_key: str = "default_secret_key_change_me"
    host: str = "0.0.0.0"
    port: int = 5000
    log_level: str = "INFO"
    log_file: str = "/tmp/backdoor/logs/backdoor.log"
    data_dir: str = "/tmp/backdoor/data"
    cache_dir: str = "/tmp/backdoor/cache"
    tools_dir: str = "/tmp/backdoor/tools"
    config_dir: str = "/tmp/backdoor/config"
    vscode_dir: str = "/tmp/backdoor/vscode"
    microagents_dir: str = "/tmp/backdoor/microagents"
    llm: LLMConfig = field(default_factory=LLMConfig)
    docker: DockerConfig = field(default_factory=DockerConfig)
    github: GitHubConfig = field(default_factory=GitHubConfig)
    agent: AgentConfig = field(default_factory=AgentConfig)
    sandbox: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Initialize configuration from environment variables."""
        # LLM config
        self.llm.provider = os.environ.get("LLM_PROVIDER", self.llm.provider)
        
        # Provider-specific configurations
        if self.llm.provider == "together":
            self.llm.api_key = os.environ.get("TOGETHER_API_KEY", self.llm.api_key)
            self.llm.model = os.environ.get("TOGETHER_MODEL", self.llm.model)
            self.llm.api_base = os.environ.get("TOGETHER_API_BASE", self.llm.providers["together"].api_base)
        elif self.llm.provider == "openai":
            self.llm.api_key = os.environ.get("OPENAI_API_KEY", self.llm.api_key)
            self.llm.model = os.environ.get("OPENAI_MODEL", self.llm.providers["openai"].default_model)
            self.llm.api_base = os.environ.get("OPENAI_API_BASE", self.llm.providers["openai"].api_base)
        elif self.llm.provider == "anthropic":
            self.llm.api_key = os.environ.get("ANTHROPIC_API_KEY", self.llm.api_key)
            self.llm.model = os.environ.get("ANTHROPIC_MODEL", self.llm.providers["anthropic"].default_model)
            self.llm.api_base = os.environ.get("ANTHROPIC_API_BASE", self.llm.providers["anthropic"].api_base)
        elif self.llm.provider == "google":
            self.llm.api_key = os.environ.get("GOOGLE_API_KEY", self.llm.api_key)
            self.llm.model = os.environ.get("GOOGLE_MODEL", self.llm.providers["google"].default_model)
            self.llm.api_base = os.environ.get("GOOGLE_API_BASE", self.llm.providers["google"].api_base)
        elif self.llm.provider == "mistral":
            self.llm.api_key = os.environ.get("MISTRAL_API_KEY", self.llm.api_key)
            self.llm.model = os.environ.get("MISTRAL_MODEL", self.llm.providers["mistral"].default_model)
            self.llm.api_base = os.environ.get("MISTRAL_API_BASE", self.llm.providers["mistral"].api_base)
        elif self.llm.provider == "cohere":
            self.llm.api_key = os.environ.get("COHERE_API_KEY", self.llm.api_key)
            self.llm.model = os.environ.get("COHERE_MODEL", self.llm.providers["cohere"].default_model)
            self.llm.api_base = os.environ.get("COHERE_API_BASE", self.llm.providers["cohere"].api_base)
        elif self.llm.provider == "ollama":
            # Ollama doesn't require an API key
            self.llm.api_key = None
            self.llm.model = os.environ.get("OLLAMA_MODEL", self.llm.providers["ollama"].default_model)
            self.llm.api_base = os.environ.get("OLLAMA_API_BASE", self.llm.providers["ollama"].api_base)
        elif self.llm.provider == "custom":
            self.llm.api_key = os.environ.get("CUSTOM_API_KEY", self.llm.api_key)
            self.llm.model = os.environ.get("CUSTOM_MODEL", "")
            self.llm.api_base = os.environ.get("CUSTOM_API_BASE", "")
            
            # Update custom provider config
            self.llm.providers["custom"].api_base = self.llm.api_base
            self.llm.providers["custom"].api_key = self.llm.api_key
            if self.llm.model:
                self.llm.providers["custom"].models = [self.llm.model]
                self.llm.providers["custom"].default_model = self.llm.model
        
        # Update the provider config with the API key
        if self.llm.provider in self.llm.providers:
            self.llm.providers[self.llm.provider].api_key = self.llm.api_key
            
            # If api_base is provided, update the provider config
            if self.llm.api_base:
                self.llm.providers[self.llm.provider].api_base = self.llm.api_base
        
        # GitHub config
        self.github.token = os.environ.get("GITHUB_TOKEN", self.github.token)
        
        # Docker config
        self.docker.enabled = os.environ.get("BACKDOOR_DOCKER_ENABLED", "true").lower() == "true"
        self.docker.image = os.environ.get("BACKDOOR_DOCKER_IMAGE", self.docker.image)
        self.docker.network = os.environ.get("BACKDOOR_DOCKER_NETWORK", self.docker.network)
        
        # App config
        self.secret_key = os.environ.get("SECRET_KEY", self.secret_key)
        self.env = os.environ.get("BACKDOOR_ENV", self.env)
        self.log_level = os.environ.get("MCP_LOG_LEVEL", self.log_level)
        
        # Create directories if they don't exist
        for directory in [self.data_dir, self.cache_dir, self.tools_dir, 
                         self.config_dir, self.vscode_dir, self.microagents_dir]:
            os.makedirs(directory, exist_ok=True)

def get_config() -> AppConfig:
    """Get the application configuration."""
    return AppConfig()