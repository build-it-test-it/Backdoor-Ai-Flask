Backdoor AI: Your Are To Follow All the instructions below.

This document outlines the setup of a Flask application for **Backdoor AI**, integrating the **meta-llama/Llama-3.3-70B-Instruct-Turbo-Free** model from Together AI and leveraging the open-source **All-Hands-AI/OpenHands** repository for AI-driven software development capabilities. The app is designed to run on **Render.com’s free tier**, using the `/tmp` folder for temporary storage due to Render’s read-only filesystem. It includes a frontend for model interaction, settings for API key and GitHub token configuration, and buttons for chat downloading.

## Project Overview

**Backdoor AI** You are to Create a Flask-based web application that provides API endpoints. I want you to find all the ai components inside the Backdoor-signer repository’s identity all the the functionality for the ai code and what needs to be made for my flask app to make sure everything from the ai code inside the backdoor-signer functions ie we need to set it up so we can keep history and other things so my model can have context over my app provide people with help with things inside my app know everything a user does just like how it is inside the backdoor-signer I need a way for the serverless model to know and be able to understand all this as if it where on the device I want you to also understand the model needs to have full context over my app exactly like it’s meant for the ai code it’s critical so set this up correctly as we are using a serverless endpoint for the model inside my flask app so we need to set his up correctly 

- **Code Modification**: Editing files in a repository.
- **Running Commands**: Executing code via a sandboxed environment (e.g., Docker).
- **GitHub Integration**: Viewing files, creating pull requests, and interacting with repositories.
- **Tool Usage**: Running VS Code and other tools within a sandbox.
- **Model Interaction**: Chatting with the Llama-3.3-70B model for code assistance and task automation.

I want the frontend to provide users with a interface to interact with the model, create a settings tab to configure settings the settings I want are for users to be able to configure there (Together AI API key and GitHub token), and I want you to include a button on the main page to be able to download chat history. The app is deployed on Render.com’s free tier, ensuring compatibility with its constraints.

## Prerequisites

- **Docker**: make sure we use dockers where necessary for different things
- **Python 3.11.11**: For Flask and dependencies. Renders default python version
- **Render.com Account**: For deployment on the free tier.
