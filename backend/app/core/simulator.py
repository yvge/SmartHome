"""Physical-ish home simulation.

No real hardware is required for the demo: lights influence ambient lux,
ACs pull room temperature toward their setpoint, purifiers clean PM2.5,
humidifiers regulate humidity, and everything contributes to power draw.
The simulator publishes a full snapshot on every tick for the live UI.
"""
from __future__ import annotations

import asyncio
import logging
import random
from datetime import datetime
from typing import Any

from app.config import Settings
from app.core.events import EventBus
from app.db import now_iso
from app.devices.registry import DeviceRegistry
from app.devices.specs import ROOMS

logger = logging.getLogger(__name__)


class EnvironmentSimulator:
    def __init__(self, settings: Settings, registry: DeviceRegistry, bus: EventBus) -> None:
        self.settings = settings
        self.registry = registry
        self.bus = bus
        self._task: asyncio.Task[None] | None = None
        self._running = False
        self._tick_count = 0
        self.room_climate: dict[str, dict[str, float]] = {
            "living": {"temperature": 26.4, "humidity": 52.0},
            "bedroom": {"temperature": 26.8, "humidity": 50.0},
            "second_bedroom": {"temperature": 26.9, "humidity": 49.0},
            "study": {"temperature": 27.1, "humidity": 48.0},
            "kitchen": {"temperature": 27.4, "humidity": 55.0},
            "balcony": {"temperature": 30.2, "humidity": 58.0},
        }
        self.environment: dict[str, Any] = {
            "indoor_temp": 26.4,
            "humidity": 52.0,
            "pm25": 21,
            "co2": 640,
            "lux": 460,
            "outdoor_temp": 31.0,
            "outdoor_weather": "晴",
            "power_w": 0.0,
            "period": "午后",
            "updated_at": now_iso(),
        }

    # ------------------------------------------------------------- lifecycle
    def start(self) -> None:
        if self._task and not self._task.done():
            return
        self._running = True
        self.tick()
        self._task = asyncio.create_task(self._loop())
        logger.info("Environment simulator started (interval=%.1fs)", self.settings.simulator_interval)

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        self.registry.save_all()
        logger.info("Environment simulator stopped")

    async def _loop(self) -> None:
        while self._running:
            await asyncio.sleep(self.settings.simulator_interval)
            try:
                self.tick()
                await self.bus.publish("state", self.snapshot())
            except asyncio.CancelledError:
                raise
            except Exception:  # pragma: no cover - keep the simulator alive
                logger.exception("Simulator tick failed")

    # ----------------------------------------------------------------- tick
    def tick(self) -> dict[str, Any]:
        self._tick_count += 1
        devices = self.registry.snapshot()
        hour = datetime.now().hour
        period, daylight = self._daylight(hour)

        lights = [d for d in devices if d["type"] == "light" and d["properties"].get("power")]
        acs = [d for d in devices if d["type"] == "ac" and d["properties"].get("power")]
        purifier = next((d for d in devices if d["type"] == "purifier" and d["properties"].get("power")), None)
        humidifier = next((d for d in devices if d["type"] == "humidifier" and d["properties"].get("power")), None)
        curtains = [d for d in devices if d["type"] == "curtain"]
        sockets = [d for d in devices if d["type"] == "socket"]
        speaker = next((d for d in devices if d["type"] == "speaker"), None)
        vacuum = next((d for d in devices if d["type"] == "vacuum"), None)

        # ---- room temperatures: AC pulls its room, otherwise outdoor drift.
        for room_id, climate in self.room_climate.items():
            room_acs = [d for d in acs if d["room_id"] == room_id]
            if room_acs:
                target = sum(float(d["properties"].get("target_temp", 26)) for d in room_acs) / len(room_acs)
                delta = target - climate["temperature"]
                step = max(-0.22, min(0.22, delta * 0.35))
                climate["temperature"] = round(climate["temperature"] + step, 2)
                climate["humidity"] = round(
                    min(70.0, max(35.0, climate["humidity"] + (48 - climate["humidity"]) * 0.03)), 1
                )
            else:
                drift = (float(self.environment["outdoor_temp"]) - climate["temperature"]) * 0.012
                climate["temperature"] = round(climate["temperature"] + drift, 2)
                climate["humidity"] = round(
                    min(75.0, max(30.0, climate["humidity"] + random.uniform(-0.3, 0.3))), 1
                )

        # ---- ambient light: daylight through curtains + artificial lights.
        curtain_ratio = (
            sum(float(d["properties"].get("position", 0)) for d in curtains) / (100 * len(curtains))
            if curtains else 0.4
        )
        light_lux = sum(
            float(d["properties"].get("brightness", 0)) * 2.4
            for d in lights
        )
        lux = round(45 + daylight * curtain_ratio * 720 + light_lux)

        # ---- PM2.5 / humidity / CO2.
        pm25 = float(self.environment["pm25"])
        if purifier:
            mode = purifier["properties"].get("mode", "auto")
            rate = {"high": 2.6, "auto": 1.5, "sleep": 0.8}.get(mode, 1.5)
            pm25 = max(6.0, pm25 - rate)
        else:
            pm25 = min(38.0, pm25 + 0.35)
        self.registry.update_telemetry("purifier_living", {"pm25": round(pm25)})

        humidity = float(self.room_climate["living"]["humidity"])
        if humidifier:
            target = float(humidifier["properties"].get("target_humidity", 55))
            room = humidifier["room_id"]
            self.room_climate[room]["humidity"] = round(
                min(80.0, max(30.0, self.room_climate[room]["humidity"] + (target - self.room_climate[room]["humidity"]) * 0.12)), 1
            )
        co2 = max(420, min(1200, int(float(self.environment["co2"]) + random.randint(-12, 9))))
        if purifier:
            co2 = max(420, co2 - 8)

        # ---- vacuum battery.
        if vacuum and vacuum["properties"].get("power"):
            battery = int(vacuum["properties"].get("battery", 100))
            battery = max(0, battery - random.randint(1, 2))
            self.registry.update_telemetry("vacuum_robot", {"battery": battery})
            if battery <= 12:
                self.registry.apply("vacuum_robot", {"power": False})
                self.bus.publish_nowait(
                    "notification",
                    {"level": "info", "message": "扫地机器人电量偏低，已自动返回充电座"},
                )

        # ---- power model.
        power = 46.0
        for light in lights:
            power += 6 + float(light["properties"].get("brightness", 0)) * 0.32
        power += len(acs) * 880.0
        if purifier:
            power += {"high": 58, "auto": 32, "sleep": 16}.get(purifier["properties"].get("mode", "auto"), 32)
        if humidifier:
            power += 24
        power += sum(125.0 for d in sockets if d["properties"].get("power"))
        if speaker and speaker["properties"].get("playing"):
            power += 9
        if vacuum and vacuum["properties"].get("power"):
            power += 42

        self.registry.update_telemetry(
            "socket_tv",
            {"power_w": 125 if any(d["properties"].get("power") for d in sockets) else 0},
        )

        # ---- living-room sensor reflects the living-room climate.
        living = self.room_climate["living"]
        self.environment.update({
            "indoor_temp": living["temperature"],
            "humidity": living["humidity"],
            "pm25": round(pm25),
            "co2": co2,
            "lux": lux,
            "outdoor_temp": round(
                float(self.environment["outdoor_temp"]) + random.uniform(-0.05, 0.05), 1
            ),
            "power_w": round(power, 1),
            "period": period,
            "updated_at": now_iso(),
        })
        self.registry.update_telemetry(
            "sensor_living",
            {
                "temperature": living["temperature"],
                "humidity": living["humidity"],
                "pm25": round(pm25),
            },
        )
        second = self.room_climate["second_bedroom"]
        self.registry.update_telemetry(
            "sensor_second",
            {
                "temperature": second["temperature"],
                "humidity": second["humidity"],
                "pm25": round(pm25),
            },
        )
        return self.snapshot()

    # --------------------------------------------------------------- utils
    @staticmethod
    def _daylight(hour: int) -> tuple[str, float]:
        if 5 <= hour < 8:
            return "清晨", 0.35
        if 8 <= hour < 11:
            return "上午", 0.8
        if 11 <= hour < 14:
            return "正午", 1.0
        if 14 <= hour < 18:
            return "午后", 0.75
        if 18 <= hour < 21:
            return "傍晚", 0.28
        if 21 <= hour < 24:
            return "夜晚", 0.04
        return "深夜", 0.0

    def room(self, room_id: str) -> dict[str, Any] | None:
        climate = self.room_climate.get(room_id)
        if not climate:
            return None
        return {
            "id": room_id,
            "temperature": climate["temperature"],
            "humidity": climate["humidity"],
        }

    def snapshot(self) -> dict[str, Any]:
        return {
            "environment": dict(self.environment),
            "rooms": [
                {"id": room_id, **climate}
                for room_id, climate in self.room_climate.items()
            ],
            "devices": self.registry.snapshot(),
            "room_meta": ROOMS,
            "period": self.environment.get("period"),
            "timestamp": now_iso(),
            "tick": self._tick_count,
        }

    @property
    def is_running(self) -> bool:
        return self._running
