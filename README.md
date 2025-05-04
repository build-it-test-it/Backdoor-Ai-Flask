# Backdoor AI Flask

A powerful AI application with integrated VS Code server and PostgreSQL database for persistent context management and agent-based tool interaction.

## Features

- **AI-Powered Chat Interface**: Interact with a powerful AI model (Together AI Llama-3.3-70B)
- **Model Context Protocol (MCP)**: Persistent context storage and management using PostgreSQL
- **Github Integration**: Connect to repositories and analyze code
- **VS Code Server Integration**: Create workspaces and edit code through VS Code
- **Agent System**: AI agents with specific roles can use tools and execute commands
- **Tool Registry**: Centralized tool management with permission controls
- **Web Browsing**: Browse and extract content from websites

## Setup

### Prerequisites

- Python 3.10+
- PostgreSQL (for production)
- Docker (optional)

### Installation

1. Clone the repository:
   ```
   git clone https://github.com/your-username/backdoor-ai-flask.git
   cd backdoor-ai-flask
   ```

2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Set environment variables:
   ```
   cp .env.example .env
   ```
   Edit the `.env` file to include your API keys and database configuration.

4. Initialize the database:
   ```
   flask db upgrade
   ```

5. Run the application:
   ```
   python run.py
   ```

## Docker Deployment

1. Build the Docker image:
   ```
   docker build -t backdoor-ai-flask .
   ```

2. Run the container:
   ```
   docker run -p 5000:5000 -e TOGETHER_API_KEY=your_api_key backdoor-ai-flask
   ```

## Key Components

- **MCP Server**: The Model Context Protocol server for context management
- **Agent System**: Manages AI agents with different roles and permissions
- **VS Code Integration**: Provides a code-server instance for editing code
- **Tool Handler**: Centralized tool execution with permission controls
- **Database Models**: Store context items, agents, tasks, and tool usage
