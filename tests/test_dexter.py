"""Tests for the Dexter Orchestrator."""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch

from dexter_autonomy.agents.dexter_orchestrator import DexterOrchestrator
from dexter_autonomy.core.policy_overlay import CompositeDenyPolicy
from dexter_autonomy.core.event_bus import Topic


@pytest.fixture
def mock_bus():
    return Mock()


@pytest.fixture
def mock_policy():
    policy = Mock(spec=CompositeDenyPolicy)
    policy.allow_process.return_value = (True, "")
    policy.allow_path.return_value = (True, "")
    policy.allow_url.return_value = (True, "")
    policy.allow_hotkey.return_value = (True, "")
    policy.allow_input.return_value = (True, "")
    return policy


@pytest.fixture
def mock_brain():
    return Mock()


@pytest.fixture
def mock_executor():
    return Mock()


@pytest.fixture
def mock_aum():
    return Mock()


@pytest.fixture
def mock_bsm():
    return Mock()


@pytest.fixture
def mock_chatdock():
    return Mock()


@pytest.fixture
def mock_config():
    return {
        "slots": {
            "dexter-orchestrator": {
                "endpoint": "https://ollama.com",
                "api_key_env": "OLLAMA_CLOUD_KEY",
                "model": "deepseek-v3.1:671b-cloud",
                "system_prompt": "You are Dexter...",
                "ollama_options": {}
            }
        }
    }


@pytest.fixture
def dexter_orchestrator(mock_bus, mock_policy, mock_brain, mock_executor, 
                       mock_aum, mock_bsm, mock_chatdock, mock_config):
    with patch('dexter_autonomy.agents.dexter_orchestrator.OllamaClient'):
        orchestrator = DexterOrchestrator(
            bus=mock_bus,
            policy=mock_policy,
            brain=mock_brain,
            executor=mock_executor,
            aum=mock_aum,
            bsm=mock_bsm,
            chatdock=mock_chatdock,
            config=mock_config
        )
    return orchestrator


@pytest.mark.asyncio
async def test_dexter_initialization(dexter_orchestrator):
    """Test that Dexter initializes correctly."""
    assert dexter_orchestrator is not None
    assert len(dexter_orchestrator.conversation_history) == 0
    assert len(dexter_orchestrator.active_agents) == 0
    assert len(dexter_orchestrator.active_operations) == 0


@pytest.mark.asyncio
async def test_dexter_intent_validation(dexter_orchestrator):
    """Test that Dexter validates intents against the deny list."""
    # Test allowed intent
    intent = {
        "kind": "type_text",
        "args": {"text": "Hello, world!"}
    }
    
    result = await dexter_orchestrator.validate_intent(intent)
    assert result["allowed"] == True


@pytest.mark.asyncio
async def test_dexter_direct_communication(dexter_orchestrator):
    """Test direct communication with Dexter."""
    async def mock_chat(*args, **kwargs):
        return "Hello! I'm Dexter, your orchestrator."
    
    with patch.object(dexter_orchestrator.ollama_client, 'chat', side_effect=mock_chat):
        intent = {
            "target": "dexter",
            "message": "Hello Dexter!"
        }
        
        result = await dexter_orchestrator.handle_direct_communication(intent)
        assert result["status"] == "success"
        assert "Hello! I'm Dexter" in result["response"]
