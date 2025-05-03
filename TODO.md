# Backdoor AI with OpenHands Integration - COMPLETED

This document outlines the completed setup of a Flask application for **Backdoor AI**, integrating the **meta-llama/Llama-3.3-70B-Instruct-Turbo-Free** model from Together AI and leveraging the open-source **All-Hands-AI/OpenHands** repository for AI-driven software development capabilities. The app is designed to run on **Render.com's free tier**, using the `/tmp` folder for temporary storage due to Render's read-only filesystem. It includes a frontend for model interaction, settings for API key and GitHub token configuration, and buttons for chat downloading.

## Completed Features

✅ **Flask Application**: Created a Flask-based web application with API endpoints
✅ **AI Integration**: Integrated with Together AI's Llama-3.3-70B model
✅ **OpenHands Features**: Implemented OpenHands-style tools and function calling
✅ **Context Management**: Added robust context tracking for the AI model
✅ **Chat History**: Implemented chat history storage and retrieval
✅ **Settings Management**: Added configuration for API keys and tokens
✅ **Tool Execution**: Implemented bash command execution
✅ **File Operations**: Added file viewing, creation, and editing capabilities
✅ **Python Code Execution**: Added Python code execution in IPython
✅ **Web Browsing**: Implemented web content reading and browser interaction
✅ **GitHub Integration**: Added GitHub API integration
✅ **User Behavior Tracking**: Implemented behavior tracking for better context
✅ **Feedback System**: Added user feedback collection for AI responses
✅ **Environment Setup**: Configured OpenHands-style environment variables and directories

## Enhanced Capabilities

The application now supports:

- **Code Modification**: Editing files in a repository through AI tools
- **Running Commands**: Executing code via bash and Python
- **GitHub Integration**: Viewing files, creating pull requests, and interacting with repositories
- **Tool Usage**: Using various tools through the AI interface
- **Model Interaction**: Chatting with the Llama-3.3-70B model with function calling support

## Prerequisites

- **Python 3.11.11**: For Flask and dependencies (Render's default Python version)
- **Together AI API Key**: For model access
- **GitHub Token**: For GitHub integration (optional)
- **Render.com Account**: For deployment on the free tier
