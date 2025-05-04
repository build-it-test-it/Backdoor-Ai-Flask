"""
Exceptions module for Backdoor.
Adapted from OpenHands with modifications for Backdoor Flask app.
"""

class BackdoorError(Exception):
    """Base class for all Backdoor exceptions."""
    pass

class ConfigError(BackdoorError):
    """Raised when there is an error in the configuration."""
    pass

class LLMError(BackdoorError):
    """Base class for all LLM-related exceptions."""
    pass

class LLMNoResponseError(LLMError):
    """Raised when the LLM does not provide a response."""
    pass

class LLMRateLimitError(LLMError):
    """Raised when the LLM rate limit is exceeded."""
    pass

class LLMTimeoutError(LLMError):
    """Raised when the LLM request times out."""
    pass

class LLMInvalidRequestError(LLMError):
    """Raised when the LLM request is invalid."""
    pass

class AgentError(BackdoorError):
    """Base class for all agent-related exceptions."""
    pass

class AgentRuntimeError(AgentError):
    """Base class for all agent runtime-related exceptions."""
    pass

class AgentRuntimeNotFoundError(AgentRuntimeError):
    """Raised when the agent runtime is not found."""
    pass

class AgentRuntimeDisconnectedError(AgentRuntimeError):
    """Raised when the agent runtime is disconnected."""
    pass

class AgentRuntimeTimeoutError(AgentRuntimeError):
    """Raised when the agent runtime times out."""
    pass

class ToolError(BackdoorError):
    """Base class for all tool-related exceptions."""
    pass

class ToolExecutionError(ToolError):
    """Raised when there is an error executing a tool."""
    pass

class ToolNotFoundError(ToolError):
    """Raised when a tool is not found."""
    pass

class ToolTimeoutError(ToolError):
    """Raised when a tool execution times out."""
    pass

class GitHubError(BackdoorError):
    """Base class for all GitHub-related exceptions."""
    pass

class GitHubAuthenticationError(GitHubError):
    """Raised when there is an authentication error with GitHub."""
    pass

class GitHubRateLimitError(GitHubError):
    """Raised when the GitHub rate limit is exceeded."""
    pass

class GitHubTimeoutError(GitHubError):
    """Raised when a GitHub request times out."""
    pass

class DockerError(BackdoorError):
    """Base class for all Docker-related exceptions."""
    pass

class DockerNotFoundError(DockerError):
    """Raised when Docker is not found."""
    pass

class DockerConnectionError(DockerError):
    """Raised when there is an error connecting to Docker."""
    pass

class DockerTimeoutError(DockerError):
    """Raised when a Docker operation times out."""
    pass

class MicroagentError(BackdoorError):
    """Base class for all microagent-related exceptions."""
    pass

class MicroagentNotFoundError(MicroagentError):
    """Raised when a microagent is not found."""
    pass

class MicroagentLoadError(MicroagentError):
    """Raised when there is an error loading a microagent."""
    pass