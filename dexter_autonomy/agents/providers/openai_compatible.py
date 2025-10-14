"""
OpenAI-compatible provider implementation.

Works with:
- OpenAI
- NVIDIA (https://integrate.api.nvidia.com/v1)
- Perplexity (https://api.perplexity.ai)
- GitHub Models (https://models.inference.ai.azure.com)
- Groq (https://api.groq.com/openai/v1)
- Azure OpenAI
- LM Studio (http://localhost:1234/v1)
- Any other OpenAI-compatible API
"""

import os
from typing import Any, Dict, List

import requests

from .base import ChatMessage, ChatResponse, LLMProvider


class OpenAICompatibleProvider(LLMProvider):
    """
    OpenAI-compatible provider (works with OpenAI, NVIDIA, Perplexity, etc.)
    
    Example:
        # OpenAI
        provider = OpenAICompatibleProvider(
            name="openai",
            endpoint="https://api.openai.com/v1",
            api_key="sk-xxx",
            default_model="gpt-4o-mini"
        )
        
        # NVIDIA
        provider = OpenAICompatibleProvider(
            name="nvidia",
            endpoint="https://integrate.api.nvidia.com/v1",
            api_key="nvapi-xxx",
            default_model="meta/llama-3.1-70b-instruct"
        )
        
        # Perplexity
        provider = OpenAICompatibleProvider(
            name="perplexity",
            endpoint="https://api.perplexity.ai",
            api_key="pplx-xxx",
            default_model="llama-3.1-sonar-small-128k-online"
        )
    """
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
        if not self.endpoint:
            raise ValueError(f"OpenAI-compatible provider '{self.name}' requires 'endpoint' parameter")
        
        self.endpoint = self.endpoint.rstrip("/")
        
        # Build headers
        self.headers = {"Content-Type": "application/json"}
        
        # Add API key
        api_key = self.api_key
        if not api_key and self.api_key_env:
            api_key = os.environ.get(self.api_key_env)
        
        if api_key:
            self.headers["Authorization"] = f"Bearer {api_key}"
        
        # Azure OpenAI uses api-key header instead of Authorization
        if self.name == "azure" and api_key:
            self.headers["api-key"] = api_key
            del self.headers["Authorization"]
    
    def chat(
        self,
        messages: List[Dict[str, str] | ChatMessage],
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        **kwargs
    ) -> ChatResponse:
        """
        Perform OpenAI-compatible chat completion.
        
        Args:
            messages: Chat messages
            model: Model name
            temperature: Sampling temperature (0.0-2.0)
            max_tokens: Maximum tokens to generate
            **kwargs: Additional parameters (top_p, frequency_penalty, etc.)
        
        Returns:
            ChatResponse
        """
        model = model or self.default_model
        if not model:
            raise ValueError("No model specified and no default model set")
        
        # Normalize messages
        normalized_messages = self._normalize_messages(messages)
        
        # Build request payload
        payload = {
            "model": model,
            "messages": normalized_messages,
        }
        
        if temperature is not None:
            payload["temperature"] = temperature
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        
        # Add additional parameters
        payload.update(kwargs)
        
        # Make request
        url = f"{self.endpoint}/chat/completions"
        response = requests.post(
            url,
            json=payload,
            headers=self.headers,
            timeout=self.timeout
        )
        response.raise_for_status()
        
        data = response.json()
        
        # Extract response
        choice = data["choices"][0]
        message = choice["message"]
        content = message.get("content", "")
        
        # Extract usage
        usage = None
        if "usage" in data:
            usage_data = data["usage"]
            usage = {
                "prompt_tokens": usage_data.get("prompt_tokens", 0),
                "completion_tokens": usage_data.get("completion_tokens", 0),
                "total_tokens": usage_data.get("total_tokens", 0),
            }
        
        return ChatResponse(
            content=content,
            model=data.get("model", model),
            finish_reason=choice.get("finish_reason"),
            usage=usage,
            raw_response=data
        )
    
    def health(self) -> Dict[str, Any]:
        """Check provider health."""
        try:
            # Try to list models (most OpenAI-compatible APIs support this)
            url = f"{self.endpoint}/models"
            response = requests.get(url, headers=self.headers, timeout=5.0)
            response.raise_for_status()
            
            data = response.json()
            models = [m["id"] for m in data.get("data", [])]
            
            return {
                "ok": True,
                "endpoint": self.endpoint,
                "models_available": len(models),
                "models": models[:10],  # First 10 models
            }
        except Exception as e:
            # If model listing fails, try a simple chat completion
            try:
                test_response = self.chat(
                    messages=[{"role": "user", "content": "test"}],
                    max_tokens=1
                )
                return {
                    "ok": True,
                    "endpoint": self.endpoint,
                    "note": "Model listing not supported, but chat completion works",
                    "model": test_response.model,
                }
            except Exception as chat_error:
                return {
                    "ok": False,
                    "endpoint": self.endpoint,
                    "error": f"Model listing failed: {e}. Chat completion failed: {chat_error}",
                }
    
    def list_models(self) -> List[str]:
        """List available models."""
        try:
            url = f"{self.endpoint}/models"
            response = requests.get(url, headers=self.headers, timeout=5.0)
            response.raise_for_status()
            
            data = response.json()
            return [m["id"] for m in data.get("data", [])]
        except Exception as e:
            raise RuntimeError(f"Failed to list models: {e}")
