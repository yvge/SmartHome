"""Application configuration.

All runtime knobs are environment driven so the same image can run in
"offline demo" mode (no external services) or with a real LLM / Milvus.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ------------------------------------------------------------------ app
    app_name: str = "智慧居 · SmartHome AI Agent"
    app_version: str = "1.0.0"
    api_prefix: str = "/api/v1"
    debug: bool = False
    log_level: str = "INFO"
    data_dir: Path = Field(default=BASE_DIR / "data")

    # --------------------------------------------------------------- llm
    # Any OpenAI-compatible endpoint works: DeepSeek, Qwen/DashScope,
    # Moonshot, SiliconFlow, vLLM, Ollama ...
    llm_provider: Literal["openai", "offline"] = "openai"
    llm_api_key: str = ""
    llm_base_url: str = "https://api.deepseek.com/v1"
    llm_model: str = "deepseek-chat"
    llm_temperature: float = 0.2
    llm_timeout: float = 60.0
    llm_max_tokens: int = 800

    # ---------------------------------------------------------- embedding
    embedding_provider: Literal["local", "openai"] = "local"
    embedding_api_key: str = ""
    embedding_base_url: str = ""
    embedding_model: str = "text-embedding-v3"
    embedding_dim: int = 512
    embedding_batch_size: int = 16

    # ------------------------------------------------------------ vector db
    vector_store: Literal["auto", "milvus", "local"] = "auto"
    milvus_uri: str = "http://localhost:19530"
    milvus_token: str = ""
    milvus_collection: str = "smart_home_kb"

    # ------------------------------------------------------------ runtime
    simulator_interval: float = 4.0
    cors_origins: str = "*"
    seed_version: str = "2024.12-smarthome-1"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def llm_enabled(self) -> bool:
        return self.llm_provider != "offline" and bool(self.llm_api_key.strip())

    @computed_field  # type: ignore[prop-decorator]
    @property
    def resolved_data_dir(self) -> str:
        return str(self.data_dir)

    @property
    def db_path(self) -> Path:
        return self.data_dir / "smart_home.db"

    @property
    def vector_cache_path(self) -> Path:
        return self.data_dir / "vector_cache.json"

    @property
    def cors_origin_list(self) -> list[str]:
        if self.cors_origins.strip() == "*":
            return ["*"]
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    def ensure_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_dirs()
    return settings
