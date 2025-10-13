from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

from ..tools.common.actions import parse_actions_fallback
from .adapters.ollama_adapter import OllamaClient

DEFAULT_AUM_PROMPT = (
    "You are an action extraction model. Return a JSON array of actions with fields "
    "`kind`, `args`, and `rationale`. Allowed kinds: "
    "type {\"text\": \"...\"}, hotkey {\"chord\": \"CTRL+S\"}, "
    "click {\"x\": <int>, \"y\": <int>}, ocr {}. "
    "Ground responses strictly in the supplied UI transcript.\n<<<\n{ui}\n>>>"
)

DEFAULT_AUM_SYSTEM = "You must reply with JSON only. No prose."


class AUM:
    def __init__(
        self,
        model: str | None,
        host: str,
        temperature: float = 0.1,
        *,
        api_key_env: str | None = None,
        system_prompt: str | None = None,
        prompt: str | None = None,
        client_options: Optional[Dict[str, object]] = None,
        call_options: Optional[Dict[str, object]] = None,
    ) -> None:
        self.model = model
        self.temperature = temperature
        self.prompt = prompt or DEFAULT_AUM_PROMPT
        self.system_prompt = system_prompt or DEFAULT_AUM_SYSTEM
        self.call_options = dict(call_options or {})

        self.ollama = (
            OllamaClient(host, api_key_env=api_key_env, default_options=client_options)
            if model
            else None
        )

    def extract(self, ui_text: str) -> List[Dict[str, Any]]:
        if not self.ollama or not self.model:
            return parse_actions_fallback(ui_text)

        prompt_body = self.prompt.replace("{ui}", ui_text[:4000])
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": prompt_body},
        ]
        try:
            out = self.ollama.chat(
                self.model,
                messages,
                temperature=self.temperature,
                options=self.call_options,
            )
            match = re.search(r"\[.*\]", out, re.DOTALL)
            if match:
                return json.loads(match.group(0))
        except Exception:
            # fall back to deterministic parser on any failure
            pass
        return parse_actions_fallback(ui_text)
