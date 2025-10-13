from __future__ import annotations

from typing import Any, Dict

from ..core.event_bus import EventBus, Topic
from ..core.policy_overlay import CompositeDenyPolicy
from ..tools.windows.ocr import ocr_hwnd
from .action_executor import ActionExecutor
from .aum import AUM
from .bsm import BSM


class ChatDockAgent:
    def __init__(
        self,
        bus: EventBus,
        policy: CompositeDenyPolicy,
        executor: ActionExecutor,
        aum: AUM,
        bsm: BSM,
        tesseract_path: str | None,
    ) -> None:
        self.bus = bus
        self.policy = policy
        self.executor = executor
        self.aum = aum
        self.bsm = bsm
        self.tesseract_path = tesseract_path

    async def handle_intent(self, intent: Dict[str, Any]) -> Dict[str, Any]:
        if intent.get("kind") != "chatdock_run":
            payload = {
                "status": "unknown_intent",
                "intent": intent,
                "detail": {"reason": "ChatDock only handles chatdock_run intents."},
            }
            await self.bus.publish(Topic.EFFECT, payload)
            return payload

        hwnd = int(intent.get("args", {}).get("hwnd", 0) or 0)
        text = ""
        try:
            text = ocr_hwnd(hwnd, self.tesseract_path)
        except Exception as exc:
            payload = {
                "status": "error",
                "intent": intent,
                "detail": {"results": [], "error": str(exc)},
            }
            await self.bus.publish(Topic.EFFECT, payload)
            return payload

        actions = self.aum.extract(text) or []
        if not actions:
            actions = [{"kind": "ocr", "args": {"hwnd": hwnd}}]

        payload = await self.executor.run_actions(
            intent,
            actions,
            context={
                "text": text[:4096],
                "source": "chatdock",
            },
        )

        results = payload.get("detail", {}).get("results", [])
        self.bsm.ingest(
            text,
            {
                "source": "chatdock",
                "results": results,
                "hwnd": hwnd,
                "status": payload.get("status"),
            },
        )
        return payload
