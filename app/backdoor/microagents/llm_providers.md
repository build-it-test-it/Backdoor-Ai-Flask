---
name: LLM Providers
type: knowledge
version: 1.0.0
agent: CodeActAgent
triggers:
  - llm
  - language model
  - ai model
  - together
  - openai
  - anthropic
  - google
  - mistral
  - cohere
  - custom model
  - api key
---

# LLM Providers Microagent

This microagent provides knowledge and capabilities for working with different LLM providers.

## Supported Providers

The Backdoor system supports the following LLM providers:

1. **Together AI** - Provider ID: `together`
   - Default model: `meta-llama/Llama-3.3-70B-Instruct-Turbo-Free`
   - API Base: `https://api.together.xyz/v1`
   - Environment variables: `TOGETHER_API_KEY`, `TOGETHER_MODEL`, `TOGETHER_API_BASE`

2. **OpenAI** - Provider ID: `openai`
   - Default model: `gpt-3.5-turbo`
   - API Base: `https://api.openai.com/v1`
   - Environment variables: `OPENAI_API_KEY`, `OPENAI_MODEL`, `OPENAI_API_BASE`

3. **Anthropic** - Provider ID: `anthropic`
   - Default model: `claude-3-haiku-20240307`
   - API Base: `https://api.anthropic.com/v1`
   - Environment variables: `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL`, `ANTHROPIC_API_BASE`

4. **Google** - Provider ID: `google`
   - Default model: `gemini-pro`
   - API Base: `https://generativelanguage.googleapis.com/v1beta`
   - Environment variables: `GOOGLE_API_KEY`, `GOOGLE_MODEL`, `GOOGLE_API_BASE`

5. **Mistral AI** - Provider ID: `mistral`
   - Default model: `mistral-small`
   - API Base: `https://api.mistral.ai/v1`
   - Environment variables: `MISTRAL_API_KEY`, `MISTRAL_MODEL`, `MISTRAL_API_BASE`

6. **Cohere** - Provider ID: `cohere`
   - Default model: `command`
   - API Base: `https://api.cohere.ai/v1`
   - Environment variables: `COHERE_API_KEY`, `COHERE_MODEL`, `COHERE_API_BASE`

7. **Custom** - Provider ID: `custom`
   - Default model: None
   - API Base: None
   - Environment variables: `CUSTOM_API_KEY`, `CUSTOM_MODEL`, `CUSTOM_API_BASE`

## API Endpoints

The Backdoor system provides the following API endpoints for working with LLM providers:

- `GET /api/backdoor/llm/providers` - Get the available LLM providers
- `GET /api/backdoor/llm/models` - Get the available LLM models
- `GET /api/backdoor/llm/config` - Get the LLM configuration
- `POST /api/backdoor/llm/config` - Update the LLM configuration
- `POST /api/backdoor/llm/test` - Test the LLM configuration

## Using a Custom LLM Provider

To use a custom LLM provider, you need to provide the following information:

1. API Key - The API key for the custom provider
2. API Base - The base URL for the custom provider's API
3. Model - The model ID to use with the custom provider

Example:

```python
import requests

# Update LLM configuration
response = requests.post(
    "http://localhost:5000/api/backdoor/llm/config",
    json={
        "provider": "custom",
        "api_key": "your-api-key",
        "api_base": "https://api.custom-provider.com/v1",
        "model": "custom-model"
    }
)

# Test the configuration
response = requests.post(
    "http://localhost:5000/api/backdoor/llm/test",
    json={}
)
```

## Best Practices

1. Store API keys securely and never expose them in client-side code
2. Use environment variables to configure API keys in production
3. Test the LLM configuration before using it in production
4. Use the default model for each provider unless you have specific requirements
5. Consider rate limits and costs when choosing a provider and model

## Troubleshooting

Common issues:

- **Invalid API Key**: Check that the API key is valid and has the necessary permissions
- **Rate Limit Exceeded**: Reduce the frequency of requests or upgrade your plan
- **Model Not Found**: Check that the model ID is correct and available for your account
- **API Base URL Incorrect**: Verify the API base URL for the provider
- **Network Error**: Check your network connection and firewall settings