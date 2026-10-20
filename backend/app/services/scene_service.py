"""Direct scene execution over SSE (scene library page)."""
from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from typing import Any, AsyncIterator

from app.agent.events import RunContext, sse_frame
from app.db import new_id, now_iso
from app.runtime import AppRuntime
from app.services.chat_service import _record_execution, normalize_session_id

logger = logging.getLogger(__name__)


class SceneService:
    def __init__(self, runtime: AppRuntime) -> None:
        self.runtime = runtime

    async def stream(
        self, scene: dict[str, Any], session_id: str | None = None,
    ) -> AsyncIterator[str]:
        runtime = self.runtime
        ctx = RunContext(
            run_id=new_id("run_"),
            session_id=normalize_session_id(session_id or f"scene_{scene['id']}"),
            kind="scene",
            title=scene["name"],
        )
        await ctx.emit(
            "run_start",
            session_id=ctx.session_id,
            kind="scene",
            title=scene["name"],
            mode="llm" if runtime.llm.enabled else "offline",
            started_at=now_iso(),
            scene_id=scene["id"],
        )
        task = asyncio.create_task(self._run(ctx, scene))
        try:
            while True:
                try:
                    event = await asyncio.wait_for(ctx.queue.get(), timeout=15)
                except asyncio.TimeoutError:
                    yield ": ping\n\n"
                    continue
                if event.get("type") == "__end__":
                    break
                yield sse_frame(event)
        finally:
            if not task.done():
                task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await task

    async def _run(self, ctx: RunContext, scene: dict[str, Any]) -> None:
        runtime = self.runtime
        started = time.perf_counter()
        result: dict[str, Any] | None = None
        try:
            final = await runtime.scene_graph.ainvoke(
                {
                    "scene_id": scene["id"],
                    "index": 0,
                    "results": [],
                    "failures": [],
                },
                config={"configurable": {"ctx": ctx}},
            )
            result = final.get("result") or {
                "scene_id": scene["id"],
                "scene_name": scene["name"],
                "status": "failed",
                "message": "场景执行异常，未返回结果。",
                "results": [],
                "failures": [],
                "fallback_used": False,
            }
            duration = (time.perf_counter() - started) * 1000
            execution_id = _record_execution(
                runtime, ctx,
                session_id=ctx.session_id, kind="scene",
                title=scene["name"], user_input=scene["id"],
                final={
                    "scene_result": result,
                    "intent": {"intent_type": "scene", "intent": scene["id"], "confidence": 1.0},
                },
                response=result.get("message", ""),
                status=result.get("status", "success"),
                duration_ms=duration,
            )
            await ctx.emit(
                "done",
                session_id=ctx.session_id,
                scene_id=scene["id"],
                execution_id=execution_id,
                status=result.get("status"),
                duration_ms=round(duration, 1),
                result=result,
            )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.exception("Scene execution failed")
            duration = (time.perf_counter() - started) * 1000
            await ctx.emit("error", message=str(exc), recoverable=True)
            await ctx.emit(
                "done",
                session_id=ctx.session_id,
                scene_id=scene["id"],
                execution_id=None,
                status="failed",
                duration_ms=round(duration, 1),
            )
        finally:
            with contextlib.suppress(Exception):
                await ctx.queue.put({"type": "__end__"})
