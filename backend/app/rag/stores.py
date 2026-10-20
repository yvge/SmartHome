"""Vector store adapters: Milvus for production, in-memory for zero-setup."""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

PAYLOAD_FIELDS = ("text", "kind", "intent", "category", "device_type", "answer", "metadata")


class BaseVectorStore(ABC):
    backend: str

    @abstractmethod
    def initialize(self, entries: list[dict[str, Any]], vectors: np.ndarray) -> None:
        raise NotImplementedError

    @abstractmethod
    def search(
        self, vector: np.ndarray, top_k: int, kind: str | None = None,
    ) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def stats(self) -> dict[str, Any]:
        raise NotImplementedError

    def close(self) -> None:
        return None


class LocalVectorStore(BaseVectorStore):
    backend = "local"

    def __init__(self) -> None:
        self.entries: list[dict[str, Any]] = []
        self.vectors = np.zeros((0, 1), dtype=np.float32)

    def initialize(self, entries: list[dict[str, Any]], vectors: np.ndarray) -> None:
        self.entries = [dict(entry) for entry in entries]
        self.vectors = np.asarray(vectors, dtype=np.float32)

    def search(
        self, vector: np.ndarray, top_k: int, kind: str | None = None,
    ) -> list[dict[str, Any]]:
        if not self.entries or self.vectors.size == 0:
            return []
        indices = list(range(len(self.entries)))
        if kind:
            indices = [i for i in indices if self.entries[i].get("kind") == kind]
        if not indices:
            return []
        matrix = self.vectors[indices]
        query = np.asarray(vector, dtype=np.float32).reshape(-1)
        scores = matrix @ query
        order = np.argsort(-scores)[:top_k]
        hits: list[dict[str, Any]] = []
        for position in order:
            entry = self.entries[indices[int(position)]]
            hits.append({
                "id": entry["id"],
                "score": round(float(scores[int(position)]), 4),
                **{field: entry.get(field) for field in PAYLOAD_FIELDS},
            })
        return hits

    def stats(self) -> dict[str, Any]:
        return {
            "backend": self.backend,
            "collection": "in-memory",
            "count": len(self.entries),
            "dim": int(self.vectors.shape[1]) if self.vectors.size else 0,
            "healthy": True,
        }


class MilvusVectorStore(BaseVectorStore):
    backend = "milvus"

    def __init__(self, uri: str, token: str, collection: str, dim: int) -> None:
        try:
            from pymilvus import DataType, MilvusClient  # type: ignore
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise RuntimeError(
                "pymilvus is not installed. Run `pip install pymilvus` "
                "or set VECTOR_STORE=local."
            ) from exc
        self._DataType = DataType
        self._client = MilvusClient(uri=uri, token=token or "", timeout=3)
        self.collection = collection
        self.dim = dim
        # Fail fast so the service can fall back without blocking startup.
        self._client.list_collections()

    def _create_collection(self) -> None:
        DataType = self._DataType
        if self._client.has_collection(self.collection):
            self._client.drop_collection(self.collection)
        schema = self._client.create_schema(auto_id=False, enable_dynamic_field=False)
        schema.add_field("id", DataType.VARCHAR, is_primary=True, max_length=128)
        schema.add_field("vector", DataType.FLOAT_VECTOR, dim=self.dim)
        schema.add_field("text", DataType.VARCHAR, max_length=2048)
        schema.add_field("kind", DataType.VARCHAR, max_length=32)
        schema.add_field("intent", DataType.VARCHAR, max_length=128)
        schema.add_field("category", DataType.VARCHAR, max_length=64)
        schema.add_field("device_type", DataType.VARCHAR, max_length=64)
        schema.add_field("answer", DataType.VARCHAR, max_length=4096)
        schema.add_field("metadata", DataType.JSON)
        index_params = self._client.prepare_index_params()
        index_params.add_index(
            field_name="vector", index_type="AUTOINDEX", metric_type="COSINE"
        )
        self._client.create_collection(
            collection_name=self.collection,
            schema=schema,
            index_params=index_params,
        )

    def initialize(self, entries: list[dict[str, Any]], vectors: np.ndarray) -> None:
        self._create_collection()
        rows = []
        for entry, vector in zip(entries, vectors):
            rows.append({
                "id": entry["id"],
                "vector": [float(value) for value in vector],
                "text": entry.get("text", "")[:2000],
                "kind": entry.get("kind", "intent")[:30],
                "intent": entry.get("intent", "")[:120],
                "category": entry.get("category", "")[:60],
                "device_type": entry.get("device_type", "")[:60],
                "answer": entry.get("answer", "")[:4000],
                "metadata": entry.get("metadata", {}) or {},
            })
        if rows:
            self._client.upsert(collection_name=self.collection, data=rows)
        logger.info("Milvus collection %s rebuilt with %d entries", self.collection, len(rows))

    def search(
        self, vector: np.ndarray, top_k: int, kind: str | None = None,
    ) -> list[dict[str, Any]]:
        if self._client.has_collection(self.collection) is False:
            return []
        kwargs: dict[str, Any] = {
            "collection_name": self.collection,
            "data": [np.asarray(vector, dtype=np.float32).tolist()],
            "anns_field": "vector",
            "limit": top_k,
            "output_fields": list(PAYLOAD_FIELDS),
            "search_params": {"metric_type": "COSINE"},
        }
        if kind:
            kwargs["filter"] = f'kind == "{kind}"'
        result = self._client.search(**kwargs)
        hits: list[dict[str, Any]] = []
        for group in result:
            for hit in group:
                entity = hit.get("entity", {}) or {}
                hits.append({
                    "id": hit.get("id"),
                    "score": round(float(hit.get("distance", 0.0)), 4),
                    **{field: entity.get(field) for field in PAYLOAD_FIELDS},
                })
        return hits

    def stats(self) -> dict[str, Any]:
        count = 0
        healthy = True
        try:
            rows = self._client.query(
                collection_name=self.collection, output_fields=["count(*)"]
            )
            if rows:
                count = int(rows[0].get("count(*)", 0))
        except Exception:  # pragma: no cover - best-effort telemetry
            healthy = False
        return {
            "backend": self.backend,
            "collection": self.collection,
            "count": count,
            "dim": self.dim,
            "healthy": healthy,
        }

    def close(self) -> None:
        try:
            self._client.close()
        except Exception:  # pragma: no cover
            pass
