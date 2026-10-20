"""RAG orchestration: embedding + vector store lifecycle and search."""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

import numpy as np

from app.config import Settings
from app.db import Database
from app.rag.embedder import BaseEmbedder, HashEmbedder, create_embedder
from app.rag.stores import BaseVectorStore, LocalVectorStore, MilvusVectorStore

logger = logging.getLogger(__name__)


class RAGService:
    def __init__(self, settings: Settings, db: Database) -> None:
        self.settings = settings
        self.db = db
        self.entries: list[dict[str, Any]] = []
        self.embedder: BaseEmbedder = create_embedder(settings)
        self.store: BaseVectorStore | None = None
        self.requested_backend = settings.vector_store
        self.error: str | None = None
        self.embedding_error: str | None = None
        self._last_latency_ms = 0.0
        self._lock = asyncio.Lock()

    # ----------------------------------------------------------- lifecycle
    async def initialize(self, entries: list[dict[str, Any]] | None = None) -> None:
        async with self._lock:
            self.entries = entries if entries is not None else self.db.load_kb()
            await self._prepare_embedder()
            vectors = await self.embedder.embed([entry["text"] for entry in self.entries])
            store = await self._create_store()
            await asyncio.to_thread(store.initialize, self.entries, vectors)
            self.store = store
            logger.info(
                "RAG ready: backend=%s embedder=%s entries=%d dim=%d",
                store.backend, self.embedder.name, len(self.entries), self.embedder.dim,
            )

    async def _prepare_embedder(self) -> None:
        try:
            # Probe once so invalid keys or network issues fail over early.
            await self.embedder.embed(["连接测试"])
        except Exception as exc:
            self.embedding_error = f"{type(exc).__name__}: {exc}"
            logger.warning("Embedding backend unavailable, falling back to local: %s", exc)
            await self.embedder.close()
            self.embedder = HashEmbedder(dim=self.settings.embedding_dim)

    async def _create_store(self) -> BaseVectorStore:
        requested = self.settings.vector_store
        if requested in {"auto", "milvus"}:
            try:
                store = await asyncio.to_thread(
                    MilvusVectorStore,
                    self.settings.milvus_uri,
                    self.settings.milvus_token,
                    self.settings.milvus_collection,
                    self.embedder.dim,
                )
                return store
            except Exception as exc:
                self.error = f"Milvus 不可用，已降级到本地向量库：{exc}"
                logger.warning(self.error)
                if requested == "milvus":
                    # Keep the app runnable even when the operator asked for Milvus
                    # but the container isn't up yet.
                    logger.warning("VECTOR_STORE=milvus but Milvus is unreachable; using local store")
        return LocalVectorStore()

    async def close(self) -> None:
        if self.store:
            await asyncio.to_thread(self.store.close)
        await self.embedder.close()

    # -------------------------------------------------------------- search
    async def search(
        self, query: str, top_k: int = 5, kind: str | None = None,
    ) -> dict[str, Any]:
        if not self.store:
            return {"hits": [], "latency_ms": 0.0}
        started = time.perf_counter()
        try:
            vector = (await self.embedder.embed([query]))[0]
            hits = await asyncio.to_thread(self.store.search, vector, top_k, kind)
        except Exception as exc:  # keep chat alive if the vector DB hiccups
            logger.exception("Vector search failed: %s", exc)
            self.error = f"向量检索失败：{exc}"
            hits = []
        latency = round((time.perf_counter() - started) * 1000, 2)
        self._last_latency_ms = latency
        return {"hits": hits, "latency_ms": latency}

    async def search_intents(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        result = await self.search(query, top_k=top_k, kind="intent")
        return result["hits"]

    async def search_knowledge(self, query: str, top_k: int = 3) -> list[dict[str, Any]]:
        result = await self.search(query, top_k=top_k, kind="knowledge")
        return result["hits"]

    # ------------------------------------------------------------- rebuild
    async def reindex(self, entries: list[dict[str, Any]] | None = None) -> None:
        async with self._lock:
            self.entries = entries if entries is not None else self.db.load_kb()
            vectors = await self.embedder.embed([entry["text"] for entry in self.entries])
            if not self.store:
                self.store = await self._create_store()
            await asyncio.to_thread(self.store.initialize, self.entries, vectors)

    async def add_entry(self, entry: dict[str, Any]) -> None:
        self.db.save_kb_entry(entry)
        await self.reindex()

    # --------------------------------------------------------------- stats
    async def stats(self) -> dict[str, Any]:
        store_stats: dict[str, Any] = {
            "backend": self.store.backend if self.store else "none",
            "collection": "unavailable",
            "count": len(self.entries),
            "dim": self.embedder.dim,
            "healthy": False,
        }
        if self.store:
            try:
                store_stats = await asyncio.to_thread(self.store.stats)
            except Exception as exc:
                store_stats["healthy"] = False
                store_stats["error"] = str(exc)
        intents = sum(1 for entry in self.entries if entry.get("kind") == "intent")
        knowledge = sum(1 for entry in self.entries if entry.get("kind") == "knowledge")
        return {
            **store_stats,
            "count": len(self.entries),
            "intents": intents,
            "knowledge": knowledge,
            "embedding": {
                "provider": "openai" if not self.embedder.is_local else "local",
                "model": self.embedder.name,
                "dim": self.embedder.dim,
                "fallback": self.embedding_error,
            },
            "requested_backend": self.requested_backend,
            "degraded": self.store.backend != "milvus" if self.requested_backend == "milvus" else False,
            "latency_ms": self._last_latency_ms,
            "error": self.error,
        }

    def entry_payloads(self) -> list[dict[str, Any]]:
        return [
            {
                "id": entry["id"],
                "kind": entry.get("kind"),
                "text": entry.get("text"),
                "intent": entry.get("intent"),
                "category": entry.get("category"),
                "device_type": entry.get("device_type"),
                "answer": entry.get("answer"),
                "metadata": entry.get("metadata", {}),
            }
            for entry in self.entries
        ]
