"""
Tests for Merged AUM Functionality in Dexter Orchestrator

Tests the action extraction capability that was merged from AUM into Dexter.
Dexter can now converse AND extract actions in a single LLM call.
"""
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from dexter_autonomy.agents.dexter_orchestrator import DexterOrchestrator
from dexter_autonomy.core.event_bus import EventBus
from dexter_autonomy.core.policy_overlay import CompositeDenyPolicy
from dexter_autonomy.brain.memory import BrainDB


@pytest_asyncio.fixture
async def mock_dexter():
    """Create a mock Dexter orchestrator for testing"""
    # Create mock dependencies
    bus = AsyncMock(spec=EventBus)
    bus.publish = AsyncMock()
    bus.subscribe = MagicMock()
    
    policy = MagicMock(spec=CompositeDenyPolicy)
    policy.allow_input = MagicMock(return_value=(True, ""))
    policy.allow_hotkey = MagicMock(return_value=(True, ""))
    policy.allow_path = MagicMock(return_value=(True, ""))
    policy.allow_process = MagicMock(return_value=(True, ""))
    policy.allow_url = MagicMock(return_value=(True, ""))
    
    brain = AsyncMock(spec=BrainDB)
    brain.store_effect = AsyncMock()
    brain.get_summary = AsyncMock(return_value={"status": "ok"})
    
    executor = AsyncMock()
    executor.handle_intent = AsyncMock(return_value={"status": "ok"})
    
    aum = MagicMock()
    bsm = AsyncMock()
    chatdock = AsyncMock()
    
    config = {
        "slots": {
            "dexter-orchestrator": {
                "endpoint": "http://127.0.0.1:11434",
                "model": "qwen2.5:3b-instruct",
                "system_prompt": "You are Dexter, the orchestrator.",
                "ollama_options": {},
                "api_key_env": "OLLAMA_API_KEY"
            }
        }
    }
    
    # Create orchestrator
    with patch('dexter_autonomy.agents.dexter_orchestrator.Path.exists', return_value=False):
        dexter = DexterOrchestrator(
            bus=bus,
            policy=policy,
            brain=brain,
            executor=executor,
            aum=aum,
            bsm=bsm,
            chatdock=chatdock,
            config=config
        )
    
    return dexter


def test_extract_actions_from_json(mock_dexter):
    """Test extracting actions from JSON in response"""
    text_with_actions = """I'll save the file now. [{"kind": "hotkey", "args": {"chord": "CTRL+S"}, "rationale": "saving file"}]"""
    
    actions = mock_dexter._extract_actions(text_with_actions)
    
    assert len(actions) == 1
    assert actions[0]["kind"] == "hotkey"
    assert actions[0]["args"]["chord"] == "CTRL+S"
    assert actions[0]["rationale"] == "saving file"


def test_extract_multiple_actions(mock_dexter):
    """Test extracting multiple actions from response"""
    text = """I'll type and save. [
        {"kind": "type", "args": {"text": "hello"}, "rationale": "greeting"},
        {"kind": "hotkey", "args": {"chord": "CTRL+S"}, "rationale": "saving"}
    ]"""
    
    actions = mock_dexter._extract_actions(text)
    
    assert len(actions) == 2
    assert actions[0]["kind"] == "type"
    assert actions[1]["kind"] == "hotkey"


def test_fallback_click_pattern(mock_dexter):
    """Test fallback parsing for click actions"""
    text = "Please click at (100, 200)"
    
    actions = mock_dexter._parse_actions_fallback(text)
    
    assert len(actions) == 1
    assert actions[0]["kind"] == "click"
    assert actions[0]["args"]["x"] == 100
    assert actions[0]["args"]["y"] == 200


def test_fallback_hotkey_pattern(mock_dexter):
    """Test fallback parsing for hotkey actions"""
    text = "Press CTRL+S to save"
    
    actions = mock_dexter._parse_actions_fallback(text)
    
    assert len(actions) == 1
    assert actions[0]["kind"] == "hotkey"
    assert actions[0]["args"]["chord"] == "CTRL+S"


