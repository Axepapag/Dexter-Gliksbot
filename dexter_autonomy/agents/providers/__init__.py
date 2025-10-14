"""
Multi-Provider LLM Support for Dexter Agents

This module provides a unified interface for multiple LLM providers:
- Ollama (local/cloud)
- OpenAI
- Anthropic
- NVIDIA (OpenAI-compatible)
- Perplexity (OpenAI-compatible)
- GitHub Models (OpenAI-compatible)
- Groq (OpenAI-compatible)
- Azure OpenAI
- LM Studio (OpenAI-compatible)
- Generic HTTP (any OpenAI-compatible endpoint)

Usage:
    from dexter_autonomy.agents.providers import get_provider, PROVIDERS
    
    # Get provider by name
    provider = get_provider("nvidia", api_key="your-key", model="meta/llama-3.1-70b-instruct")
    
    # Chat completion
    response = provider.chat(messages=[{"role": "user", "content": "Hello"}])
    
    # List available providers
    print(list(PROVIDERS.keys()))
"""

from .base import LLMProvider, ChatMessage, ChatResponse
from .ollama import OllamaProvider
from .openai_compatible import OpenAICompatibleProvider
from .anthropic_provider import AnthropicProvider

# Provider registry
PROVIDERS: dict[str, type[LLMProvider]] = {
    "ollama": OllamaProvider,
    "openai": OpenAICompatibleProvider,
    "nvidia": OpenAICompatibleProvider,
    "perplexity": OpenAICompatibleProvider,
    "github": OpenAICompatibleProvider,
    "groq": OpenAICompatibleProvider,
    "azure": OpenAICompatibleProvider,
    "lmstudio": OpenAICompatibleProvider,
    "anthropic": AnthropicProvider,
    "generic": OpenAICompatibleProvider,
}

# Provider presets (default endpoints and settings)
PROVIDER_PRESETS = {
    "ollama": {
        "endpoint": "http://127.0.0.1:11434",
        "api_key_env": None,
        "default_model": "qwen2.5:3b-instruct",
    },
    "openai": {
        "endpoint": "https://api.openai.com/v1",
        "api_key_env": "OPENAI_API_KEY",
        "default_model": "gpt-4o-mini",
    },
    "nvidia": {
        "endpoint": "https://integrate.api.nvidia.com/v1",
        "api_key_env": "NVIDIA_API_KEY",
        "default_model": "meta/llama-3.1-70b-instruct",
    },
    "perplexity": {
        "endpoint": "https://api.perplexity.ai",
        "api_key_env": "PERPLEXITY_API_KEY",
        "default_model": "llama-3.1-sonar-small-128k-online",
    },
    "github": {
        "endpoint": "https://models.inference.ai.azure.com",
        "api_key_env": "GITHUB_TOKEN",
        "default_model": "gpt-4o-mini",
    },
    "groq": {
        "endpoint": "https://api.groq.com/openai/v1",
        "api_key_env": "GROQ_API_KEY",
        "default_model": "llama-3.1-70b-versatile",
    },
    "azure": {
        "endpoint": None,  # User must provide: https://{resource}.openai.azure.com
        "api_key_env": "AZURE_OPENAI_API_KEY",
        "default_model": None,  # User must specify deployment name
    },
    "lmstudio": {
        "endpoint": "http://localhost:1234/v1",
        "api_key_env": None,
        "default_model": "local-model",
    },
    "anthropic": {
        "endpoint": "https://api.anthropic.com/v1",
        "api_key_env": "ANTHROPIC_API_KEY",
        "default_model": "claude-3-5-sonnet-20241022",
    },
    "generic": {
        "endpoint": None,  # User must provide
        "api_key_env": None,  # Optional
        "default_model": None,  # User must specify
    },
}


def get_provider(
    provider_name: str,
    endpoint: str | None = None,
    api_key: str | None = None,
    api_key_env: str | None = None,
    model: str | None = None,
    **kwargs
) -> LLMProvider:
    """
    Get an LLM provider instance by name.
    
    Args:
        provider_name: Name of provider (ollama, openai, nvidia, etc.)
        endpoint: API endpoint (uses preset if not provided)
        api_key: API key (if not using env var)
        api_key_env: Environment variable name for API key
        model: Default model name
        **kwargs: Additional provider-specific options
    
    Returns:
        LLMProvider instance
    
    Raises:
        ValueError: If provider not found or required parameters missing
    
    Examples:
        # Use preset configuration
        provider = get_provider("nvidia", api_key="nvapi-xxx")
        
        # Override endpoint
        provider = get_provider("openai", endpoint="https://custom.openai.com/v1")
        
        # Generic OpenAI-compatible endpoint
        provider = get_provider("generic", 
                              endpoint="https://api.together.xyz/v1",
                              api_key="xxx",
                              model="mistralai/Mixtral-8x7B-Instruct-v0.1")
    """
    if provider_name not in PROVIDERS:
        available = ", ".join(PROVIDERS.keys())
        raise ValueError(
            f"Unknown provider: {provider_name}. Available: {available}"
        )
    
    # Get preset configuration
    preset = PROVIDER_PRESETS.get(provider_name, {})
    
    # Build configuration (user overrides preset)
    config = {
        "endpoint": endpoint or preset.get("endpoint"),
        "api_key": api_key,
        "api_key_env": api_key_env or preset.get("api_key_env"),
        "default_model": model or preset.get("default_model"),
        **kwargs
    }
    
    # Validate required fields
    if not config["endpoint"] and provider_name not in ["anthropic"]:
        raise ValueError(
            f"Provider '{provider_name}' requires 'endpoint' parameter. "
            f"Example: endpoint='https://api.example.com/v1'"
        )
    
    # Instantiate provider
    provider_class = PROVIDERS[provider_name]
    return provider_class(name=provider_name, **config)


__all__ = [
    "LLMProvider",
    "ChatMessage",
    "ChatResponse",
    "OllamaProvider",
    "OpenAICompatibleProvider",
    "AnthropicProvider",
    "PROVIDERS",
    "PROVIDER_PRESETS",
    "get_provider",
]
