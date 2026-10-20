"""Chat + conversation history endpoints."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.runtime import AppRuntime
from app.schemas import ChatRequest
from app.services.chat_service import ChatService

router = APIRouter(prefix="/chat", tags=["chat"])

SSE_HEADERS = {
    "Cache-Control": "no-cache, no-transform",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}


def _runtime(request: Request) -> AppRuntime:
    return request.app.state.runtime


@router.post("/stream", summary="对话（SSE 流式）")
async def chat_stream(payload: ChatRequest, request: Request) -> StreamingResponse:
    runtime = _runtime(request)
    service = ChatService(runtime)
    return StreamingResponse(
        service.stream(payload.message, payload.session_id, voice=payload.voice),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )


@router.get("/sessions", summary="对话会话列表")
async def list_sessions(request: Request, limit: int = 20) -> dict:
    runtime = _runtime(request)
    return {"sessions": runtime.db.list_sessions(limit=min(max(limit, 1), 100))}


@router.get("/sessions/{session_id}/messages", summary="会话消息")
async def list_messages(session_id: str, request: Request, limit: int = 100) -> dict:
    runtime = _runtime(request)
    session_id = session_id[:64]
    messages = runtime.db.list_messages(session_id, limit=min(max(limit, 1), 200))
    return {"session_id": session_id, "messages": messages}


@router.delete("/sessions/{session_id}", summary="删除会话")
async def delete_session(session_id: str, request: Request) -> dict:
    runtime = _runtime(request)
    runtime.db.delete_session(session_id[:64])
    return {"ok": True}