def test_fallback_type_pattern(mock_dexter):
    """Test fallback parsing for type actions"""
    text = 'Type "hello world"'
    
    actions = mock_dexter._parse_actions_fallback(text)
    
    assert len(actions) == 1
    assert actions[0]["kind"] == "type"
    assert actions[0]["args"]["text"] == "hello world"


def test_fallback_ocr_pattern(mock_dexter):
    """Test fallback parsing for OCR actions"""
    text = "Capture screen with OCR"
    
    actions = mock_dexter._parse_actions_fallback(text)
    
    assert len(actions) == 1
    assert actions[0]["kind"] == "ocr"


def test_no_actions_in_regular_conversation(mock_dexter):
    """Test that regular conversation doesn't extract false actions"""
    text = "Hello! How can I help you today?"
    
    actions = mock_dexter._extract_actions(text)
    
    assert len(actions) == 0


def test_action_extraction_prompt_includes_schema(mock_dexter):
    """Test that action extraction prompt includes action schema"""
    prompt = mock_dexter._build_action_extraction_prompt()
    
    assert "SUPPORTED ACTIONS" in prompt
    assert "type" in prompt
    assert "hotkey" in prompt
    assert "click" in prompt
    assert "ocr" in prompt
    assert "JSON array" in prompt


@pytest.mark.asyncio
async def test_handle_communication_with_actions(mock_dexter):
    """Test handling user communication that includes actions"""
    # Mock LLM response with actions
    with patch.object(mock_dexter, '_invoke_ollama_chat', new_callable=AsyncMock) as mock_chat:
        mock_chat.return_value = 'I\'ll save the file. [{"kind": "hotkey", "args": {"chord": "CTRL+S"}, "rationale": "saving"}]'
        
        result = await mock_dexter.handle_direct_communication({
            "target": "dexter",
            "message": "Please save the file"
        })
        
        assert result["status"] == "success"
        assert result["actions_extracted"] == 1
        assert result["actions_executed"] == 1
        
        # Verify executor was called
        assert mock_dexter.executor.handle_intent.called


@pytest.mark.asyncio
async def test_handle_communication_without_actions(mock_dexter):
    """Test handling user communication without actions"""
    with patch.object(mock_dexter, '_invoke_ollama_chat', new_callable=AsyncMock) as mock_chat:
        mock_chat.return_value = "Hello! I'm ready to help."
        
        result = await mock_dexter.handle_direct_communication({
            "target": "dexter",
            "message": "Hello Dexter"
        })
        
        assert result["status"] == "success"
        assert result["actions_extracted"] == 0
        
        # Verify executor was NOT called
        assert not mock_dexter.executor.handle_intent.called


@pytest.mark.asyncio
async def test_action_validation_before_execution(mock_dexter):
    """Test that actions are validated against policy before execution"""
    # Mock denied policy
    mock_dexter.policy.allow_hotkey = MagicMock(return_value=(False, "Hotkey denied"))
    
    with patch.object(mock_dexter, '_invoke_ollama_chat', new_callable=AsyncMock) as mock_chat:
        mock_chat.return_value = '[{"kind": "hotkey", "args": {"chord": "ALT+F4"}, "rationale": "closing"}]'
        
        result = await mock_dexter.handle_direct_communication({
            "target": "dexter",
            "message": "Close the window"
        })
        
        assert result["status"] == "success"
        assert result["actions_extracted"] == 1
        assert result["actions_executed"] == 0  # Action was denied
        
        # Verify executor was NOT called (action denied)
        assert not mock_dexter.executor.handle_intent.called


