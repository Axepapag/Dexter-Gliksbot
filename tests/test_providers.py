"""
Tests for multi-provider LLM support.
"""

import os
from unittest.mock import Mock, patch

import pytest

from dexter_autonomy.agents.providers import (
    PROVIDERS,
    PROVIDER_PRESETS,
    ChatMessage,
    ChatResponse,
    get_provider,
)
from dexter_autonomy.agents.providers.anthropic_provider import AnthropicProvider
from dexter_autonomy.agents.providers.ollama import OllamaProvider
from dexter_autonomy.agents.providers.openai_compatible import OpenAICompatibleProvider


class TestProviderRegistry:
    """Test provider registry and factory."""
    
    def test_all_providers_registered(self):
        """Test all expected providers are in registry."""
        expected = [
            "ollama", "openai", "nvidia", "perplexity",
            "github", "groq", "azure", "lmstudio", "anthropic", "generic"
        ]
        for name in expected:
            assert name in PROVIDERS, f"Provider '{name}' not in registry"
    
    def test_all_providers_have_presets(self):
        """Test all providers have preset configurations."""
        for name in PROVIDERS.keys():
            assert name in PROVIDER_PRESETS, f"Provider '{name}' missing preset"
    
    def test_get_provider_with_preset(self):
        """Test getting provider with preset configuration."""
        provider = get_provider("ollama")
        assert isinstance(provider, OllamaProvider)
        assert provider.name == "ollama"
        assert provider.endpoint == "http://127.0.0.1:11434"
        assert provider.default_model == "qwen2.5:3b-instruct"
    
    def test_get_provider_with_override(self):
        """Test overriding preset configuration."""
        provider = get_provider(
            "ollama",
            endpoint="http://custom:8000",
            model="custom-model"
        )
        assert provider.endpoint == "http://custom:8000"
        assert provider.default_model == "custom-model"
    
    def test_get_provider_unknown_raises(self):
        """Test unknown provider raises ValueError."""
        with pytest.raises(ValueError, match="Unknown provider"):
            get_provider("nonexistent")
    
    def test_get_provider_missing_endpoint_raises(self):
        """Test missing required endpoint raises ValueError."""
        with pytest.raises(ValueError, match="requires 'endpoint'"):
            get_provider("generic")


