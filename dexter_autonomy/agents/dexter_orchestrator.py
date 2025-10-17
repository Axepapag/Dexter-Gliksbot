from __future__ import annotations

import asyncio
import json
import re
from typing import Any, Dict, List, Optional
from pathlib import Path

import yaml

from ..core.triple_bus import TripleBusSystem, MainTopic, CollabTopic, PrivateTopic
from ..core.policy_overlay import CompositeDenyPolicy
from ..brain.memory import BrainDB
from ..agents.action_executor import ActionExecutor
from ..agents.bsm import BSM
from ..agents.chatdock import ChatDockAgent
from .adapters.ollama_adapter import OllamaClient


class DexterOrchestrator:
    """Dexter - Central Orchestrator Agent for the autonomy system."""
    
    def _load_master_deny_list(self) -> Dict[str, Any]:
        """Load the master deny list from configuration."""
        try:
            config_path = Path("configs/denylist.master.yml")
            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    return yaml.safe_load(f) or {}
            else:
                # Return empty deny list if file doesn't exist
                return {}
        except Exception as e:
            # Log error but don't fail initialization
            print(f"Warning: Could not load master deny list: {e}")
            return {}
    
    def __init__(
        self,
        buses: TripleBusSystem,
        policy: CompositeDenyPolicy,
        brain: BrainDB,
        executor: ActionExecutor,
        bsm: BSM,
        chatdock: ChatDockAgent,
        config: Dict[str, Any]
    ) -> None:
        self.buses = buses
        self.policy = policy
        self.brain = brain
        self.executor = executor
        self.bsm = bsm
        self.chatdock = chatdock
        self.config = config
        
        # Load master deny list
        self.master_deny_list = self._load_master_deny_list()
        
        # Initialize Dexter's slot configuration
        self.dexter_slot = config.get("slots", {}).get("dexter-orchestrator", {})
        self.ollama_client = OllamaClient(
            host=self.dexter_slot.get("endpoint", "http://127.0.0.1:11434"),
            api_key_env=self.dexter_slot.get("api_key_env", "OLLAMA_CLOUD_KEY"),
            default_options=self.dexter_slot.get("ollama_options", {})
        )
        
        # Track active agents and operations
        self.active_agents: Dict[str, Dict[str, Any]] = {}
        self.active_operations: Dict[str, Dict[str, Any]] = {}
        
        # Conversation history
        self.conversation_history: List[Dict[str, str]] = []
        
        # Register for relevant events on MAIN bus
        # Dexter monitors ALL buses, but primarily interacts on MAIN
        self.buses.main.subscribe(MainTopic.INTENT, self.handle_intent)
        self.buses.main.subscribe(MainTopic.EFFECT, self.handle_effect)
        # Keep SYSTEM subscription for backward compatibility (consider migrating to CollabTopic)
        # For now, we'll handle SYSTEM on main bus as well
        self.buses.main.subscribe(MainTopic.TRACE, self.handle_system_event)  # Map SYSTEM to TRACE temporarily

    async def _invoke_ollama_chat(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Invoke Ollama chat in a thread-safe manner."""
        loop = asyncio.get_running_loop()
        model = self.dexter_slot.get("model", "deepseek-v3.1:671b-cloud")
        merged_options: Dict[str, Any] = dict(self.dexter_slot.get("ollama_options", {}))
        if options:
            merged_options.update({k: v for k, v in options.items() if v is not None})

        return await loop.run_in_executor(
            None,
            lambda: self.ollama_client.chat(
                model=model,
                messages=messages,
                temperature=temperature,
                options=merged_options,
            ),
        )
    
    def _extract_actions(self, text: str) -> List[Dict[str, Any]]:
        """
        Extract structured actions from text response.
        Merged AUM functionality - Dexter can now extract actions in single LLM call.
        
        Looks for JSON arrays in the response containing action objects with:
        - kind: type, hotkey, click, ocr
        - args: action-specific arguments
        - rationale: reason for the action
        
        Falls back to deterministic parsing if LLM doesn't provide structured actions.
        """
        # Try to find JSON array in the text
        match = re.search(r'\[.*?\]', text, re.DOTALL)
        if match:
            try:
                actions = json.loads(match.group(0))
                if isinstance(actions, list):
                    # Validate structure
                    valid_actions = []
                    for action in actions:
                        if isinstance(action, dict) and 'kind' in action and 'args' in action:
                            valid_actions.append(action)
                    if valid_actions:
                        return valid_actions
            except (json.JSONDecodeError, ValueError):
                pass
        
        # Fallback: deterministic parsing
        return self._parse_actions_fallback(text)
    
    def _parse_actions_fallback(self, text: str) -> List[Dict[str, Any]]:
        """
        Deterministic fallback for action extraction.
        Looks for common patterns in text to infer actions.
        """
        actions = []
        text_lower = text.lower()
        
        # Pattern: "click at (x, y)" or "click x,y" or "click (x,y)"
        click_patterns = [
            r'click\s+at\s*\(?\s*(\d+)\s*,\s*(\d+)\s*\)?',
            r'click\s+\(?\s*(\d+)\s*,\s*(\d+)\s*\)?',
        ]
        for pattern in click_patterns:
            matches = re.finditer(pattern, text_lower)
            for match in matches:
                actions.append({
                    "kind": "click",
                    "args": {"x": int(match.group(1)), "y": int(match.group(2))},
                    "rationale": "Extracted from text instruction"
                })
        
        # Pattern: "press CTRL+S" or "hotkey CTRL+S" (prioritize compound keys)
        hotkey_patterns = [
            r'(?:press|hotkey)\s+([A-Z]+(?:\+[A-Z0-9]+)+)',  # Compound keys (CTRL+S, ALT+F4)
        ]
        for pattern in hotkey_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                chord = match.group(1).upper()
                actions.append({
                    "kind": "hotkey",
                    "args": {"chord": chord},
                    "rationale": "Extracted from text instruction"
                })
        
        # Pattern: "type 'text'" or 'type "text"'
        type_patterns = [
            r'type\s+["\']([^"\']+)["\']',
            r'enter\s+["\']([^"\']+)["\']',
            r'input\s+["\']([^"\']+)["\']',
        ]
        for pattern in type_patterns:
            matches = re.finditer(pattern, text_lower)
            for match in matches:
                actions.append({
                    "kind": "type",
                    "args": {"text": match.group(1)},
                    "rationale": "Extracted from text instruction"
                })
        
        # Pattern: "ocr" or "capture screen"
        if re.search(r'\b(ocr|capture\s+screen|screenshot)\b', text_lower):
            actions.append({
                "kind": "ocr",
                "args": {},
                "rationale": "Extracted from text instruction"
            })
        
        return actions
    
    def _build_action_extraction_prompt(self) -> str:
        """
        Build system prompt that includes action extraction instructions.
        This enables Dexter to converse AND extract actions in single call.
        """
        base_prompt = self.dexter_slot.get("system_prompt", "")
        
        action_schema = """
When you need to execute UI actions, include them in your response as a JSON array.

SUPPORTED ACTIONS:
1. Type text: {"kind": "type", "args": {"text": "hello world"}, "rationale": "entering greeting"}
2. Hotkey: {"kind": "hotkey", "args": {"chord": "CTRL+S"}, "rationale": "saving file"}
3. Click: {"kind": "click", "args": {"x": 100, "y": 200}, "rationale": "clicking submit button"}
4. OCR: {"kind": "ocr", "args": {}, "rationale": "capturing screen text"}

Example response with actions:
"I'll save the file now. [{'kind': 'hotkey', 'args': {'chord': 'CTRL+S'}, 'rationale': 'saving file'}]"

Include actions ONLY when actually executing UI operations. Regular conversation doesn't need actions.
"""
        
        return base_prompt + "\n\n" + action_schema

    def _resolve_participants(self) -> List[str]:
        participants = list(self.active_agents.keys())
        if not participants:
            participants = ["chatdock", "action-executor"]
        if "dexter" not in participants:
            participants.insert(0, "dexter")
        return participants

    def _requires_collaboration(self, message: str) -> bool:
        text = (message or "").lower()
        triggers = [
            "work together",
            "collaborate",
            "collaboration",
            "coordinate",
            "refine",
            "help each other",
        ]
        if any(term in text for term in triggers):
            return True
        return "plan" in text and "before" in text

    async def _publish_council_event(self, payload: Dict[str, Any]) -> None:
        """Publish collaboration event to COLLAB bus"""
        enriched = dict(payload)
        enriched.setdefault("source", "dexter")
        # COUNCIL events map to COLLAB bus (collaboration)
        # Determine appropriate topic based on event type
        event_type = enriched.get("event", "observation")
        if event_type == "agent_message":
            await self.buses.collab.publish(CollabTopic.OBSERVATION, enriched)
        else:
            await self.buses.collab.publish(CollabTopic.OBSERVATION, enriched)

    async def _generate_collaboration_plan(
        self,
        user_message: str,
        participants: List[str],
        context: Dict[str, Any],
    ) -> str:
        system_instructions = (
            self.dexter_slot.get("system_prompt", "")
            + "\nYou are orchestrating a multi-agent collaboration."
            " Produce a structured plan before execution occurs."
            " Respond in Markdown with sections: Objective, Participants, Plan (numbered steps),"
            " Refinement, Risks, Next Actions."
        )
        user_payload = (
            f"Problem statement: {user_message}\n"
            f"Participants: {', '.join(participants)}\n"
            f"Context snapshot: {json.dumps(context, ensure_ascii=False)}"
        )
        messages = [
            {"role": "system", "content": system_instructions},
            {"role": "user", "content": user_payload},
        ]
        return await self._invoke_ollama_chat(messages)

    async def send_agent_message(self, sender: str, recipients: Optional[List[str]], message: str) -> None:
        targets = recipients or [p for p in self._resolve_participants() if p != sender]
        event = {
            "event": "agent_message",
            "from": sender,
            "to": targets,
            "message": message,
        }
        self.conversation_history.append({"role": sender, "content": json.dumps(event)})
        await self._publish_council_event(event)

    def update_configuration(
        self,
        policy: CompositeDenyPolicy,
        executor: ActionExecutor,
        aum: AUM,
        bsm: BSM,
        chatdock: ChatDockAgent,
        config: Dict[str, Any],
    ) -> None:
        """Refresh Dexter's view when slots or policies change."""
        self.policy = policy
        self.executor = executor
        self.aum = aum
        self.bsm = bsm
        self.chatdock = chatdock
        self.config = config
        self.dexter_slot = config.get("slots", {}).get("dexter-orchestrator", {})
        self.ollama_client = OllamaClient(
            host=self.dexter_slot.get("endpoint", "http://127.0.0.1:11434"),
            api_key_env=self.dexter_slot.get("api_key_env", "OLLAMA_CLOUD_KEY"),
            default_options=self.dexter_slot.get("ollama_options", {}),
        )
    
    async def handle_intent(self, intent: Dict[str, Any]) -> Dict[str, Any]:
        """Handle incoming intents and route them through Dexter's validation."""
        # Add to conversation history
        self.conversation_history.append({
            "role": "user",
            "content": json.dumps(intent)
        })
        
        # Check if this is a direct communication with Dexter
        if intent.get("target") == "dexter":
            return await self.handle_direct_communication(intent)
        
        # For all other intents, validate against deny list first
        validation_result = await self.validate_intent(intent)
        if not validation_result["allowed"]:
            # Log the denied intent to MAIN bus (TRACE for logging)
            await self.buses.main.publish(MainTopic.TRACE, {
                "event": "intent_denied",
                "intent": intent,
                "reason": validation_result["reason"]
            })
            
            # Notify the user via EFFECT
            await self.buses.main.publish(MainTopic.EFFECT, {
                "status": "denied",
                "detail": {
                    "reason": validation_result["reason"],
                    "intent": intent
                }
            })
            
            return {
                "status": "denied",
                "reason": validation_result["reason"]
            }
        
        # Route to appropriate agent
        return await self.route_intent_to_agent(intent)
    
    async def handle_effect(self, effect: Dict[str, Any]) -> None:
        """Handle effects from agents and update Dexter's knowledge."""
        # Add to conversation history
        self.conversation_history.append({
            "role": "system",
            "content": json.dumps(effect)
        })
        
        # Update brain with the effect
        await self.update_brain_with_effect(effect)
        
        # Check if any active operations need updating
        await self.update_operation_status(effect)
    
    async def handle_system_event(self, event: Dict[str, Any]) -> None:
        """Handle system events and maintain oversight."""
        # System events arrive on the dedicated SYSTEM topic
        event_type = event.get("event")
        
        if event_type == "agent_registered":
            self.active_agents[event["agent_id"]] = {
                "status": "active",
                "last_seen": asyncio.get_event_loop().time(),
                "capabilities": event.get("capabilities", [])
            }
        elif event_type == "agent_deregistered":
            if event["agent_id"] in self.active_agents:
                del self.active_agents[event["agent_id"]]
        elif event_type == "operation_started":
            self.active_operations[event["operation_id"]] = {
                "status": "running",
                "agent": event["agent_id"],
                "start_time": asyncio.get_event_loop().time(),
                "description": event.get("description", "")
            }
        elif event_type == "operation_completed":
            if event["operation_id"] in self.active_operations:
                self.active_operations[event["operation_id"]]["status"] = "completed"
                self.active_operations[event["operation_id"]]["end_time"] = asyncio.get_event_loop().time()
    
    async def handle_direct_communication(self, intent: Dict[str, Any]) -> Dict[str, Any]:
        """Handle direct communication with Dexter."""
        user_message = intent.get("message", "")

        context = {
            "active_agents": self.active_agents,
            "active_operations": self.active_operations,
            "policy_status": "active",
            "brain_summary": await self.get_brain_summary(),
            "conversation_history": self.conversation_history[-10:],
        }

        participants = self._resolve_participants()

        if self._requires_collaboration(user_message):
            plan = await self._generate_collaboration_plan(user_message, participants, context)
            self.conversation_history.append({"role": "assistant", "content": plan})

            await self._publish_council_event(
                {
                    "event": "collaboration_plan",
                    "plan": plan,
                    "participants": participants,
                    "request": user_message,
                }
            )

            await self.brain.store_effect(
                {
                    "status": "plan",
                    "detail": {"plan": plan, "participants": participants},
                    "intent": intent,
                }
            )

            return {
                "status": "success",
                "response": plan,
                "target": "user",
                "participants": participants,
                "collaboration_plan": plan,
            }

        # Use enhanced system prompt with action extraction capability
        system_prompt = self._build_action_extraction_prompt()
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]

        try:
            response = await self._invoke_ollama_chat(messages)
            self.conversation_history.append({"role": "assistant", "content": response})
            
            # Extract actions from response (merged AUM functionality)
            actions = self._extract_actions(response)
            actions_count = len(actions)
            
            # If actions were extracted, validate and execute them
            if actions:
                validated_actions = []
                for action in actions:
                    validation = await self.validate_intent({
                        "kind": action["kind"],
                        "args": action["args"]
                    })
                    if validation["allowed"]:
                        validated_actions.append(action)
                    else:
                        # Log denied action to MAIN bus (TRACE for logging)
                        await self.buses.main.publish(MainTopic.TRACE, {
                            "event": "action_denied",
                            "action": action,
                            "reason": validation["reason"]
                        })
                
                # Execute validated actions
                execution_results = []
                if validated_actions:
                    for action in validated_actions:
                        result = await self.executor.handle_intent({
                            "kind": action["kind"],
                            "args": action["args"]
                        })
                        execution_results.append(result)
                
                return {
                    "status": "success",
                    "response": response,
                    "target": "user",
                    "actions_extracted": len(actions),
                    "actions_executed": len(validated_actions),
                    "execution_results": execution_results
                }
            
            return {
                "status": "success",
                "response": response,
                "target": "user",
                "actions_extracted": actions_count
            }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
            }
    
    async def validate_intent(self, intent: Dict[str, Any]) -> Dict[str, Any]:
        """Validate intent against the deny list as the single source of truth."""
        intent_kind = intent.get("kind", "")
        intent_args = intent.get("args", {})
        
        # Check against master deny list first
        master_validation = self._validate_against_master_deny_list(intent_kind, intent_args)
        if not master_validation["allowed"]:
            return master_validation
        
        # Then check against current policy
        policy_validation = self._validate_against_policy(intent_kind, intent_args)
        if not policy_validation["allowed"]:
            return policy_validation
        
        return {"allowed": True, "reason": "passed validation"}
    
    def _validate_against_master_deny_list(self, intent_kind: str, intent_args: Dict[str, Any]) -> Dict[str, Any]:
        """Validate intent against the master deny list."""
        # Check process commands
        if intent_kind == "execute_process":
            cmd = intent_args.get("command", "")
            process_deny = self.master_deny_list.get("process", {}).get("deny_cmd_patterns", [])
            import fnmatch
            for pattern in process_deny:
                if fnmatch.fnmatch(cmd, pattern):
                    return {"allowed": False, "reason": f"command denied by master deny list: {pattern}"}
        
        # Check file operations
        if intent_kind in ["read_file", "write_file"]:
            path = intent_args.get("path", "")
            write = intent_kind == "write_file"
            
            if write:
                file_deny = self.master_deny_list.get("files", {}).get("deny_write_globs", [])
            else:
                file_deny = self.master_deny_list.get("files", {}).get("deny_read_globs", [])
            
            import fnmatch
            for pattern in file_deny:
                if fnmatch.fnmatch(path, pattern):
                    return {"allowed": False, "reason": f"path denied by master deny list: {pattern}"}
            
            dir_deny = self.master_deny_list.get("files", {}).get("deny_dirs", [])
            for dir_pattern in dir_deny:
                if str(path).startswith(str(dir_pattern)):
                    return {"allowed": False, "reason": f"directory denied by master deny list: {dir_pattern}"}
        
        # Check network operations
        if intent_kind == "network_request":
            url = intent_args.get("url", "")
            
            # Check URL regex patterns
            import re
            url_deny_regex = self.master_deny_list.get("network", {}).get("deny_url_regex", [])
            for pattern in url_deny_regex:
                if re.search(pattern, url):
                    return {"allowed": False, "reason": f"URL denied by master deny list regex: {pattern}"}
            
            # Check hosts
            host_deny = self.master_deny_list.get("network", {}).get("deny_hosts", [])
            for host in host_deny:
                if host in url:
                    return {"allowed": False, "reason": f"host denied by master deny list: {host}"}
        
        # Check hotkey operations
        if intent_kind == "hotkey":
            chord = intent_args.get("chord", "")
            hotkey_deny = self.master_deny_list.get("hotkeys", {}).get("deny", [])
            for denied_chord in hotkey_deny:
                if denied_chord.upper() == chord.upper():
                    return {"allowed": False, "reason": f"hotkey denied by master deny list: {denied_chord}"}
        
        # Check input length/content
        if intent_kind == "type_text":
            text = intent_args.get("text", "")
            max_chars = self.master_deny_list.get("input", {}).get("max_chars", 0)
            if max_chars and len(text) > max_chars:
                return {"allowed": False, "reason": f"text too long (max {max_chars} chars)"}
            
            # Check input regex patterns
            import re
            input_deny_regex = self.master_deny_list.get("input", {}).get("deny_regex", [])
            for pattern in input_deny_regex:
                if re.search(pattern, text):
                    return {"allowed": False, "reason": f"content denied by master deny list pattern: {pattern}"}
        
        return {"allowed": True, "reason": "passed master deny list validation"}
    
    def _validate_against_policy(self, intent_kind: str, intent_args: Dict[str, Any]) -> Dict[str, Any]:
        """Validate intent against the current policy."""
        # Check process commands
        if intent_kind == "execute_process":
            cmd = intent_args.get("command", "")
            allowed, reason = self.policy.allow_process(cmd)
            if not allowed:
                return {"allowed": False, "reason": reason}
        
        # Check file operations
        if intent_kind in ["read_file", "write_file"]:
            path = intent_args.get("path", "")
            write = intent_kind == "write_file"
            allowed, reason = self.policy.allow_path(path, write=write)
            if not allowed:
                return {"allowed": False, "reason": reason}
        
        # Check network operations
        if intent_kind == "network_request":
            url = intent_args.get("url", "")
            allowed, reason = self.policy.allow_url(url)
            if not allowed:
                return {"allowed": False, "reason": reason}
        
        # Check hotkey operations
        if intent_kind == "hotkey":
            chord = intent_args.get("chord", "")
            allowed, reason = self.policy.allow_hotkey(chord)
            if not allowed:
                return {"allowed": False, "reason": reason}
        
        # Check input length/content
        if intent_kind == "type_text":
            text = intent_args.get("text", "")
            allowed, reason = self.policy.allow_input(text)
            if not allowed:
                return {"allowed": False, "reason": reason}
        
        return {"allowed": True, "reason": "passed policy validation"}
    
    async def route_intent_to_agent(self, intent: Dict[str, Any]) -> Dict[str, Any]:
        """Route validated intents to appropriate agents."""
        intent_kind = intent.get("kind", "")
        
        # Route based on intent type
        if intent_kind.startswith("chatdock"):
            return await self.chatdock.handle_intent(intent)
        elif intent_kind in ["type_text", "type", "hotkey", "key", "click", "ocr"]:
            return await self.executor.handle_intent(intent)
        elif intent_kind == "nl_command":
            # Handle natural language commands through AUM
            text = str(intent.get("args", {}).get("text", "") or "")
            if text:
                actions = self.aum.extract(text)
                context = {"source": "nl_command", "prompt": text}
                return await self.executor.run_actions(intent, actions, context)
            else:
                payload = {
                    "status": "error",
                    "detail": {"reason": "No text provided for nl_command"},
                    "intent": intent,
                }
                await self.buses.main.publish(MainTopic.EFFECT, payload)
                return payload
        else:
            # For other intents, try to extract actions using AUM
            # This is a fallback for complex planning
            text = str(intent.get("args", {}).get("text", "") or "")
            if text:
                actions = self.aum.extract(text)
                return await self.executor.run_actions(intent, actions)
            else:
                payload = {
                    "status": "unknown_intent",
                    "detail": {"reason": f"unsupported intent kind '{intent_kind}'"},
                    "intent": intent,
                }
                await self.buses.main.publish(MainTopic.EFFECT, payload)
                return payload
    
    async def update_brain_with_effect(self, effect: Dict[str, Any]) -> None:
        """Update the brain/memory system with new effects."""
        try:
            # Create a summary of the effect for memory storage
            summary = {
                "timestamp": asyncio.get_event_loop().time(),
                "effect_type": effect.get("status", "unknown"),
                "intent": effect.get("intent", {}),
                "details": effect.get("detail", {})
            }
            
            # Store in brain
            await self.brain.store_effect(summary)
        except Exception as e:
            # Log error but don't fail the operation (use TRACE for logging)
            await self.buses.main.publish(MainTopic.TRACE, {
                "event": "brain_update_error",
                "error": str(e)
            })
    
    async def update_operation_status(self, effect: Dict[str, Any]) -> None:
        """Update the status of active operations based on effects."""
        # This would contain logic to track operation progress
        pass
    
    async def get_brain_summary(self) -> Dict[str, Any]:
        """Get a summary of the current brain state."""
        try:
            return await self.brain.get_summary()
        except Exception:
            return {"status": "unavailable"}
    
    def _build_dexter_prompt(self, user_message: str, context: Dict[str, Any]) -> str:
        """Build a comprehensive prompt for Dexter's responses."""
        prompt = f"""You are Dexter, the central orchestrator of this autonomy system. 

USER MESSAGE:
{user_message}

CONTEXT:
Active Agents: {len(context['active_agents'])} agents currently active
Active Operations: {len(context['active_operations'])} operations running
Policy Status: {context['policy_status']}
Brain Summary: {context['brain_summary']}

CONVERSATION HISTORY:
"""
        
        for msg in context['conversation_history']:
            prompt += f"{msg['role']}: {msg['content']}\n"
        
        prompt += "\nRespond as Dexter, providing guidance, coordination, and oversight as needed."
        
        return prompt
    
    async def register_agent(self, agent_id: str, capabilities: List[str]) -> None:
        """Register a new agent with Dexter."""
        # System events go to TRACE topic on MAIN bus
        await self.buses.main.publish(MainTopic.TRACE, {
            "event": "agent_registered",
            "agent_id": agent_id,
            "capabilities": capabilities
        })
    
    async def deregister_agent(self, agent_id: str) -> None:
        """Deregister an agent from Dexter."""
        await self.buses.main.publish(MainTopic.TRACE, {
            "event": "agent_deregistered",
            "agent_id": agent_id
        })
    
    async def start_operation(self, operation_id: str, agent_id: str, description: str) -> None:
        """Start tracking a new operation."""
        await self.buses.main.publish(MainTopic.TRACE, {
            "event": "operation_started",
            "operation_id": operation_id,
            "agent_id": agent_id,
            "description": description
        })
    
    async def complete_operation(self, operation_id: str) -> None:
        """Mark an operation as completed."""
        await self.buses.main.publish(MainTopic.TRACE, {
            "event": "operation_completed",
            "operation_id": operation_id
        })
