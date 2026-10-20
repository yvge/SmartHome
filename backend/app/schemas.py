"""Pydantic request/response models for the HTTP API."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1000)
    session_id: str | None = Field(default=None, max_length=64)
    voice: bool = False

    @field_validator("message")
    @classmethod
    def message_not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("message 不能为空")
        return value


class DevicePatch(BaseModel):
    properties: dict[str, Any] = Field(default_factory=dict)

    @field_validator("properties")
    @classmethod
    def not_empty(cls, value: dict[str, Any]) -> dict[str, Any]:
        if not value:
            raise ValueError("properties 不能为空")
        return value


class ConnectivityPatch(BaseModel):
    online: bool


class SceneStepPayload(BaseModel):
    device_id: str
    params: dict[str, Any] = Field(default_factory=dict)
    label: str | None = Field(default=None, max_length=80)
    delay_ms: int = Field(default=200, ge=0, le=2000)
    critical: bool = False
    when: dict[str, Any] | None = None


class ScenePayload(BaseModel):
    name: str = Field(min_length=1, max_length=30)
    icon: str = Field(default="sparkles", max_length=40)
    description: str = Field(default="", max_length=160)
    condition: dict[str, Any] | None = None
    steps: list[SceneStepPayload] = Field(min_length=1, max_length=40)
    fallback: list[SceneStepPayload] = Field(default_factory=list, max_length=20)

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        return value.strip()


class RAGSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=300)
    top_k: int = Field(default=5, ge=1, le=20)
    kind: Literal["intent", "knowledge"] | None = None


class RAGEntryPayload(BaseModel):
    kind: Literal["intent", "knowledge"] = "knowledge"
    text: str = Field(min_length=1, max_length=300)
    intent: str = Field(default="", max_length=80)
    category: str = Field(default="custom", max_length=60)
    device_type: str = Field(default="", max_length=40)
    answer: str = Field(default="", max_length=2000)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("text")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip()
