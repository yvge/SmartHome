"""RAG knowledge base endpoints."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from app.db import new_id, now_iso
from app.runtime import AppRuntime
from app.schemas import RAGEntryPayload, RAGSearchRequest

router = APIRouter(prefix="/rag", tags=["rag"])


def _runtime(request: Request) -> AppRuntime:
    return request.app.state.runtime


@router.get("/stats", summary="向量库与 Embedding 状态")
async def rag_stats(request: Request) -> dict:
    runtime = _runtime(request)
    return await runtime.rag.stats()


@router.post("/search", summary="检索意图示例 / 知识片段")
async def rag_search(payload: RAGSearchRequest, request: Request) -> dict:
    runtime = _runtime(request)
    result = await runtime.rag.search(payload.query, top_k=payload.top_k, kind=payload.kind)
    return {
        "query": payload.query,
        "kind": payload.kind,
        "hits": result["hits"],
        "latency_ms": result["latency_ms"],
        "embedding": runtime.rag.embedder.name,
        "backend": runtime.rag.store.backend if runtime.rag.store else "none",
    }


@router.get("/entries", summary="知识库条目")
async def list_entries(
    request: Request, kind: str | None = None, q: str | None = None, limit: int = 200,
) -> dict:
    runtime = _runtime(request)
    entries = runtime.db.load_kb()
    if kind:
        entries = [entry for entry in entries if entry.get("kind") == kind]
    if q:
        needle = q.strip().lower()
        entries = [
            entry for entry in entries
            if needle in entry.get("text", "").lower()
            or needle in entry.get("intent", "").lower()
            or needle in (entry.get("answer") or "").lower()
        ]
    total = len(entries)
    return {"entries": entries[:max(1, min(limit, 500))], "total": total}


@router.post("/entries", summary="新增知识库条目")
async def add_entry(payload: RAGEntryPayload, request: Request) -> dict:
    runtime = _runtime(request)
    if payload.kind == "knowledge" and not payload.answer.strip():
        raise HTTPException(422, "知识类条目必须填写 answer")
    if payload.kind == "intent" and not payload.intent.strip():
        raise HTTPException(422, "意图示例必须填写 intent")
    entry_id = new_id("kb_custom_")
    metadata = {
        **payload.metadata,
        "source": "custom",
        "intent_type": "knowledge" if payload.kind == "knowledge" else "control",
    }
    entry = {
        "id": entry_id,
        "kind": payload.kind,
        "text": payload.text,
        "intent": payload.intent,
        "category": payload.category or "custom",
        "device_type": payload.device_type,
        "answer": payload.answer,
        "metadata": metadata,
        "created_at": now_iso(),
    }
    await runtime.rag.add_entry(entry)
    return {"entry": entry, "stats": await runtime.rag.stats()}
