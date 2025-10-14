"""
Anthropic Claude provider implementation.

Anthropic uses a different API format than OpenAI, so it needs
its own adapter.
"""

import os
from typing import Any, Dict, List

import requests

from .base import ChatMessage, ChatResponse, LLMProvider


class AnthropicProvider(LLMProvider):
    """
    Anthropic Claude provider.
    
    Example:
        provider = AnthropicProvider(
            name="anthropic",
            api_key="sk-ant-xxx",
            default_model="claude-3-5-sonnet-20241022"
        )
        
        response = provider.chat(messages=[
            {"role": "user", "content": "Hello!"}
        ])
    """
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.endpoint = (self.endpoint or "https://api.anthropic.com/v1").rstrip("/")
        
        # Get API key
        api_key = self.api_key
        if not api_key and self.api_key_env:
            api_key = os.environ.get(self.api_key_env)
        
        if not api_key:
            raise ValueError("Anthropic provider requires API key (via api_key or api_key_env)")
        
        # Build headers
        self.headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
    
    def chat(
        self,
        messages: List[Dict[str, str] | ChatMessage],
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        system: str | None = None,
        **kwargs
    ) -> ChatResponse:
        """
        Perform chat completion with Anthropic.
        
        Args:
            messages: Chat messages
            model: Model name
            temperature: Sampling temperature (0.0-1.0)
            max_tokens: Maximum tokens to generate (required by Anthropic)
            system: System prompt (Anthropic uses separate system parameter)
            **kwargs: Additional parameters
        
        Returns:
            ChatResponse
        """
        model = model or self.default_model
        if not model:
            raise ValueError("No model specified and no default model set")
        
        # Normalize messages
        normalized_messages = self._normalize_messages(messages)
        
        # Extract system message if present
        anthropic_messages = []
        for msg in normalized_messages:
            if msg["role"] == "system":
                if not system:
                    system = msg["content"]
            else:
                anthropic_messages.append(msg)
        
        # Build request payload
        payload = {
            "model": model,
            "messages": anthropic_messages,
            "max_tokens": max_tokens or 4096,  # Anthropic requires max_tokens
        }
        
        if system:
            payload["system"] = system
        if temperature is not None:
            payload["temperature"] = temperature
        
        # Add additional parameters
        payload.update(kwargs)
        
        # Make request
        url = f"{self.endpoint}/messages"
        response = requests.post(
            url,
            json=payload,
            headers=self.headers,
            timeout=self.timeout
        )
        response.raise_for_status()
        
        data = response.json()
        
        # Extract response
        content_blocks = data.get("content", [])
        content = ""
        if content_blocks:
            # Combine all text blocks
            content = " ".join(
                block.get("text", "") 
                for block in content_blocks 
                if block.get("type") == "text"
            )
        
        # Extract usage
        usage = None
        if "usage" in data:
            usage_data = data["usage"]
            usage = {
                "prompt_tokens": usage_data.get("input_tokens", 0),
                "completion_tokens": usage_data.get("output_tokens", 0),
                "total_tokens": usage_data.get("input_tokens", 0) + usage_data.get("output_tokens", 0),
            }
        
        return ChatResponse(
            content=content,
            model=data.get("model", model),
            finish_reason=data.get("stop_reason"),
            usage=usage,
            raw_response=data
        )
    
    def health(self) -> Dict[str, Any]:
        """Check Anthropic health."""
        try:
            # Anthropic doesn't have a dedicated health endpoint
            # Try a minimal chat completion
            test_response = self.chat(
                messages=[{"role": "user", "content": "Hi"}],
                max_tokens=10
            )
            return {
                "ok": True,
                "endpoint": self.endpoint,
                "model": test_response.model,
            }
        except Exception as e:
            return {
                "ok": False,
                "endpoint": self.endpoint,
                "error": str(e),
            }
    
    def list_models(self) -> List[str]:
        """List available models (hardcoded - Anthropic doesn't provide API)."""
        return [
            "claude-3-5-sonnet-20241022",
            "claude-3-5-haiku-20241022",
            "claude-3-opus-20240229",
            "claude-3-sonnet-20240229",
            "claude-3-haiku-20240307",
        ]
