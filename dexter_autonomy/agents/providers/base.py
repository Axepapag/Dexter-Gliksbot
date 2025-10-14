"""
Base protocol for LLM providers.

All provider implementations must implement this interface.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class ChatMessage:
    """Standardized chat message format."""
    role: str  # "system", "user", "assistant"
    content: str
    name: Optional[str] = None  # Optional message author name


@dataclass
class ChatResponse:
    """Standardized chat response format."""
    content: str  # Assistant's response text
    model: str  # Model that generated the response
    finish_reason: Optional[str] = None  # "stop", "length", "content_filter", etc.
    usage: Optional[Dict[str, int]] = None  # {"prompt_tokens": X, "completion_tokens": Y, "total_tokens": Z}
    raw_response: Optional[Dict[str, Any]] = None  # Original provider response


class LLMProvider(ABC):
    """
    Abstract base class for LLM providers.
    
    All providers must implement:
    - chat() - Synchronous chat completion
    - health() - Health check
    - list_models() - List available models (if supported)
    """
    
    def __init__(
        self,
        name: str,
        endpoint: str | None = None,
        api_key: str | None = None,
        api_key_env: str | None = None,
        default_model: str | None = None,
        timeout: float = 120.0,
        **kwargs
    ):
        """
        Initialize provider.
        
        Args:
            name: Provider name (ollama, openai, nvidia, etc.)
            endpoint: API endpoint URL
            api_key: API key (if not using env var)
            api_key_env: Environment variable name for API key
            default_model: Default model to use
            timeout: Request timeout in seconds
            **kwargs: Provider-specific options
        """
        self.name = name
        self.endpoint = endpoint
        self.api_key = api_key
        self.api_key_env = api_key_env
        self.default_model = default_model
        self.timeout = timeout
        self.extra_params = kwargs
    
    @abstractmethod
    def chat(
        self,
        messages: List[Dict[str, str] | ChatMessage],
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        **kwargs
    ) -> ChatResponse:
        """
        Perform chat completion.
        
        Args:
            messages: List of chat messages
            model: Model to use (uses default if not specified)
            temperature: Sampling temperature (0.0-2.0)
            max_tokens: Maximum tokens to generate
            **kwargs: Provider-specific parameters
        
        Returns:
            ChatResponse with standardized format
        
        Raises:
            Exception: On API errors
        """
        pass
    
    @abstractmethod
    def health(self) -> Dict[str, Any]:
        """
        Check provider health.
        
        Returns:
            Dict with status info: {"ok": bool, "error": str | None, ...}
        """
        pass
    
    def list_models(self) -> List[str]:
        """
        List available models.
        
        Returns:
            List of model names
        
        Raises:
            NotImplementedError: If provider doesn't support model listing
        """
        raise NotImplementedError(f"Provider '{self.name}' does not support model listing")
    
    def _normalize_messages(
        self, messages: List[Dict[str, str] | ChatMessage]
    ) -> List[Dict[str, str]]:
        """Convert messages to standard dict format."""
        normalized = []
        for msg in messages:
            if isinstance(msg, ChatMessage):
                msg_dict = {"role": msg.role, "content": msg.content}
                if msg.name:
                    msg_dict["name"] = msg.name
                normalized.append(msg_dict)
            else:
                normalized.append(msg)
        return normalized
    
    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}(name='{self.name}', "
            f"endpoint='{self.endpoint}', "
            f"default_model='{self.default_model}')"
        )
