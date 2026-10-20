"""Chat orchestration + SSE event production."""
from __future__ import annotations

import asyncio
import contextlib
import logging
import re
import time
import uuid
from typing import Any, AsyncIterator

from app.agent.events import RunContext, sse_frame
from app.db import new_id, now_iso
from app.runtime import AppRuntime

logger = logging.getLogger(__name__)

_SESSION_SANITIZER = re.compile(r"[^a-zA-Z0-9_\-]")


def normalize_session_id(session_id: str | None) -> str:
    if not session_id:
        return f"s_{uuid.uuid4().hex[:12]}"
    cleaned = _SESSION_SANITIZER.sub("", session_id)[:64]
    return cleaned or f"s_{uuid.uuid4().hex[:12]}"


def _compact_trace(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    keep = {
        "node_start", "node_end", "retrieval", "intent", "plan", "guard",
        "tool_call", "tool_result", "verification", "scene_start", "scene_step",
        "scene_step_result", "scene_condition", "scene_fallback", "scene_verify",
        "scene_done", "error", "notice", "run_start",
    }
    return [event for event in events if event.get("type") in keep]


def _status_from_final(final: dict[str, Any]) -> str:
    scene_result = final.get("scene_result")
    if scene_result:
        mapping = {"success": "success", "partial": "partial", "failed": "failed", "skipped": "skipped"}
        return mapping.get(scene_result.get("status"), "success")
    results = final.get("tool_results", [])
    if not results:
        return "success"
    successes = sum(1 for result in results if result.get("ok"))
    if successes == len(results):
        return "success"
    return "partial" if successes else "failed"


def _record_execution(
    runtime: AppRuntime,
    ctx: RunContext,
    *,
    session_id: str,
    kind: str,
    title: str,
    user_input: str,
    final: dict[str, Any] | None,
    response: str,
    status: str,
    duration_ms: float,
    error: str | None = None,
) -> str:
    execution_id = new_id("exec_")
    final = final or {}
    tool_results = final.get("tool_results", [])
    tool_calls = [
        {
            "name": result.get("name"),
            "args": result.get("args"),
            "ok": result.get("ok"),
            "message": result.get("message"),
        }
        for result in tool_results
    ]
    runtime.db.add_execution({
        "id": execution_id,
        "session_id": session_id,
        "kind": kind,
        "title": title[:120],
        "input": user_input[:1000],
        "intent": final.get("intent", {}),
        "tool_calls": tool_calls,
        "trace": _compact_trace(ctx.trace()),
        "result": {
            "response": response,
            "scene_result": final.get("scene_result"),
            "verification": final.get("verification", []),
            "error": error,
        },
        "status": status,
        "duration_ms": int(duration_ms),
        "created_at": now_iso(),
    })
    ctx.events.append({
        "type": "execution_saved",
        "run_id": ctx.run_id,
        "execution_id": execution_id,
        "ts": int(time.time() * 1000),
    })
    return execution_id


class ChatService:
    def __init__(self, runtime: AppRuntime) -> None:
        self.runtime = runtime

    async def stream(
        self, message: str, session_id: str | None = None, *, voice: bool = False,
    ) -> AsyncIterator[str]:
        runtime = self.runtime
        session_id = normalize_session_id(session_id)
        message = message.strip()[:1000]
        history = runtime.db.recent_history(session_id, limit=8)
        runtime.db.add_message(
            session_id, "user", message, {"voice": voice, "source": "voice" if voice else "text"},
            ensure_session=True,
        )
        if not history:
            runtime.db.rename_session(session_id, message[:24] or "新的对话")

        ctx = RunContext(
            run_id=new_id("run_"),
            session_id=session_id,
            kind="chat",
            title=message[:40],
        )
        mode = "llm" if runtime.llm.enabled else "offline"
        await ctx.emit(
            "run_start",
            session_id=session_id,
            kind="chat",
            title=ctx.title,
            mode=mode,
            assistant="小居",
            started_at=now_iso(),
        )
        task = asyncio.create_task(
            self._run(ctx, session_id, message, history)
        )
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

    async def _run(
        self,
        ctx: RunContext,
        session_id: str,
        message: str,
        history: list[dict[str, str]],
    ) -> None:
        runtime = self.runtime
        started = time.perf_counter()
        final: dict[str, Any] | None = None
        try:
            final = await runtime.agent_graph.ainvoke(
                {
                    "session_id": session_id,
                    "user_input": message,
                    "history": history,
                },
                config={
                    "configurable": {
                        "thread_id": session_id,
                        "ctx": ctx,
                    }
                },
            )
            response = str(final.get("response") or "处理完成。")
            status = _status_from_final(final)
            duration = (time.perf_counter() - started) * 1000
            execution_id = _record_execution(
                runtime, ctx,
                session_id=session_id, kind="chat",
                title=message[:60], user_input=message,
                final=final, response=response, status=status,
                duration_ms=duration,
            )
            message_id = runtime.db.add_message(
                session_id, "assistant", response,
                {
                    "execution_id": execution_id,
                    "intent": final.get("intent", {}).get("intent"),
                    "intent_type": final.get("intent", {}).get("intent_type"),
                    "confidence": final.get("intent", {}).get("confidence"),
                    "status": status,
                },
            )
            await ctx.emit(
                "done",
                session_id=session_id,
                execution_id=execution_id,
                message_id=message_id,
                status=status,
                duration_ms=round(duration, 1),
                mode="llm" if runtime.llm.enabled else "offline",
                usage=runtime.llm.last_usage,
            )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.exception("Agent run failed")
            duration = (time.perf_counter() - started) * 1000
            response = (
                "抱歉，我在处理这条指令时遇到了内部异常。"
                "你可以换一种说法，或者直接在设备面板操作。"
            )
            await ctx.emit("error", message=str(exc), recoverable=True)
            for start in range(0, len(response), 8):
                await ctx.emit("token", content=response[start:start + 8])
                await asyncio.sleep(0.006)
            await ctx.emit("response", content=response)
            execution_id = _record_execution(
                runtime, ctx,
                session_id=session_id, kind="chat",
                title=message[:60], user_input=message,
                final=final, response=response, status="failed",
                duration_ms=duration, error=str(exc),
            )
            message_id = runtime.db.add_message(
                session_id, "assistant", response,
                {"execution_id": execution_id, "status": "failed"},
            )
            await ctx.emit(
                "done",
                session_id=session_id,
                execution_id=execution_id,
                message_id=message_id,
                status="failed",
                duration_ms=round(duration, 1),
                mode="llm" if runtime.llm.enabled else "offline",
            )
        finally:
            with contextlib.suppress(Exception):
                await ctx.queue.put({"type": "__end__"})
