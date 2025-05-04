# Backdoor AI Flask

A Flask-based AI application with enhanced agent capabilities.

## Features

### Agent System

The Backdoor AI Flask application includes a sophisticated agent system inspired by OpenHands:

- **Modular Agent Architecture**: Flexible, extensible agent system with state management
- **Tool Execution Framework**: Advanced function calling for executing tools
- **Memory Management**: Conversation memory and context condensation
- **Microagent Support**: Specialized knowledge agents for specific domains

### Agent Types

- **CodeAgent**: Specialized agent for coding tasks, with support for:
  - Code generation
  - Debugging
  - Code explanation
  - Tool execution

### Memory Management

- **ConversationMemory**: Manages conversation history
- **Condenser**: Condenses long conversations to fit in context windows
  - NoOpCondenser: Passes messages unchanged
  - SummaryCondenser: Summarizes older messages

### Microagent System

- **KnowledgeMicroagent**: Triggered by specific keywords to provide specialized knowledge
- **RepoMicroagent**: Repository-specific knowledge and guidelines

## API Endpoints

### Code Agent API

- `POST /api/code-agent/create`: Create a new code agent
- `POST /api/code-agent/<agent_id>/chat`: Chat with a code agent
- `POST /api/code-agent/<agent_id>/run`: Run a code agent for multiple steps
- `GET /api/code-agent/<agent_id>/state`: Get the state of a code agent
- `DELETE /api/code-agent/<agent_id>`: Delete a code agent
- `GET /api/code-agent/list`: List all code agents for the current session

## Getting Started

1. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

2. Set environment variables:
   ```
   export TOGETHER_API_KEY=your_api_key
   export FLASK_APP=wsgi.py
   ```

3. Run the application:
   ```
   flask run
   ```

## Architecture

The application follows a modular architecture:

- **Agent**: Base class for all agents
- **AgentController**: Manages agent execution and state
- **ConversationMemory**: Manages conversation history
- **Condenser**: Condenses conversation history
- **Microagent**: Specialized knowledge agents

## License

[MIT License](LICENSE)

