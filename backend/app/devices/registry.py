"""In-memory device registry backed by SQLite.

The registry is the single simulation boundary for all device types. Tool
calls, scene steps and the REST API all funnel through ``apply`` so that
validation and state persistence stay consistent.
"""
from __future__ import annotations

import threading
from datetime import datetime
from typing import Any, Callable

from app.db import Database, now_iso
from app.devices.specs import (
    DEVICE_SEEDS,
    ROOM_NAMES,
    TYPE_LABELS,
    TYPE_SPECS,
    build_device_seed,
    capabilities_for,
    default_properties,
    kelvin_to_hex,
)

BOOLEAN_KEYS = {"power", "playing"}
INT_KEYS = {"brightness", "color_temp", "target_temp", "position", "target_humidity", "volume"}
ENUM_VALUES: dict[str, set[str]] = {
    "ac_mode": {"cool", "heat", "dry", "fan", "auto"},
    "fan_speed": {"auto", "low", "medium", "high"},
    "purifier_mode": {"auto", "sleep", "high"},
    "vacuum_mode": {"auto", "spot", "edge", "mop"},
    "track": {"晨间新闻", "轻音乐", "白噪音", "入睡冥想"},
}


class DeviceError(Exception):
    def __init__(self, code: str, message: str, device_id: str | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.device_id = device_id

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code, "message": self.message, "device_id": self.device_id}


ChangeHook = Callable[[dict[str, Any], str], None]


