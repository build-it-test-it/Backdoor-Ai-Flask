# Backdoor AI Flask Application with OpenHands Integration

A Flask-based web application that integrates with the meta-llama/Llama-3.3-70B-Instruct-Turbo-Free model from Together AI and leverages the open-source All-Hands-AI/OpenHands repository for AI-driven software development capabilities.

## Features

- **AI Chat Interface**: Interact with the Llama-3.3-70B model for code assistance and task automation
- **GitHub Integration**: Configure GitHub tokens for repository access
- **Chat History**: Save and download chat conversations
- **Settings Management**: Configure API keys and tokens
- **Responsive Design**: Works on desktop and mobile devices

## OpenHands Integration Features

- **Function Calling**: Execute tools and functions directly from the AI chat
- **File Operations**: View, create, and edit files through the AI interface
- **Bash Command Execution**: Run terminal commands and view results
- **Python Code Execution**: Run Python code in an IPython environment
- **Web Browsing**: Read content from webpages and interact with web browsers
- **Thought Process**: Log AI thoughts for complex reasoning
- **Task Completion**: Signal when tasks are completed with summaries

## Prerequisites

- Python 3.11.11 (Render.com's default Python version)
- Together AI API key
- GitHub token (optional)

## Installation

1. Clone the repository:
   ```
   git clone https://github.com/Tools-for-testing/Backdoor-Ai-Flask.git
   cd Backdoor-Ai-Flask
   ```

2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Run the application:
   ```
   python wsgi.py
   ```

4. Access the application at http://localhost:12000

## Environment Variables

- `SECRET_KEY`: Flask secret key for session security
- `TOGETHER_API_KEY`: Your Together AI API key
- `GITHUB_TOKEN`: Your GitHub personal access token
- `OPENHANDS_ENV`: Environment type (development, production)
- `OPENHANDS_LOG_LEVEL`: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- `OPENHANDS_DISABLE_TOOLS`: Comma-separated list of tools to disable
- `OPENHANDS_ENABLE_TOOLS`: Comma-separated list of tools to enable
- `OPENHANDS_TOOL_TIMEOUT`: Timeout in seconds for tool execution (default: 120)

## Deployment on Render.com

This application is designed to run on Render.com's free tier:

1. Create a new Web Service on Render
2. Connect your GitHub repository
3. Set the following:
   - Environment: Python 3
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `gunicorn wsgi:app`
4. Add environment variables in the Render dashboard

## Docker Support

Build and run with Docker:

```
docker build -t backdoor-ai .
docker run -p 8000:8000 backdoor-ai
```

## License

This project is licensed under the MIT License - see the LICENSE file for details.