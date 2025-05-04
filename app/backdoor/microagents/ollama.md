---
name: Ollama
type: knowledge
version: 1.0.0
agent: CodeActAgent
triggers:
  - ollama
  - local llm
  - llama
  - llama4
  - local models
  - self-hosted llm
---

# Ollama Microagent

This microagent provides knowledge and capabilities for using Ollama to run LLMs locally.

## What is Ollama?

Ollama is an open-source tool that allows you to run large language models (LLMs) locally on your own hardware. It simplifies the process of downloading, setting up, and interacting with state-of-the-art LLM models including Llama models from Meta.

## Setup

### Installation

To use Ollama with Backdoor, you need to:

1. Install Ollama on your machine by following the instructions at [https://ollama.com/download](https://ollama.com/download)
   - Linux: `curl -fsSL https://ollama.com/install.sh | sh`
   - macOS: Download from the website or use Homebrew: `brew install ollama`
   - Windows: Download the installer from the website

2. Start the Ollama service:
   - The service typically starts automatically after installation
   - You can manually start it with: `ollama serve`

3. Configure Backdoor to use Ollama:
   - Set the LLM provider to `ollama` in your environment variables or through the API
   - Specify the model you want to use (e.g., `llama4:latest`)
   - Set the API base URL (default is `http://localhost:11434`)

### Environment Variables

Configure Ollama in Backdoor using these environment variables:

- `LLM_PROVIDER=ollama` - Sets Ollama as the default provider
- `OLLAMA_MODEL=llama4:latest` - Sets the default model to use
- `OLLAMA_API_BASE=http://localhost:11434` - Sets the base URL for the Ollama API

## Available Models

Ollama supports a wide range of models, with special support for Llama 4 models in Backdoor:

### Recommended Models

- **llama4:latest** - Llama 4 (base model)
- **llama4-8b:latest** - Llama 4 8B parameters model
- **llama4-code:latest** - Specialized Llama 4 model for coding tasks
- **llama4-tiny:latest** - Smaller, faster Llama 4 variant
- **mistral:latest** - Mistral AI model
- **gemma:latest** - Google's Gemma model

### Model Commands

```bash
# List available models
ollama list

# Pull a model
ollama pull llama4

# Run a model
ollama run llama4
```

## API Usage

The Ollama API base URL is typically `http://localhost:11434`. Backdoor automatically configures this when you select the Ollama provider.

```python
# Update configuration to use Ollama
response = requests.post(
    "http://localhost:5000/api/backdoor/llm/config",
    json={
        "provider": "ollama",
        "model": "llama4:latest",
        "api_base": "http://localhost:11434"
    }
)
```

## Model Management

Ollama allows you to manage models with the following commands:

```bash
# List downloaded models
ollama list

# Remove a model
ollama rm llama4

# Get model info
ollama info llama4
```

## Troubleshooting

Common issues:

- **Connection Error**: Ensure Ollama is running with `ollama serve`
- **Model Not Found**: Run `ollama pull [model-name]` to download the model
- **Out of Memory**: Try using a smaller model or increase available memory
- **Slow Performance**: Ensure your hardware meets minimum requirements:
  - 8GB RAM for smaller models (7B parameter models)
  - 16GB+ RAM for larger models
  - CPU only is supported but GPU is recommended

## Best Practices

1. Start with smaller models like `llama4-8b` or `llama4-tiny` if you have limited hardware
2. Use a GPU if available for significantly faster inference
3. Download models in advance rather than on first use
4. Keep Ollama updated for the latest optimizations and models
5. Configure the `max_tokens` parameter for faster responses
