from __future__ import annotations

import os
from typing import Dict, List, Optional

import requests


class OllamaClient:
    """Thin wrapper around the Ollama HTTP API with optional cloud headers."""

    def __init__(
        self,
        host: str = "http://127.0.0.1:11434",
        api_key_env: str | None = None,
        default_options: Optional[Dict[str, object]] = None,
        request_timeout: float = 120.0,
        verify_tls: bool = True,
    ) -> None:
        self.host = host.rstrip("/")
        self.default_options = dict(default_options or {})
        self.timeout = request_timeout
        self.verify_tls = verify_tls

        api_key = os.environ.get(api_key_env) if api_key_env else None
        headers = {"Accept": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        self.headers = headers

        self._session = requests.Session()

    def _merge_options(
        self,
        temperature: float | None,
        options: Dict[str, object] | None,
    ) -> Dict[str, object]:
        merged: Dict[str, object] = dict(self.default_options)
        if options:
            merged.update({k: v for k, v in options.items() if v is not None})
        if temperature is not None:
            merged["temperature"] = temperature
        return merged

    def chat(
        self,
        model: str,
        messages: List[Dict[str, str]],
        temperature: float | None = None,
        options: Dict[str, object] | None = None,
    ) -> str:
        payload = {
            "model": model,
            "messages": messages,
            "options": self._merge_options(temperature, options),
        }
        response = self._session.post(
            f"{self.host}/api/chat",
            json=payload,
            headers=self.headers,
            timeout=self.timeout,
            verify=self.verify_tls,
        )
        response.raise_for_status()
        data = response.json()
        if isinstance(data, dict):
            message = data.get("message") or {}
            return message.get("content", "")
        if isinstance(data, list):
            return "".join(chunk.get("message", {}).get("content", "") for chunk in data)
        return str(data)

    def embed(
        self,
        model: str,
        text: str,
        options: Dict[str, object] | None = None,
    ) -> List[float]:
        payload = {
            "model": model,
            "prompt": text,
            "options": self._merge_options(None, options),
        }
        response = self._session.post(
            f"{self.host}/api/embeddings",
            json=payload,
            headers=self.headers,
            timeout=self.timeout,
            verify=self.verify_tls,
        )
        response.raise_for_status()
        return response.json().get("embedding", [])
