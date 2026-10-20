"""Embedding backends.

``local`` is a zero-dependency hashed character n-gram embedder. It is not a
semantic model, but with synonym expansion it retrieves intent exemplars well
and keeps the whole demo runnable with no API key. ``openai`` talks to any
OpenAI-compatible embeddings endpoint for production-quality vectors.
"""
from __future__ import annotations

import hashlib
import re
import unicodedata
from abc import ABC, abstractmethod

import numpy as np

SYNONYM_EXPANSION: dict[str, str] = {
    "开": "打开 开启 启动",
    "关": "关闭 关掉 停止",
    "灯": "灯光 照明",
    "空调": "冷气 暖气 空调机",
    "窗帘": "帘子 布帘",
    "温度": "气温 室温",
    "湿度": "潮湿度",
    "回家": "到家 回来了 归家",
    "离家": "出门 外出 上班",
    "观影": "电影 看电影 影院",
    "睡觉": "睡眠 晚安 休息",
    "起床": "早安 早上好 清晨",
    "节能": "省电 低碳",
    "净化器": "空气净化器 净化机",
    "加湿器": "增湿器",
    "音箱": "音响 扬声器",
    "扫地": "扫地机 机器人 清扫",
}

_PUNCT = re.compile(r"[\s,，。！？、；：,.!?;:~～\"'“”‘’（）()\[\]【】<>《》\-_/\\|]+")
_CJK_RUN = re.compile(r"[一-鿿]+")
_ASCII_WORD = re.compile(r"[a-z0-9]+")


def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFKC", text or "").lower()
    text = _PUNCT.sub(" ", text)
    return re.sub(r"\s+", " ", text).strip()


def expand_text(text: str) -> str:
    normalized = normalize_text(text)
    extra = [expansion for key, expansion in SYNONYM_EXPANSION.items() if key in normalized]
    return " ".join([normalized, *extra]).strip()


def tokenize(text: str) -> list[tuple[str, float]]:
    """Return weighted tokens: CJK uni/bi/trigrams + ASCII words."""
    normalized = expand_text(text)
    tokens: list[tuple[str, float]] = []
    for run in _CJK_RUN.findall(normalized):
        for char in run:
            tokens.append((char, 0.25))
        for size, weight in ((2, 1.0), (3, 0.55)):
            if len(run) >= size:
                for index in range(len(run) - size + 1):
                    tokens.append((run[index:index + size], weight))
    for word in _ASCII_WORD.findall(normalized):
        tokens.append((word, 0.9))
    return tokens


class BaseEmbedder(ABC):
    name: str
    dim: int
    is_local: bool = False

    @abstractmethod
    async def embed(self, texts: list[str]) -> np.ndarray:
        raise NotImplementedError

    async def close(self) -> None:
        return None


class HashEmbedder(BaseEmbedder):
    """Signed feature hashing with L2 normalisation."""

    name = "local-hash-ngram"
    is_local = True

    def __init__(self, dim: int = 512) -> None:
        self.dim = dim

    @staticmethod
    def _hash(token: str) -> int:
        digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
        return int.from_bytes(digest, "big")

    def _embed_one(self, text: str) -> np.ndarray:
        vector = np.zeros(self.dim, dtype=np.float32)
        counts: dict[str, int] = {}
        weights: dict[str, float] = {}
        for token, weight in tokenize(text):
            counts[token] = counts.get(token, 0) + 1
            weights[token] = weight
        for token, count in counts.items():
            value = (1.0 + np.log1p(count)) * weights[token]
            hashed = self._hash(token)
            index = hashed % self.dim
            sign = 1.0 if (hashed >> 63) & 1 else -1.0
            vector[index] += sign * value
        norm = float(np.linalg.norm(vector))
        if norm > 0:
            vector /= norm
        return vector

    async def embed(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, self.dim), dtype=np.float32)
        return np.stack([self._embed_one(text) for text in texts]).astype(np.float32)


class OpenAIEmbedder(BaseEmbedder):
    name = "openai-compatible"

    def __init__(
        self, api_key: str, base_url: str, model: str, dim: int,
        batch_size: int = 16,
    ) -> None:
        from openai import AsyncOpenAI

        if not api_key:
            raise ValueError("EMBEDDING_API_KEY is required for the openai embedder")
        self._client = AsyncOpenAI(
            api_key=api_key, base_url=base_url or None, timeout=30.0, max_retries=1
        )
        self.model = model
        self.dim = dim
        self.batch_size = max(1, batch_size)

    async def embed(self, texts: list[str]) -> np.ndarray:
        vectors: list[list[float]] = []
        for start in range(0, len(texts), self.batch_size):
            batch = texts[start:start + self.batch_size]
            response = await self._client.embeddings.create(
                model=self.model, input=batch, encoding_format="float"
            )
            ordered = sorted(response.data, key=lambda item: item.index)
            vectors.extend([item.embedding for item in ordered])
        array = np.asarray(vectors, dtype=np.float32)
        norms = np.linalg.norm(array, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return array / norms

    async def close(self) -> None:
        await self._client.close()


def create_embedder(settings) -> BaseEmbedder:
    if settings.embedding_provider == "openai" and settings.embedding_api_key:
        return OpenAIEmbedder(
            api_key=settings.embedding_api_key,
            base_url=settings.embedding_base_url or settings.llm_base_url,
            model=settings.embedding_model,
            dim=settings.embedding_dim,
            batch_size=settings.embedding_batch_size,
        )
    return HashEmbedder(dim=settings.embedding_dim)
