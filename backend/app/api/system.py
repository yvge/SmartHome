"""System status, live state stream, traces and diagnostics."""
from __future__ import annotations

import asyncio
import contextlib
import json
import time
from typing import AsyncIterator

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.agent.events import sse_frame
from app.agent.tools import tool_catalog
from app.runtime import AppRuntime

router = APIRouter(prefix="/system", tags=["system"])

SSE_HEADERS = {
    "Cache-Control": "no-cache, no-transform",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}


def _runtime(request: Request) -> AppRuntime:
    return request.app.state.runtime


@router.get("/status", summary="系统状态")
async def status(request: Request) -> dict:
    runtime = _runtime(request)
    return await runtime.status()


@router.get("/tools", summary="Function Calling 工具 Schema")
async def tools(request: Request) -> dict:
    runtime = _runtime(request)
    return {
        "tools": tool_catalog(),
        "device_count": len(runtime.devices.snapshot()),
        "mode": "llm" if runtime.llm.enabled else "offline-rules",
    }


@router.get("/graph", summary="Agent 图拓扑")
async def graph(request: Request) -> dict:
    runtime = _runtime(request)
    return runtime.graph_topology()


@router.get("/events", summary="全屋状态事件流（SSE）")
async def events(request: Request) -> StreamingResponse:
    runtime = _runtime(request)
    queue = runtime.bus.subscribe()

    async def generator() -> AsyncIterator[str]:
        try:
            initial = {
                "type": "snapshot",
                "data": runtime.snapshot(),
                "ts": int(time.time() * 1000),
            }
            yield f"event: snapshot\ndata: {json.dumps(initial, ensure_ascii=False, default=str)}\n\n"
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=20)
                except asyncio.TimeoutError:
                    yield ": ping\n\n"
                    continue
                yield sse_frame(event)
        finally:
            runtime.bus.unsubscribe(queue)

    return StreamingResponse(generator(), media_type="text/event-stream", headers=SSE_HEADERS)


@router.get("/executions", summary="Agent 运行记录")
async def executions(
    request: Request, limit: int = 30, kind: str | None = None, status: str | None = None,
) -> dict:
    runtime = _runtime(request)
    rows = runtime.db.list_executions(limit=min(max(limit, 1), 100))
    if kind:
        rows = [row for row in rows if row.get("kind") == kind]
    if status:
        rows = [row for row in rows if row.get("status") == status]
    return {"executions": rows}


@router.get("/executions/{execution_id}", summary="单次运行详情")
async def execution_detail(execution_id: str, request: Request) -> dict:
    runtime = _runtime(request)
    row = runtime.db.get_execution(execution_id)
    if not row:
        raise HTTPException(404, "运行记录不存在")
    return {"execution": row}


@router.post("/reset-devices", summary="重置所有设备到演示初始状态")
async def reset_devices(request: Request) -> dict:
    runtime = _runtime(request)
    devices = runtime.devices.reset()
    runtime.simulator.tick()
    await runtime.bus.publish("state", runtime.snapshot())
    return {"ok": True, "devices": devices}


@router.get("/environment", summary="环境与能耗快照")
async def environment(request: Request) -> dict:
    runtime = _runtime(request)
    snapshot = runtime.snapshot()
    return {
        "environment": snapshot["environment"],
        "rooms": snapshot["rooms"],
        "period": snapshot["period"],
    }