class TestOllamaProvider:
    """Test Ollama provider."""
    
    def test_initialization(self):
        """Test Ollama provider initialization."""
        provider = OllamaProvider(
            name="ollama",
            endpoint="http://localhost:11434",
            default_model="llama2"
        )
        assert provider.name == "ollama"
        assert provider.endpoint == "http://localhost:11434"
        assert provider.default_model == "llama2"
    
    def test_endpoint_normalization(self):
        """Test endpoint trailing slash removal."""
        provider = OllamaProvider(
            name="ollama",
            endpoint="http://localhost:11434/"
        )
        assert provider.endpoint == "http://localhost:11434"
    
    @patch('requests.post')
    def test_chat_completion(self, mock_post):
        """Test chat completion."""
        # Mock response
        mock_response = Mock()
        mock_response.json.return_value = {
            "message": {"role": "assistant", "content": "Hello!"},
            "done_reason": "stop",
            "prompt_eval_count": 10,
            "eval_count": 5
        }
        mock_post.return_value = mock_response
        
        provider = OllamaProvider(
            name="ollama",
            endpoint="http://localhost:11434",
            default_model="llama2"
        )
        
        response = provider.chat(messages=[
            {"role": "user", "content": "Hi"}
        ])
        
        assert isinstance(response, ChatResponse)
        assert response.content == "Hello!"
        assert response.model == "llama2"
        assert response.finish_reason == "stop"
        assert response.usage["prompt_tokens"] == 10
        assert response.usage["completion_tokens"] == 5
    
    @patch('requests.post')
    def test_chat_with_chatmessage_objects(self, mock_post):
        """Test chat with ChatMessage objects."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "message": {"role": "assistant", "content": "Response"}
        }
        mock_post.return_value = mock_response
        
        provider = OllamaProvider(
            name="ollama",
            endpoint="http://localhost:11434",
            default_model="llama2"
        )
        
        response = provider.chat(messages=[
            ChatMessage(role="system", content="You are helpful."),
            ChatMessage(role="user", content="Hi")
        ])
        
        assert response.content == "Response"
        
        # Verify messages were normalized
        call_args = mock_post.call_args[1]["json"]
        assert call_args["messages"] == [
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "Hi"}
        ]
    
    @patch('requests.get')
    def test_health_check_success(self, mock_get):
        """Test health check when Ollama is available."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "models": [
                {"name": "llama2"},
                {"name": "mistral"}
            ]
        }
        mock_get.return_value = mock_response
        
        provider = OllamaProvider(
            name="ollama",
            endpoint="http://localhost:11434"
        )
        
        health = provider.health()
        
        assert health["ok"] is True
        assert health["models_available"] == 2
        assert "llama2" in health["models"]
    
    @patch('requests.get')
    def test_health_check_failure(self, mock_get):
        """Test health check when Ollama is unavailable."""
        mock_get.side_effect = Exception("Connection refused")
        
        provider = OllamaProvider(
            name="ollama",
            endpoint="http://localhost:11434"
        )
        
        health = provider.health()
        
        assert health["ok"] is False
        assert "Connection refused" in health["error"]
    
    @patch('requests.get')
    def test_list_models(self, mock_get):
        """Test listing available models."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "models": [
                {"name": "model1"},
                {"name": "model2"},
                {"name": "model3"}
            ]
        }
        mock_get.return_value = mock_response
        
        provider = OllamaProvider(
            name="ollama",
            endpoint="http://localhost:11434"
        )
        
        models = provider.list_models()
        
        assert len(models) == 3
        assert "model1" in models
        assert "model2" in models
        assert "model3" in models


class TestOpenAICompatibleProvider:
    """Test OpenAI-compatible provider."""
    
    def test_initialization(self):
        """Test provider initialization."""
        provider = OpenAICompatibleProvider(
            name="openai",
            endpoint="https://api.openai.com/v1",
            api_key="sk-test",
            default_model="gpt-4o-mini"
        )
        assert provider.name == "openai"
        assert provider.endpoint == "https://api.openai.com/v1"
        assert "Bearer sk-test" in provider.headers["Authorization"]
    
    def test_initialization_missing_endpoint_raises(self):
        """Test missing endpoint raises error."""
        with pytest.raises(ValueError, match="requires 'endpoint'"):
            OpenAICompatibleProvider(name="openai")
    
    def test_api_key_from_env(self):
        """Test API key loading from environment."""
        with patch.dict(os.environ, {"TEST_API_KEY": "env-key"}):
            provider = OpenAICompatibleProvider(
                name="openai",
                endpoint="https://api.openai.com/v1",
                api_key_env="TEST_API_KEY"
            )
            assert "Bearer env-key" in provider.headers["Authorization"]
    
    @patch('requests.post')
    def test_chat_completion(self, mock_post):
        """Test chat completion."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "model": "gpt-4o-mini",
            "choices": [{
                "message": {"role": "assistant", "content": "Hello!"},
                "finish_reason": "stop"
            }],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "total_tokens": 15
            }
        }
        mock_post.return_value = mock_response
        
        provider = OpenAICompatibleProvider(
            name="openai",
            endpoint="https://api.openai.com/v1",
            api_key="sk-test",
            default_model="gpt-4o-mini"
        )
        
        response = provider.chat(messages=[
            {"role": "user", "content": "Hi"}
        ])
        
        assert response.content == "Hello!"
        assert response.model == "gpt-4o-mini"
        assert response.usage["total_tokens"] == 15
    
    @patch('requests.get')
    def test_health_check(self, mock_get):
        """Test health check."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "data": [
                {"id": "model1"},
                {"id": "model2"}
            ]
        }
        mock_get.return_value = mock_response
        
        provider = OpenAICompatibleProvider(
            name="openai",
            endpoint="https://api.openai.com/v1",
            api_key="sk-test"
        )
        
        health = provider.health()
        
        assert health["ok"] is True
        assert health["models_available"] == 2


class TestAnthropicProvider:
    """Test Anthropic provider."""
    
    def test_initialization(self):
        """Test provider initialization."""
        provider = AnthropicProvider(
            name="anthropic",
            api_key="sk-ant-test",
            default_model="claude-3-5-sonnet-20241022"
        )
        assert provider.name == "anthropic"
        assert provider.headers["x-api-key"] == "sk-ant-test"
        assert provider.default_model == "claude-3-5-sonnet-20241022"
    
    def test_initialization_missing_api_key_raises(self):
        """Test missing API key raises error."""
        with pytest.raises(ValueError, match="requires API key"):
            AnthropicProvider(name="anthropic")
    
    @patch('requests.post')
    def test_chat_completion(self, mock_post):
        """Test chat completion."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "model": "claude-3-5-sonnet-20241022",
            "content": [
                {"type": "text", "text": "Hello!"}
            ],
            "stop_reason": "end_turn",
            "usage": {
                "input_tokens": 10,
                "output_tokens": 5
            }
        }
        mock_post.return_value = mock_response
        
        provider = AnthropicProvider(
            name="anthropic",
            api_key="sk-ant-test",
            default_model="claude-3-5-sonnet-20241022"
        )
        
        response = provider.chat(messages=[
            {"role": "user", "content": "Hi"}
        ])
        
        assert response.content == "Hello!"
        assert response.model == "claude-3-5-sonnet-20241022"
        assert response.usage["prompt_tokens"] == 10
        assert response.usage["completion_tokens"] == 5
    
    @patch('requests.post')
    def test_system_message_handling(self, mock_post):
        """Test system message is extracted properly."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "model": "claude-3-5-sonnet-20241022",
            "content": [{"type": "text", "text": "Response"}],
            "stop_reason": "end_turn"
        }
        mock_post.return_value = mock_response
        
        provider = AnthropicProvider(
            name="anthropic",
            api_key="sk-ant-test",
            default_model="claude-3-5-sonnet-20241022"
        )
        
        provider.chat(messages=[
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "Hi"}
        ])
        
        # Verify system message was extracted
        call_args = mock_post.call_args[1]["json"]
        assert call_args["system"] == "You are helpful."
        assert len(call_args["messages"]) == 1
        assert call_args["messages"][0]["role"] == "user"
    
    def test_list_models(self):
        """Test model listing returns hardcoded list."""
        provider = AnthropicProvider(
            name="anthropic",
            api_key="sk-ant-test"
        )
        
        models = provider.list_models()
        
        assert len(models) > 0
        assert "claude-3-5-sonnet-20241022" in models


class TestProviderPresets:
    """Test provider preset configurations."""
    
    def test_nvidia_preset(self):
        """Test NVIDIA preset configuration."""
        preset = PROVIDER_PRESETS["nvidia"]
        assert preset["endpoint"] == "https://integrate.api.nvidia.com/v1"
        assert preset["api_key_env"] == "NVIDIA_API_KEY"
        assert "llama" in preset["default_model"]
    
    def test_perplexity_preset(self):
        """Test Perplexity preset configuration."""
        preset = PROVIDER_PRESETS["perplexity"]
        assert preset["endpoint"] == "https://api.perplexity.ai"
        assert preset["api_key_env"] == "PERPLEXITY_API_KEY"
    
    def test_github_preset(self):
        """Test GitHub Models preset configuration."""
        preset = PROVIDER_PRESETS["github"]
        assert preset["endpoint"] == "https://models.inference.ai.azure.com"
        assert preset["api_key_env"] == "GITHUB_TOKEN"
    
    def test_groq_preset(self):
        """Test Groq preset configuration."""
        preset = PROVIDER_PRESETS["groq"]
        assert preset["endpoint"] == "https://api.groq.com/openai/v1"
        assert preset["api_key_env"] == "GROQ_API_KEY"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