class DeviceRegistry:
    def __init__(self, db: Database, on_change: ChangeHook | None = None) -> None:
        self.db = db
        self._devices: dict[str, dict[str, Any]] = {}
        self._lock = threading.RLock()
        self._on_change = on_change

    # ------------------------------------------------------------ loading
    def load(self) -> None:
        rows = self.db.load_devices()
        if not rows:
            self._seed_defaults()
            rows = self.db.load_devices()
        with self._lock:
            self._devices = {row["id"]: row for row in rows}

    def _seed_defaults(self) -> None:
        now = now_iso()
        seeds = []
        for seed in DEVICE_SEEDS:
            device = build_device_seed(seed)
            device["updated_at"] = now
            seeds.append(device)
        self.db.save_devices(seeds)

    # ------------------------------------------------------------- access
    def snapshot(self) -> list[dict[str, Any]]:
        with self._lock:
            devices = [self._public(dict(device)) for device in self._devices.values()]
        return sorted(devices, key=lambda d: (d.get("sort_order", 0), d["id"]))

    def get(self, device_id: str) -> dict[str, Any]:
        with self._lock:
            device = self._devices.get(device_id)
            if not device:
                raise DeviceError("NOT_FOUND", f"未找到设备 {device_id}", device_id)
            return self._public(dict(device))

    def get_raw(self, device_id: str) -> dict[str, Any]:
        with self._lock:
            device = self._devices.get(device_id)
            if not device:
                raise DeviceError("NOT_FOUND", f"未找到设备 {device_id}", device_id)
            return dict(device)

    def find(
        self, *, room_id: str | None = None, device_type: str | None = None,
        online: bool | None = None,
    ) -> list[dict[str, Any]]:
        with self._lock:
            result = []
            for device in self._devices.values():
                if room_id and device["room_id"] != room_id:
                    continue
                if device_type and device["type"] != device_type:
                    continue
                if online is not None and bool(device["online"]) != online:
                    continue
                result.append(self._public(dict(device)))
        return sorted(result, key=lambda d: (d.get("sort_order", 0), d["id"]))

    def primary(self, device_type: str, room_id: str | None = None) -> dict[str, Any] | None:
        matches = self.find(room_id=room_id, device_type=device_type)
        return matches[0] if matches else None

    def rooms(self) -> list[dict[str, Any]]:
        result = []
        for room_id, name in ROOM_NAMES.items():
            devices = self.find(room_id=room_id)
            if devices:
                result.append({
                    "id": room_id, "name": name, "devices": len(devices),
                    "online": sum(1 for d in devices if d["online"]),
                })
        return result

    def summary(self) -> list[dict[str, Any]]:
        """Compact representation injected into LLM prompts."""
        rows = []
        for device in self.snapshot():
            props = device["properties"]
            state = []
            if device["type"] == "light":
                state.append("开" if props.get("power") else "关")
                if props.get("power"):
                    state.append(f"亮度{props.get('brightness')}%")
            elif device["type"] == "ac":
                state.append("开" if props.get("power") else "关")
                if props.get("power"):
                    state.append(f"{props.get('target_temp')}°C")
            elif device["type"] == "curtain":
                state.append(f"开合{props.get('position')}%")
            elif device["type"] == "purifier":
                state.append("开" if props.get("power") else "关")
            elif device["type"] == "humidifier":
                state.append("开" if props.get("power") else "关")
            elif device["type"] == "socket":
                state.append("通电" if props.get("power") else "断电")
            elif device["type"] == "speaker":
                state.append("播放中" if props.get("playing") else ("待机" if props.get("power") else "关"))
            elif device["type"] == "vacuum":
                state.append("清扫中" if props.get("power") else "在充电座")
            elif device["type"] == "sensor":
                state.append(f"{props.get('temperature')}°C/{props.get('humidity')}%")
            rows.append({
                "id": device["id"],
                "name": device["name"],
                "room": device["room"],
                "type": device["type"],
                "type_label": TYPE_LABELS.get(device["type"], device["type"]),
                "online": device["online"],
                "state": "，".join(state),
            })
        return rows

    # ------------------------------------------------------------- writes
    def apply(
        self, device_id: str, params: dict[str, Any], *, persist: bool = True,
    ) -> dict[str, Any]:
        with self._lock:
            device = self._devices.get(device_id)
            if not device:
                raise DeviceError("NOT_FOUND", f"未找到设备 {device_id}", device_id)
            if not device.get("online", True):
                raise DeviceError(
                    "OFFLINE", f"{device['name']}当前处于离线状态，无法执行操作", device_id
                )
            if device["type"] == "sensor":
                raise DeviceError("READ_ONLY", f"{device['name']}是只读传感器", device_id)

            normalized = self._normalize(device, params)
            if not normalized:
                raise DeviceError("EMPTY_COMMAND", "没有可执行的设备参数", device_id)

            properties = dict(device["properties"])
            properties.update(normalized)
            if device["type"] == "light":
                properties["color_hex"] = kelvin_to_hex(
                    int(properties.get("color_temp", 4000))
                )
            if device["type"] == "vacuum" and "power" in normalized:
                properties["state"] = "cleaning" if normalized["power"] else "docked"
            device["properties"] = properties
            device["updated_at"] = now_iso()
            self._devices[device_id] = device
            public = self._public(dict(device))

        if persist:
            self.db.save_device({**public, "capabilities": capabilities_for(device["type"])})
        if self._on_change:
            self._on_change(public, "device_update")
        return public

    def set_online(self, device_id: str, online: bool) -> dict[str, Any]:
        with self._lock:
            device = self._devices.get(device_id)
            if not device:
                raise DeviceError("NOT_FOUND", f"未找到设备 {device_id}", device_id)
            device["online"] = bool(online)
            device["updated_at"] = now_iso()
            self._devices[device_id] = device
            public = self._public(dict(device))
        self.db.save_device({**public, "capabilities": capabilities_for(device["type"])})
        if self._on_change:
            self._on_change(public, "connectivity")
        return public

    def update_telemetry(self, device_id: str, values: dict[str, Any]) -> dict[str, Any] | None:
        """Simulator-only lightweight update, not persisted on every tick."""
        with self._lock:
            device = self._devices.get(device_id)
            if not device:
                return None
            device["properties"].update(values)
            device["updated_at"] = now_iso()
            return self._public(dict(device))

    def update_simulated_property(
        self, device_id: str, key: str, value: Any, *, persist: bool = False,
    ) -> dict[str, Any] | None:
        with self._lock:
            device = self._devices.get(device_id)
            if not device:
                return None
            if device["properties"].get(key) == value:
                return None
            device["properties"][key] = value
            device["updated_at"] = now_iso()
            public = self._public(dict(device))
        if persist:
            self.db.save_device({**public, "capabilities": capabilities_for(device["type"])})
        if self._on_change:
            self._on_change(public, "telemetry")
        return public

    def _normalize(self, device: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
        device_type = device["type"]
        spec = TYPE_SPECS.get(device_type, {})
        writable = set(spec.get("writable", []))
        capabilities = {cap["key"]: cap for cap in spec.get("capabilities", [])}
        normalized: dict[str, Any] = {}

        for key, value in params.items():
            if key in {"device_id", "device_ids"}:
                continue
            if key not in writable:
                raise DeviceError(
                    "INVALID_PARAM",
                    f"{device['name']}不支持参数「{key}」",
                    device["id"],
                )

            cap = capabilities.get(key, {})
            if key in BOOLEAN_KEYS:
                if not isinstance(value, bool):
                    value = str(value).lower() in {"1", "true", "on", "yes", "开"}
                normalized[key] = value
            elif key in INT_KEYS:
                try:
                    number = int(round(float(value)))
                except (TypeError, ValueError) as exc:
                    raise DeviceError(
                        "INVALID_VALUE", f"「{cap.get('label', key)}」需要一个数字", device["id"]
                    ) from exc
                minimum = cap.get("min")
                maximum = cap.get("max")
                if minimum is not None:
                    number = max(minimum, number)
                if maximum is not None:
                    number = min(maximum, number)
                normalized[key] = number
            elif key in {"mode", "fan_speed", "track"}:
                allowed_key = {
                    ("ac", "mode"): "ac_mode",
                    ("ac", "fan_speed"): "fan_speed",
                    ("purifier", "mode"): "purifier_mode",
                    ("vacuum", "mode"): "vacuum_mode",
                    ("speaker", "track"): "track",
                }.get((device_type, key))
                allowed = ENUM_VALUES.get(allowed_key or "", set())
                if allowed and value not in allowed:
                    raise DeviceError(
                        "INVALID_VALUE",
                        f"「{cap.get('label', key)}」不支持取值 {value}",
                        device["id"],
                    )
                normalized[key] = value
            else:
                normalized[key] = value

        # Convenience: adjusting a functional property implies power-on.
        power_implied = (
            device_type == "light" and {"brightness", "color_temp"} & params.keys()
        ) or (
            device_type == "ac" and {"target_temp", "mode", "fan_speed"} & params.keys()
        ) or (
            device_type == "purifier" and "mode" in params
        ) or (
            device_type == "humidifier" and "target_humidity" in params
        ) or (
            device_type == "speaker" and {"volume", "track", "playing"} & params.keys()
        ) or (
            device_type == "vacuum" and "mode" in params
        )
        if power_implied and "power" not in normalized:
            normalized["power"] = True
        if device_type == "light" and normalized.get("power") is False:
            pass
        if device_type == "vacuum" and normalized.get("power") is True:
            normalized.setdefault("battery", max(0, int(device["properties"].get("battery", 100))))
        return normalized

    @staticmethod
    def _public(device: dict[str, Any]) -> dict[str, Any]:
        properties = dict(device.get("properties", {}))
        if device["type"] == "light" and "color_hex" not in properties:
            properties["color_hex"] = kelvin_to_hex(int(properties.get("color_temp", 4000)))
        capabilities = device.get("capabilities") or capabilities_for(device["type"])
        return {
            "id": device["id"],
            "name": device["name"],
            "room": device["room"],
            "room_id": device["room_id"],
            "type": device["type"],
            "type_label": TYPE_LABELS.get(device["type"], device["type"]),
            "online": bool(device.get("online", True)),
            "icon": device.get("icon", TYPE_SPECS[device["type"]]["icon"]),
            "sort_order": device.get("sort_order", 0),
            "properties": properties,
            "capabilities": capabilities,
            "updated_at": device.get("updated_at") or now_iso(),
        }

    def save_all(self) -> None:
        devices = []
        for device in self.snapshot():
            devices.append({**device, "capabilities": device["capabilities"]})
        self.db.save_devices(devices)

    def reset(self) -> list[dict[str, Any]]:
        now = now_iso()
        seeds = []
        for seed in DEVICE_SEEDS:
            device = build_device_seed(seed)
            device["updated_at"] = now
            seeds.append(device)
        self.db.save_devices(seeds)
        with self._lock:
            self._devices = {seed["id"]: seed for seed in seeds}
        return self.snapshot()


def humanize_params(device: dict[str, Any], params: dict[str, Any]) -> str:
    """Turn a parameter patch into a short Chinese description."""
    parts: list[str] = []
    if params.get("power") is True:
        parts.append("开启")
    elif params.get("power") is False:
        parts.append("关闭")
    labels = {cap["key"]: cap.get("label", cap["key"]) for cap in device.get("capabilities", [])}
    if "brightness" in params:
        parts.append(f"亮度{params['brightness']}%")
    if "color_temp" in params:
        parts.append(f"色温{params['color_temp']}K")
    if "target_temp" in params:
        parts.append(f"设定{params['target_temp']}°C")
    if "mode" in params and device["type"] == "ac":
        mapping = {"cool": "制冷", "heat": "制热", "dry": "除湿", "fan": "送风", "auto": "自动"}
        parts.append(mapping.get(params["mode"], params["mode"]))
    if "mode" in params and device["type"] in {"purifier", "vacuum"}:
        parts.append(f"模式{params['mode']}")
    if "position" in params:
        parts.append(f"开合度{params['position']}%")
    if "target_humidity" in params:
        parts.append(f"目标湿度{params['target_humidity']}%")
    if "volume" in params:
        parts.append(f"音量{params['volume']}%")
    if "playing" in params:
        parts.append("开始播放" if params["playing"] else "暂停播放")
    if "track" in params:
        parts.append(f"播放{params['track']}")
    if not parts:
        parts.append("状态已更新")
    return "，".join(parts)


def timestamp() -> str:
    return datetime.now().strftime("%H:%M:%S")