@pytest.mark.asyncio
async def test_mixed_valid_and_invalid_actions(mock_dexter):
    """Test handling mix of valid and invalid actions"""
    # First hotkey allowed, second denied
    def mock_allow_hotkey(chord):
        if chord == "CTRL+S":
            return (True, "")
        else:
            return (False, "Denied")
    
    mock_dexter.policy.allow_hotkey = MagicMock(side_effect=mock_allow_hotkey)
    
    with patch.object(mock_dexter, '_invoke_ollama_chat', new_callable=AsyncMock) as mock_chat:
        mock_chat.return_value = '''[
            {"kind": "hotkey", "args": {"chord": "CTRL+S"}, "rationale": "save"},
            {"kind": "hotkey", "args": {"chord": "ALT+F4"}, "rationale": "close"}
        ]'''
        
        result = await mock_dexter.handle_direct_communication({
            "target": "dexter",
            "message": "Save and close"
        })
        
        assert result["status"] == "success"
        assert result["actions_extracted"] == 2
        assert result["actions_executed"] == 1  # Only first action executed


def test_complex_click_patterns(mock_dexter):
    """Test various click pattern formats"""
    patterns = [
        ("click at (100, 200)", 100, 200),
        ("click 150,250", 150, 250),
        ("click (300,400)", 300, 400),
    ]
    
    for text, expected_x, expected_y in patterns:
        actions = mock_dexter._parse_actions_fallback(text)
        assert len(actions) == 1
        assert actions[0]["args"]["x"] == expected_x
        assert actions[0]["args"]["y"] == expected_y


def test_multiple_actions_in_fallback(mock_dexter):
    """Test extracting multiple actions from fallback parser"""
    text = 'Type "hello" then press CTRL+S and click at (100, 200)'
    
    actions = mock_dexter._parse_actions_fallback(text)
    
    # Should extract all three actions
    kinds = [a["kind"] for a in actions]
    assert "type" in kinds
    assert "hotkey" in kinds
    assert "click" in kinds


def test_conversation_history_tracking(mock_dexter):
    """Test that conversation history is properly tracked"""
    initial_len = len(mock_dexter.conversation_history)
    
    mock_dexter.conversation_history.append({
        "role": "user",
        "content": "test message"
    })
    
    assert len(mock_dexter.conversation_history) == initial_len + 1
    assert mock_dexter.conversation_history[-1]["role"] == "user"


@pytest.mark.asyncio
async def test_error_handling_in_action_extraction(mock_dexter):
    """Test error handling when LLM response is malformed"""
    with patch.object(mock_dexter, '_invoke_ollama_chat', new_callable=AsyncMock) as mock_chat:
        # Return malformed JSON
        mock_chat.return_value = "I'll save [this is not valid json}"
        
        result = await mock_dexter.handle_direct_communication({
            "target": "dexter",
            "message": "Save file"
        })
        
        # Should not crash, should fall back
        assert result["status"] == "success"


def test_action_schema_validation(mock_dexter):
    """Test that extracted actions have required fields"""
    # Valid action
    text_valid = '[{"kind": "type", "args": {"text": "hello"}, "rationale": "greeting"}]'
    actions_valid = mock_dexter._extract_actions(text_valid)
    assert len(actions_valid) == 1
    
    # Invalid action (missing args)
    text_invalid = '[{"kind": "type", "rationale": "greeting"}]'
    actions_invalid = mock_dexter._extract_actions(text_invalid)
    assert len(actions_invalid) == 0  # Should be filtered out


@pytest.mark.asyncio
async def test_integration_with_existing_conversation(mock_dexter):
    """Test that action extraction works within ongoing conversation"""
    # Simulate conversation history
    mock_dexter.conversation_history = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi! How can I help?"},
    ]
    
    with patch.object(mock_dexter, '_invoke_ollama_chat', new_callable=AsyncMock) as mock_chat:
        mock_chat.return_value = 'I\'ll save it. [{"kind": "hotkey", "args": {"chord": "CTRL+S"}, "rationale": "save"}]'
        
        result = await mock_dexter.handle_direct_communication({
            "target": "dexter",
            "message": "Save the file"
        })
        
        assert result["status"] == "success"
        assert len(mock_dexter.conversation_history) > 2  # History extended
