from __future__ import annotations

import json
import re
from typing import Any, Dict, Optional

from ..brain.memory import BrainDB
from .adapters.ollama_adapter import OllamaClient

DEFAULT_BSM_PROMPT = (
    'Summarize the observation and return JSON with fields: '
    '"summary": str, "tags": [str], "entities": [{"type": "", "value": ""}], '
    '"relations": [{"source": "", "target": "", "relation": ""}].\n<<<\n{obs}\n>>>'
)
DEFAULT_BSM_SYSTEM = "Respond with a single JSON object only."


class BSM:
    def __init__(
        self,
        model: str | None,
        host: str,
        brain: BrainDB,
        temperature: float = 0.1,
        *,
        api_key_env: str | None = None,
        system_prompt: str | None = None,
        prompt: str | None = None,
        client_options: Optional[Dict[str, object]] = None,
        call_options: Optional[Dict[str, object]] = None,
    ) -> None:
        self.model = model
        self.brain = brain
        self.temperature = temperature
        self.prompt = prompt or DEFAULT_BSM_PROMPT
        self.system_prompt = system_prompt or DEFAULT_BSM_SYSTEM
        self.call_options = dict(call_options or {})

        self.ollama = (
            OllamaClient(host, api_key_env=api_key_env, default_options=client_options)
            if model
            else None
        )

    def ingest(self, obs: str, meta: Dict[str, Any]) -> int:
        if not self.ollama or not self.model:
            return self.brain.add_memory("observation", obs[:500], meta)

        prompt_body = self.prompt.replace("{obs}", obs[:4000])
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
            match = re.search(r"\{.*\}", out, re.DOTALL)
            document = json.loads(match.group(0)) if match else {}
        except Exception:
            document = {}

        summary = document.get("summary") or obs[:500]
        tags = document.get("tags", [])
        memory_meta = {"tags": tags, **meta}
        return self.brain.add_memory("observation", summary, memory_meta)
