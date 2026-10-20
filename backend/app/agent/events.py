"""Run-scoped event streaming.

Every graph node emits structured events into an asyncio queue that the SSE
endpoint drains. This gives the UI a live LangGraph trace (nodes, tools,
tokens, scene steps) without coupling the graph to FastAPI.
"""
from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field
from typing import Any

NODE_LABELS = {
    "understand": "意图理解",
    "plan": "工具规划",
    "guard": "安全检查",
    "execute": "设备执行",
    "scene": "场景编排",
    "verify": "状态校验",
    "respond": "生成回复",
    "fallback": "异常兜底",
    "scene_load": "加载场景",
    "scene_conditions": "条件判断",
    "scene_plan": "动作编排",
    "scene_execute": "设备联动",
    "scene_fallback": "异常兜底",
    "scene_verify": "场景校验",
}


@dataclass
class RunContext:
    run_id: str
    session_id: str
    kind: str = "chat"
    title: str = ""
    events: list[dict[str, Any]] = field(default_factory=list)
    queue: asyncio.Queue[dict[str, Any]] = field(
        default_factory=lambda: asyncio.Queue(maxsize=1000)
    )
    _seq: int = 0
    started_at: float = field(default_factory=time.time)

    async def emit(self, event_type: str, **data: Any) -> None:
        self._seq += 1
        payload = {
            "type": event_type,
            "run_id": self.run_id,
            "seq": self._seq,
            "ts": int(time.time() * 1000),
            **data,
        }
        if len(self.events) < 800:
            self.events.append(payload)
        try:
            self.queue.put_nowait(payload)
        except asyncio.QueueFull:  # pragma: no cover
            try:
                self.queue.get_nowait()
                self.queue.put_nowait(payload)
            except asyncio.QueueEmpty:
                pass

    async def node_start(self, node: str, **extra: Any) -> None:
        await self.emit("node_start", node=node, label=NODE_LABELS.get(node, node), **extra)

    async def node_end(self, node: str, duration_ms: float, summary: str = "", **extra: Any) -> None:
        await self.emit(
            "node_end",
            node=node,
            label=NODE_LABELS.get(node, node),
            duration_ms=round(duration_ms, 1),
            summary=summary,
            **extra,
        )

    @property
    def elapsed_ms(self) -> float:
        return round((time.time() - self.started_at) * 1000, 1)

    def trace(self) -> list[dict[str, Any]]:
        return list(self.events)


def sse_frame(payload: dict[str, Any]) -> str:
    event_type = str(payload.get("type", "message"))
    return (
        f"event: {event_type}\n"
        f"data: {json.dumps(payload, ensure_ascii=False, default=str)}\n\n"
    )
