# Backdoor AI Agent System

Backdoor is an AI agent system that enables AI assistants to interact with a computer to solve tasks. It is based on the OpenHands project with modifications for the Backdoor Flask application.

## Features

- **CodeActAgent**: An agent that can execute code and other actions in a sandboxed environment
- **Docker Runtime**: A containerized runtime for agent execution
- **Together AI Integration**: Integration with Together AI for LLM capabilities
- **GitHub Integration**: Integration with GitHub for repository operations
- **Microagents**: Specialized prompts that provide context and capabilities for specific domains or tasks
- **Tools**: A set of tools for interacting with the computer, including bash, file editing, browser, and more

## Architecture

The Backdoor system consists of the following components:

- **Core**: Core modules for configuration, logging, and exceptions
- **LLM**: LLM integration with Together AI
- **Runtime**: Docker runtime for agent execution
- **Agenthub**: Agent implementations, including CodeActAgent
- **Microagents**: Specialized prompts for specific domains or tasks
- **Tools**: Tools for interacting with the computer

## Usage

The Backdoor system can be used through the Flask API:

```python
from app.backdoor.agenthub import CodeActAgent
from app.backdoor import config

# Create an agent
agent = CodeActAgent(config, session_id="my-session")

# Process a message
response = agent.process_message("Hello, can you help me with a task?")

# Execute a tool
result = agent.execute_tool("execute_bash", {"command": "ls -la"})
```

## API Endpoints

The Backdoor system exposes the following API endpoints:

- `GET /api/backdoor/status`: Get the status of the Backdoor agent
- `POST /api/backdoor/initialize`: Initialize the Backdoor agent
- `POST /api/backdoor/chat`: Chat with the Backdoor agent
- `POST /api/backdoor/execute_tool`: Execute a tool
- `GET /api/backdoor/conversation`: Get the conversation history
- `DELETE /api/backdoor/conversation`: Clear the conversation history
- `GET /api/backdoor/tools`: Get the available tools
- `GET /api/backdoor/runtime/status`: Get the runtime status
- `GET /api/backdoor/runtime/logs`: Get the runtime logs
- `POST /api/backdoor/runtime/restart`: Restart the runtime

## Docker Runtime

The Backdoor system uses Docker for agent execution. The Docker runtime provides a sandboxed environment for executing code and other actions.

### Dockerfile

The Dockerfile for the Backdoor runtime is located at `/workspace/Backdoor-Ai-Flask/Dockerfile.runtime`. It is based on Ubuntu 22.04 and includes the following components:

- Python 3
- Node.js
- Docker CLI
- Code-server (VS Code in the browser)
- Various Python packages for data science, machine learning, and web development

### Entrypoint

The entrypoint script for the Docker container is located at `/workspace/Backdoor-Ai-Flask/docker/entrypoint.sh`. It sets up the container environment and starts the necessary services.

## Microagents

Microagents are specialized prompts that provide context and capabilities for specific domains or tasks. They are activated by trigger words in the conversation and help the AI assistant understand what capabilities are available, how to use specific APIs or tools, what limitations exist, and how to handle common scenarios.

### GitHub Microagent

The GitHub microagent provides knowledge and capabilities for working with GitHub repositories. It includes information on authentication, API usage, common operations, best practices, error handling, and security considerations.

### Docker Microagent

The Docker microagent provides knowledge and capabilities for working with Docker containers and images. It includes information on basic Docker commands, Dockerfile basics, Docker Compose, best practices, and troubleshooting.

## Tools

The Backdoor system provides a set of tools for interacting with the computer:

- `execute_bash`: Execute a bash command in the terminal
- `str_replace_editor`: Custom editing tool for viewing, creating, and editing files
- `browser`: Interact with the browser using Python code
- `execute_ipython_cell`: Run a cell of Python code in an IPython environment
- `think`: Use the tool to think about something
- `web_read`: Read content from a webpage
- `finish`: Signals the completion of the current task or conversation

## Configuration

The Backdoor system can be configured through environment variables:

- `TOGETHER_API_KEY`: The API key for Together AI
- `TOGETHER_MODEL`: The model to use for Together AI
- `GITHUB_TOKEN`: The token for GitHub API access
- `BACKDOOR_DOCKER_ENABLED`: Whether Docker is enabled
- `BACKDOOR_DOCKER_IMAGE`: The Docker image to use
- `BACKDOOR_DOCKER_NETWORK`: The Docker network to use

## License

This project is licensed under the MIT License - see the LICENSE file for details.