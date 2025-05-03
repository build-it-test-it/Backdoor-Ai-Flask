# Backdoor AI Flask Application

A Flask-based web application that integrates with the meta-llama/Llama-3.3-70B-Instruct-Turbo-Free model from Together AI and leverages the open-source All-Hands-AI/OpenHands repository for AI-driven software development capabilities.

## Features

- **AI Chat Interface**: Interact with the Llama-3.3-70B model for code assistance and task automation
- **GitHub Integration**: Configure GitHub tokens for repository access
- **Chat History**: Save and download chat conversations
- **Settings Management**: Configure API keys and tokens
- **Responsive Design**: Works on desktop and mobile devices

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