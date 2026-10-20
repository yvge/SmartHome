"""Application runtime container.

Holds the single long-lived instance of every subsystem and wires callbacks
(device changes -> event bus) plus the two compiled LangGraphs.
"""
from __future__ import annotations

import logging
import threading
import time
from datetime import datetime
from typing import Any

from langgraph.checkpoint.memory import MemorySaver

from app.agent.llm import LLMClient
from app.agent.nlu import OfflineNLU
from app.agent.tools import ToolExecutor
from app.config import Settings, get_settings
from app.core.events import EventBus
from app.core.simulator import EnvironmentSimulator
from app.db import Database
from app.devices.registry import DeviceRegistry
from app.devices.specs import ROOMS
from app.rag.service import RAGService
from app.seed import seed_database

logger = logging.getLogger(__name__)


class AppRuntime:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.started_wall = datetime.now().astimezone()
        self.started_monotonic = time.monotonic()
        self.db = Database(self.settings.db_path)
        self.bus = EventBus()
        self.devices = DeviceRegistry(self.db, on_change=self._on_device_change)
        self.simulator = EnvironmentSimulator(self.settings, self.devices, self.bus)
        self.rag = RAGService(self.settings, self.db)
        self.llm = LLMClient(self.settings)
        self.memory = MemorySaver()
        self.nlu = OfflineNLU(self.devices, self.simulator, [])
        self.tool_executor = ToolExecutor(self.devices, self.simulator)
        self.scene_graph = None
        self.agent_graph = None
        self._started = False
        self._background_tasks: set[Any] = set()
        self._lock = threading.Lock()
        self.reload_count = 0

    # ------------------------------------------------------------ lifecycle
    async def start(self) -> None:
        if self._started:
            return
        seed_counts = seed_database(self.db, self.settings)
        self.devices.load()
        self.nlu = OfflineNLU(self.devices, self.simulator, self.db.load_scenes())
        await self.rag.initialize()
        # Imported here to avoid circular imports while modules are loading.
        from app.agent.graph import build_agent_graph
        from app.agent.scene_graph import build_scene_graph

        self.scene_graph = build_scene_graph(self)
        self.agent_graph = build_agent_graph(self)
        self.simulator.start()
        self._started = True
        logger.info(
            "Runtime ready | devices=%s scenes=%s kb=%s llm=%s rag=%s",
            seed_counts.get("devices"), seed_counts.get("scenes"),
            seed_counts.get("kb_entries"), self.llm.status()["model"],
            self.rag.store.backend if self.rag.store else "none",
        )

    async def stop(self) -> None:
        await self.simulator.stop()
        await self.rag.close()
        await self.llm.close()
        self.db.close()
        self._started = False
        logger.info("Runtime stopped")

    @property
    def started(self) -> bool:
        return self._started

    @property
    def uptime_seconds(self) -> int:
        return int(time.monotonic() - self.started_monotonic)

    # -------------------------------------------------------------- callback
    def _on_device_change(self, device: dict[str, Any], action: str) -> None:
        self.bus.publish_nowait(
            "device_update",
            {"device": device, "action": action},
        )

    # --------------------------------------------------------------- reloads
    def reload_scene_catalog(self) -> None:
        with self._lock:
            self.nlu.scenes = self.db.load_scenes()
            self.reload_count += 1

    async def reindex_rag(self) -> None:
        await self.rag.reindex(self.db.load_kb())

    # ---------------------------------------------------------------- state
    def snapshot(self) -> dict[str, Any]:
        environment = self.simulator.environment
        return {
            "devices": self.devices.snapshot(),
            "environment": environment,
            "rooms": self.simulator.snapshot()["rooms"],
            "room_meta": ROOMS,
            "period": environment.get("period"),
            "timestamp": datetime.now().astimezone().isoformat(timespec="seconds"),
        }

    async def status(self) -> dict[str, Any]:
        rag_stats = await self.rag.stats()
        db_stats = self.db.stats()
        return {
            "app": {
                "name": self.settings.app_name,
                "version": self.settings.app_version,
                "started_at": self.started_wall.isoformat(timespec="seconds"),
                "uptime_seconds": self.uptime_seconds,
                "demo_mode": not self.llm.enabled,
            },
            "llm": self.llm.status(),
            "rag": rag_stats,
            "simulator": {
                "running": self.simulator.is_running,
                "interval": self.settings.simulator_interval,
                "tick": self.simulator.snapshot()["tick"],
            },
            "events": {
                "subscribers": self.bus.subscriber_count,
            },
            "counts": {
                **db_stats,
                "devices_online": sum(1 for d in self.devices.snapshot() if d["online"]),
            },
        }

    def graph_topology(self) -> dict[str, Any]:
        return {
            "nodes": [
                {"id": "understand", "label": "意图理解", "kind": "agent",
                 "description": "RAG 召回示例 + LLM/规则结构化解析，识别多步指令与代词"},
                {"id": "plan", "label": "工具规划", "kind": "agent",
                 "description": "Function Calling 将动作映射为 JSON Schema 工具调用"},
                {"id": "guard", "label": "安全检查", "kind": "agent",
                 "description": "设备存在性、在线状态、参数范围与权限校验"},
                {"id": "execute", "label": "设备执行", "kind": "agent",
                 "description": "调用异构设备适配器，实时推送执行结果"},
                {"id": "verify", "label": "状态校验", "kind": "agent",
                 "description": "读取设备真实状态，校验指令是否生效"},
                {"id": "scene", "label": "场景子图", "kind": "subgraph",
                 "description": "多步场景：条件判断 → 动作编排 → 设备联动 → 兜底 → 校验"},
                {"id": "fallback", "label": "异常兜底", "kind": "agent",
                 "description": "无效指令、离线设备或内部异常时生成可恢复回复"},
                {"id": "respond", "label": "生成回复", "kind": "agent",
                 "description": "结合真实执行结果流式生成自然语言回复"},
            ],
            "edges": [
                ["understand", "plan"], ["understand", "scene"], ["understand", "respond"],
                ["plan", "guard"], ["guard", "execute"], ["guard", "fallback"],
                ["execute", "verify"], ["verify", "respond"],
                ["scene", "respond"], ["fallback", "respond"],
            ],
            "scene_nodes": [
                {"id": "load", "label": "加载场景"},
                {"id": "conditions", "label": "条件判断"},
                {"id": "plan", "label": "动作编排"},
                {"id": "execute", "label": "设备联动"},
                {"id": "fallback", "label": "异常兜底"},
                {"id": "verify", "label": "场景校验"},
            ],
        }
