"""Shared pytest fixtures.

Every test gets a throwaway data directory and a freshly started AppRuntime so
the demo database under ``backend/data`` is never touched. The settings force
fully offline operation: no LLM calls, the local hash embedder and the
in-memory vector store, so the suite needs neither an ``.env`` file nor
network/Milvus access.
"""
from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import app.main as main_module
from app.agent.nlu import OfflineNLU
from app.config import Settings, get_settings
from app.core.events import EventBus
from app.core.simulator import EnvironmentSimulator
from app.db import Database
from app.devices.registry import DeviceRegistry
from app.seed import seed_database


@pytest.fixture()
def settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Settings]:
    """Isolated settings whose SQLite database lives in pytest's tmp_path."""
    data_dir = tmp_path / "data"
    monkeypatch.setenv("DATA_DIR", str(data_dir))
    get_settings.cache_clear()

    test_settings = Settings(
        data_dir=data_dir,
        llm_provider="offline",
        embedding_provider="local",
        vector_store="local",
        simulator_interval=3600.0,
    )
    test_settings.ensure_dirs()

    # app.main.lifespan looks up the module-level ``settings`` at startup.
    monkeypatch.setattr(main_module, "settings", test_settings)
    yield test_settings
    get_settings.cache_clear()


@pytest.fixture()
def client(settings: Settings) -> Iterator[TestClient]:
    """TestClient with app.main:app's lifespan and an isolated runtime."""
    with TestClient(main_module.app) as test_client:
        yield test_client


@pytest.fixture()
def nlu(settings: Settings) -> Iterator[OfflineNLU]:
    """Offline NLU wired to a freshly seeded device registry (no HTTP)."""
    db = Database(settings.db_path)
    try:
        seed_database(db, settings)
        registry = DeviceRegistry(db)
        registry.load()
        simulator = EnvironmentSimulator(settings, registry, EventBus())
        yield OfflineNLU(registry, simulator, db.load_scenes())
    finally:
        db.close()
