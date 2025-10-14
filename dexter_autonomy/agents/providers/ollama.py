"""
Ollama provider implementation.
"""

import os
from typing import Any, Dict, List

import requests

from .base import ChatMessage, ChatResponse, LLMProvider


class OllamaProvider(LLMProvider):
    """
    Ollama LLM provider.
    
    Supports both local Ollama instances and cloud endpoints.
    
    Example:
        provider = OllamaProvider(
            name="ollama",
            endpoint="http://localhost:11434",
            default_model="qwen2.5:3b-instruct"
        )
        
        response = provider.chat(messages=[
            {"role": "user", "content": "Hello!"}
        ])
    """
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.endpoint = (self.endpoint or "http://127.0.0.1:11434").rstrip("/")
        
        # Build headers
        self.headers = {"Accept": "application/json", "Content-Type": "application/json"}
        
        # Add API key if provided (for cloud Ollama)
        if self.api_key:
            self.headers["Authorization"] = f"Bearer {self.api_key}"
        elif self.api_key_env:
            api_key = os.environ.get(self.api_key_env)
            if api_key:
                self.headers["Authorization"] = f"Bearer {api_key}"
    
    def chat(
        self,
        messages: List[Dict[str, str] | ChatMessage],
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        **kwargs
    ) -> ChatResponse:
        """
        Perform chat completion with Ollama.
        
        Args:
            messages: Chat messages
            model: Model name (uses default if not provided)
            temperature: Sampling temperature
            max_tokens: Maximum tokens (num_predict in Ollama)
            **kwargs: Additional Ollama options (num_ctx, top_p, etc.)
        
        Returns:
            ChatResponse
        """
        model = model or self.default_model
        if not model:
            raise ValueError("No model specified and no default model set")
        
        # Normalize messages
        normalized_messages = self._normalize_messages(messages)
        
        # Build options
        options = {}
        if temperature is not None:
            options["temperature"] = temperature
        if max_tokens is not None:
            options["num_predict"] = max_tokens
        
        # Add extra options from kwargs
        options.update(kwargs)
        
        # Build request
        payload = {
            "model": model,
            "messages": normalized_messages,
            "stream": False,
        }
        
        if options:
            payload["options"] = options
        
        # Make request
        url = f"{self.endpoint}/api/chat"
        response = requests.post(
            url,
            json=payload,
            headers=self.headers,
            timeout=self.timeout
        )
        response.raise_for_status()
        
        data = response.json()
        
        # Extract response
        assistant_message = data.get("message", {})
        content = assistant_message.get("content", "")
        
        # Extract usage (if available)
        usage = None
        if "prompt_eval_count" in data or "eval_count" in data:
            usage = {
                "prompt_tokens": data.get("prompt_eval_count", 0),
                "completion_tokens": data.get("eval_count", 0),
                "total_tokens": data.get("prompt_eval_count", 0) + data.get("eval_count", 0),
            }
        
        return ChatResponse(
            content=content,
            model=model,
            finish_reason=data.get("done_reason"),
            usage=usage,
            raw_response=data
        )
    
    def health(self) -> Dict[str, Any]:
        """Check Ollama health."""
        try:
            url = f"{self.endpoint}/api/tags"
            response = requests.get(url, headers=self.headers, timeout=5.0)
            response.raise_for_status()
            
            data = response.json()
            models = [m["name"] for m in data.get("models", [])]
            
            return {
                "ok": True,
                "endpoint": self.endpoint,
                "models_available": len(models),
                "models": models[:10],  # First 10 models
            }
        except Exception as e:
            return {
                "ok": False,
                "endpoint": self.endpoint,
                "error": str(e),
            }
    
    def list_models(self) -> List[str]:
        """List available Ollama models."""
        try:
            url = f"{self.endpoint}/api/tags"
            response = requests.get(url, headers=self.headers, timeout=5.0)
            response.raise_for_status()
            
            data = response.json()
            return [m["name"] for m in data.get("models", [])]
        except Exception as e:
            raise RuntimeError(f"Failed to list models: {e}")
