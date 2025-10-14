from __future__ import annotations

import math
from typing import Any, Dict, Iterable, List, Optional, Tuple

from PIL import ImageGrab

from ..core.triple_bus import TripleBusSystem, MainTopic
from ..core.policy_overlay import CompositeDenyPolicy
from ..tools.windows.automation import click as do_click
from ..tools.windows.automation import hotkey as do_hotkey
from ..tools.windows.automation import type_text as do_type
from ..tools.windows.ocr import ocr_hwnd


class ActionExecutor:
    """Executes low-level automation actions with policy guardrails."""

    def __init__(self, buses: TripleBusSystem, policy: CompositeDenyPolicy, tesseract_path: str | None) -> None:
        self.buses = buses
        self.policy = policy
        self.tesseract_path = tesseract_path

    def update(self, policy: CompositeDenyPolicy, tesseract_path: str | None) -> None:
        self.policy = policy
        self.tesseract_path = tesseract_path

    async def handle_intent(self, intent: Dict[str, Any]) -> Dict[str, Any]:
        """Handle a single direct intent (type_text, hotkey, click, ocr)."""
        action = {"kind": intent.get("kind"), "args": intent.get("args", {})}
        result = await self._execute_action(action, intent)
        detail = self._result_to_detail(result)

        payload = {"status": result["status"], "detail": detail, "intent": intent}
        await self.buses.main.publish(MainTopic.EFFECT, payload)
        return payload

    async def run_actions(
        self,
        origin_intent: Dict[str, Any],
        actions: Iterable[Dict[str, Any]],
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Execute a sequence of actions and publish a consolidated effect."""
        results: List[Dict[str, Any]] = []
        overall = "ok"

        for action in actions:
            result = await self._execute_action(action, origin_intent)
            results.append(result)
            status = result["status"]
            if status in {"error", "denied"}:
                overall = status
            elif status == "unknown" and overall == "ok":
                overall = "unknown_intent"

        if not results:
            overall = "unknown_intent"

        detail: Dict[str, Any] = {"results": results}
        if context:
            detail.update(context)

        payload = {"status": overall, "detail": detail, "intent": origin_intent}
        await self.buses.main.publish(MainTopic.EFFECT, payload)
        return payload

    async def _execute_action(self, action: Dict[str, Any], origin_intent: Dict[str, Any]) -> Dict[str, Any]:
        kind_raw = (action.get("kind") or "").strip()
        kind = kind_raw.lower()
        args = action.get("args") or {}

        # Normalise action kinds
        if kind == "type":
            kind = "type_text"
        elif kind == "key":
            kind = "hotkey"

        result: Dict[str, Any] = {"kind": kind_raw or kind, "status": "ok"}

        try:
            if kind == "type_text":
                text = str(args.get("text", "") or "")
                ok, reason = self.policy.allow_input(text)
                if not ok:
                    result["status"] = "denied"
                    result["reason"] = reason
                else:
                    do_type(text)
            elif kind == "hotkey":
                chord = str(args.get("chord") or args.get("keys") or "")
                if not chord:
                    result["status"] = "unknown"
                else:
                    ok, reason = self.policy.allow_hotkey(chord)
                    if not ok:
                        result["status"] = "denied"
                        result["reason"] = reason
                    else:
                        keys = _normalise_hotkey(chord)
                        do_hotkey(*keys)
                        result["effective_chord"] = "+".join(keys)
            elif kind == "click":
                x = _coerce_int(args.get("x"))
                y = _coerce_int(args.get("y"))
                if x is None or y is None:
                    result["status"] = "unknown"
                else:
                    do_click(x, y)
                    result["point"] = {"x": x, "y": y}
            elif kind == "ocr":
                text = self._perform_ocr(args, origin_intent)
                result["text"] = text[:4096]
            else:
                result["status"] = "unknown"
        except Exception as exc:
            result["status"] = "error"
            result["error"] = str(exc)

        return result

    def _perform_ocr(self, args: Dict[str, Any], origin_intent: Dict[str, Any]) -> str:
        bounds = _extract_bounds(args) or _extract_bounds(origin_intent.get("meta", {}))
        hwnd = _extract_hwnd(args) or _extract_hwnd(origin_intent.get("meta", {}))
        if bounds:
            left, top, right, bottom = bounds
            img = ImageGrab.grab(bbox=(left, top, right, bottom))
            from pytesseract import image_to_string, pytesseract as pyt

            if self.tesseract_path:
                pyt.tesseract_cmd = self.tesseract_path
            return image_to_string(img)
        if hwnd:
            return ocr_hwnd(hwnd, self.tesseract_path)
        raise RuntimeError("No bounds or window handle available for OCR action.")

    @staticmethod
    def _result_to_detail(result: Dict[str, Any]) -> Dict[str, Any]:
        detail = {k: v for k, v in result.items() if k not in {"kind", "status"}}
        detail["kind"] = result.get("kind")
        return detail


def _normalise_hotkey(chord: str) -> Tuple[str, ...]:
    parts = [segment.strip().lower() for segment in chord.split("+") if segment.strip()]
    return tuple(parts)


def _coerce_int(value: Any) -> Optional[int]:
    try:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            if isinstance(value, float) and math.isnan(value):
                return None
            return int(value)
        text = str(value).strip()
        if not text:
            return None
        return int(float(text))
    except (ValueError, TypeError):
        return None


def _extract_bounds(source: Dict[str, Any]) -> Optional[Tuple[int, int, int, int]]:
    raw = source.get("bounds") or source.get("target_bounds")
    if isinstance(raw, (list, tuple)) and len(raw) == 4:
        try:
            return tuple(int(float(v)) for v in raw)
        except (ValueError, TypeError):
            return None
    return None


def _extract_hwnd(source: Dict[str, Any]) -> Optional[int]:
    raw = source.get("hwnd") or source.get("target_hwnd") or source.get("docked_hwnd")
    if raw is None:
        return None
    if isinstance(raw, int):
        return raw
    text = str(raw)
    digits = "".join(ch for ch in text if ch.isdigit())
    if digits:
        try:
            return int(digits)
        except ValueError:
            return None
    return None
