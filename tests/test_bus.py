
import asyncio

from dexter_autonomy.core.event_bus import EventBus, Topic


async def _run() -> int:
    bus = EventBus()
    got: dict[str, int] = {}

    async def handler(payload: dict) -> None:
        got["ok"] = payload["x"]

    bus.subscribe(Topic.EFFECT, handler)
    await bus.start()
    try:
        await bus.publish(Topic.EFFECT, {"x": 42})
        for _ in range(50):
            if "ok" in got:
                break
            await asyncio.sleep(0.01)
        else:
            raise AssertionError("handler did not receive message")
    finally:
        await bus.stop()
    return got["ok"]


def test_bus():
    assert asyncio.run(_run()) == 42
