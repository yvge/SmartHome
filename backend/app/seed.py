"""Idempotent demo data seeding."""
from __future__ import annotations

import logging
from typing import Any

from app.config import Settings
from app.db import Database, now_iso
from app.devices.specs import DEVICE_SEEDS, build_device_seed
from app.rag.knowledge import SCENE_SEEDS, build_seed_entries

logger = logging.getLogger(__name__)


def seed_database(db: Database, settings: Settings) -> dict[str, int]:
    db.init_schema()
    now = now_iso()

    device_count = db.query_one("SELECT COUNT(*) AS c FROM devices")
    if not device_count or int(device_count["c"]) == 0:
        devices = []
        for seed in DEVICE_SEEDS:
            device = build_device_seed(seed)
            device["updated_at"] = now
            devices.append(device)
        db.save_devices(devices)
        logger.info("Seeded %d demo devices", len(devices))

    version = db.get_meta("seed_version")
    kb_count = db.count_kb()
    if version != settings.seed_version or kb_count == 0:
        entries = build_seed_entries()
        db.save_kb_entries(entries)
        logger.info("Seeded %d RAG entries", len(entries))

    scene_count = db.query_one("SELECT COUNT(*) AS c FROM scenes")
    if version != settings.seed_version or not scene_count or int(scene_count["c"]) == 0:
        for scene in SCENE_SEEDS:
            payload = dict(scene)
            payload.setdefault("builtin", True)
            payload.setdefault("enabled", True)
            payload["created_at"] = now
            db.save_scene(payload)
        logger.info("Seeded %d built-in scenes", len(SCENE_SEEDS))

    db.set_meta("seed_version", settings.seed_version)
    counts = db.stats()
    return counts


def seed_summary(db: Database) -> dict[str, Any]:
    return {
        "version": db.get_meta("seed_version"),
        "counts": db.stats(),
    }
